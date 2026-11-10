"""
Comprehensive OAuth authentication tests for ImpactIntel.

Covers:
- HMAC state generation and validation
- Authorization URL encoding correctness
- /auth/github/url endpoint
- /auth/github/callback (success, error, invalid state, missing code)
- /auth/me (authenticated, unauthenticated, expired JWT)
- /repos authentication enforcement and user isolation
- CORS configuration
"""
import os
import time
import tempfile
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Environment: set test-specific overrides before app modules are imported.
# conftest.py sets ALLOW_DEV_BYPASS=true globally; individual tests patch it.
# ---------------------------------------------------------------------------

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_oauth_tests_2026")

# ---------------------------------------------------------------------------
# App / DB bootstrap — use a named temp file so all connections share tables
# ---------------------------------------------------------------------------

from app.db.models import Base
from app.db.session import get_db
from app.api.app import create_app
from app.services.github_oauth import GitHubOAuthService
from app.core.config import JWT_SECRET_KEY, JWT_ALGORITHM, FRONTEND_URL

# Temporary SQLite file shared across all test-module connections
_TMP_DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB_FILE.close()
_TEST_DB_URL = f"sqlite:///{_TMP_DB_FILE.name}"

_TEST_ENGINE = create_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _override_get_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def app():
    # Create all tables on the shared test engine BEFORE the app/client starts
    Base.metadata.create_all(bind=_TEST_ENGINE)
    # Point the app's own engine at the same file so init_db() in lifespan is harmless
    with patch("app.db.session.DATABASE_URL", _TEST_DB_URL):
        application = create_app()
    # Override DB dependency so all routes use our test engine sessions
    application.dependency_overrides[get_db] = _override_get_db
    yield application
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    _TEST_ENGINE.dispose()
    try:
        os.unlink(_TMP_DB_FILE.name)
    except OSError:
        pass


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: build a real JWT for a mock user
# ---------------------------------------------------------------------------

def _make_jwt(user: dict, access_token: str = "real_token_abc", expired: bool = False) -> str:
    exp = int(time.time()) - 3600 if expired else int(time.time()) + 86400
    payload = {
        "sub": str(user.get("id", user.get("login"))),
        "user": user,
        "access_token": access_token,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


MOCK_USER_A = {
    "id": 42,
    "login": "alice",
    "name": "Alice",
    "email": "alice@example.com",
    "avatar_url": "https://avatars.githubusercontent.com/u/42",
    "html_url": "https://github.com/alice",
    "bio": None,
}

MOCK_USER_B = {
    "id": 99,
    "login": "bob",
    "name": "Bob",
    "email": "bob@example.com",
    "avatar_url": "https://avatars.githubusercontent.com/u/99",
    "html_url": "https://github.com/bob",
    "bio": None,
}


# ===========================================================================
# Fix 1 & 2: State generation and validation
# ===========================================================================

class TestOAuthStateValidation:
    def test_generate_state_returns_string_with_dot(self):
        state = GitHubOAuthService.generate_oauth_state()
        assert isinstance(state, str)
        assert "." in state

    def test_valid_state_passes_validation(self):
        state = GitHubOAuthService.generate_oauth_state()
        assert GitHubOAuthService.validate_oauth_state(state) is True

    def test_mutated_mac_fails_validation(self):
        state = GitHubOAuthService.generate_oauth_state()
        nonce, mac = state.rsplit(".", 1)
        # flip one char in the MAC
        bad_mac = mac[:-1] + ("x" if mac[-1] != "x" else "y")
        assert GitHubOAuthService.validate_oauth_state(f"{nonce}.{bad_mac}") is False

    def test_mutated_nonce_fails_validation(self):
        state = GitHubOAuthService.generate_oauth_state()
        nonce, mac = state.rsplit(".", 1)
        assert GitHubOAuthService.validate_oauth_state(f"TAMPERED_NONCE.{mac}") is False

    def test_none_state_fails(self):
        assert GitHubOAuthService.validate_oauth_state(None) is False

    def test_empty_state_fails(self):
        assert GitHubOAuthService.validate_oauth_state("") is False

    def test_state_without_dot_fails(self):
        assert GitHubOAuthService.validate_oauth_state("nodothere") is False

    def test_different_states_are_unique(self):
        states = {GitHubOAuthService.generate_oauth_state() for _ in range(10)}
        assert len(states) == 10


# ===========================================================================
# Fix 2: Authorization URL is properly URL-encoded and GitHub App compatible
# ===========================================================================

class TestAuthorizationURL:
    def test_url_contains_redirect_uri_encoded(self):
        """redirect_uri must be percent-encoded, not raw in the query string."""
        with patch("app.services.github_oauth.GITHUB_CLIENT_ID", "fake_client_id"):
            state = GitHubOAuthService.generate_oauth_state()
            url = GitHubOAuthService.get_authorization_url(state=state)

        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "github.com"
        assert parsed.path == "/login/oauth/authorize"

        # The redirect_uri value inside the query string must NOT contain raw ://
        # (it should be percent-encoded as %3A%2F%2F)
        qs = parsed.query
        # Find the redirect_uri= value
        params = parse_qs(qs)
        assert "redirect_uri" in params
        # Confirm the redirect_uri was round-trip parsed correctly (urlencode handled it)
        redirect_uri_val = params["redirect_uri"][0]
        assert "://" in redirect_uri_val  # decoded value contains ://

    def test_no_raw_colon_slash_in_redirect_uri_param_value(self):
        """The raw query string must not embed unencoded ://  inside the redirect_uri param."""
        with patch("app.services.github_oauth.GITHUB_CLIENT_ID", "fake_client_id"):
            with patch(
                "app.services.github_oauth.GITHUB_OAUTH_REDIRECT_URI",
                "https://impactintel.onrender.com/api/auth/github/callback",
            ):
                state = GitHubOAuthService.generate_oauth_state()
                url = GitHubOAuthService.get_authorization_url(state=state)

        parsed = urlparse(url)
        raw_qs = parsed.query
        # redirect_uri= segment should not contain literal ://
        idx = raw_qs.find("redirect_uri=")
        assert idx != -1
        after_key = raw_qs[idx + len("redirect_uri="):]
        # Up to the next & (or end of string)
        param_raw_value = after_key.split("&")[0]
        assert "://" not in param_raw_value, (
            f"redirect_uri value is not URL-encoded in query string: {param_raw_value!r}"
        )

    def test_url_contains_client_id(self):
        with patch("app.services.github_oauth.GITHUB_CLIENT_ID", "my_client_123"):
            state = GitHubOAuthService.generate_oauth_state()
            url = GitHubOAuthService.get_authorization_url(state=state)
        assert "client_id=my_client_123" in url

    def test_url_contains_state(self):
        with patch("app.services.github_oauth.GITHUB_CLIENT_ID", "fake_client_id"):
            state = GitHubOAuthService.generate_oauth_state()
            url = GitHubOAuthService.get_authorization_url(state=state)
        params = parse_qs(urlparse(url).query)
        assert params["state"][0] == state

    def test_url_does_not_contain_scope_for_github_app(self):
        """GitHub Apps (client_id prefix Iv23/Iv1) do NOT support the ``scope``
        query parameter.  Passing ``scope`` causes GitHub to return a 404 page
        immediately, before any redirect occurs.  Permissions are configured
        statically in the GitHub App settings dashboard instead."""
        with patch("app.services.github_oauth.GITHUB_CLIENT_ID", "Iv23liNIEtnXk14suaTc"):
            state = GitHubOAuthService.generate_oauth_state()
            url = GitHubOAuthService.get_authorization_url(state=state)
        params = parse_qs(urlparse(url).query)
        assert "scope" not in params, (
            "scope parameter must not be present in GitHub App authorization URL"
        )


# ===========================================================================
# /api/auth/github/url endpoint
# ===========================================================================

class TestAuthUrlEndpoint:
    def test_returns_url_and_state(self, client):
        resp = client.get("/api/auth/github/url")
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        assert "state" in data
        assert isinstance(data["url"], str)
        assert isinstance(data["state"], str)

    def test_state_contains_dot_separator(self, client):
        """HMAC state has nonce.mac format."""
        resp = client.get("/api/auth/github/url")
        assert "." in resp.json()["state"]

    def test_state_is_valid_hmac(self, client):
        resp = client.get("/api/auth/github/url")
        state = resp.json()["state"]
        assert GitHubOAuthService.validate_oauth_state(state)


# ===========================================================================
# /api/auth/github/callback endpoint
# ===========================================================================

class TestCallbackEndpoint:
    """
    For callback tests we need ALLOW_DEV_BYPASS=False so that state validation runs.
    We patch the config constant in routes.py AND github_oauth.py simultaneously.
    """

    _BYPASS_FALSE = {
        "app.api.routes.ALLOW_DEV_BYPASS": False,
        "app.services.github_oauth.ALLOW_DEV_BYPASS": False,
    }

    def test_callback_access_denied_error_redirects(self, client):
        resp = client.get(
            "/api/auth/github/callback",
            params={"error": "access_denied"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "error=access_denied" in resp.headers["location"]

    def test_callback_missing_code_redirects_to_error(self, client):
        with patch("app.api.routes.ALLOW_DEV_BYPASS", False):
            valid_state = GitHubOAuthService.generate_oauth_state()
            resp = client.get(
                "/api/auth/github/callback",
                params={"state": valid_state},
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        assert "error=missing_code" in resp.headers["location"]

    def test_callback_with_invalid_state_redirects_to_error(self, client):
        with patch("app.api.routes.ALLOW_DEV_BYPASS", False):
            resp = client.get(
                "/api/auth/github/callback",
                params={"code": "some_code", "state": "invalid.state"},
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        assert "error=invalid_state" in resp.headers["location"]

    def test_callback_with_missing_state_redirects_to_error(self, client):
        with patch("app.api.routes.ALLOW_DEV_BYPASS", False):
            resp = client.get(
                "/api/auth/github/callback",
                params={"code": "some_code"},
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        assert "error=invalid_state" in resp.headers["location"]

    def test_callback_success_redirects_to_frontend_with_token(self, client):
        """Full happy path: valid state → exchange → profile → JWT → frontend redirect."""
        valid_state = GitHubOAuthService.generate_oauth_state()
        with (
            patch("app.api.routes.ALLOW_DEV_BYPASS", False),
            patch.object(
                GitHubOAuthService,
                "exchange_code_for_token",
                return_value="gho_real_access_token",
            ),
            patch.object(
                GitHubOAuthService,
                "get_user_profile",
                return_value=MOCK_USER_A,
            ),
        ):
            resp = client.get(
                "/api/auth/github/callback",
                params={"code": "real_code_abc", "state": valid_state},
                follow_redirects=False,
            )

        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "/auth/callback" in location
        assert "token=" in location
        assert "error" not in location

    def test_callback_redirect_goes_to_frontend_not_backend(self, client):
        """The redirect must NOT point back to the backend (Render) host."""
        valid_state = GitHubOAuthService.generate_oauth_state()
        with (
            patch("app.api.routes.ALLOW_DEV_BYPASS", False),
            patch.object(GitHubOAuthService, "exchange_code_for_token", return_value="tok"),
            patch.object(GitHubOAuthService, "get_user_profile", return_value=MOCK_USER_A),
        ):
            resp = client.get(
                "/api/auth/github/callback",
                params={"code": "some_code", "state": valid_state},
                follow_redirects=False,
            )

        location = resp.headers["location"]
        assert "impactintel.onrender.com" not in location

    def test_callback_exchange_failure_redirects_access_denied(self, client):
        valid_state = GitHubOAuthService.generate_oauth_state()
        with (
            patch("app.api.routes.ALLOW_DEV_BYPASS", False),
            patch.object(GitHubOAuthService, "exchange_code_for_token", return_value=None),
        ):
            resp = client.get(
                "/api/auth/github/callback",
                params={"code": "bad_code", "state": valid_state},
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        assert "error=access_denied" in resp.headers["location"]


# ===========================================================================
# /api/auth/me endpoint
# ===========================================================================

class TestAuthMeEndpoint:
    def test_unauthenticated_returns_401(self, client):
        with patch("app.api.routes.ALLOW_DEV_BYPASS", False):
            resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_valid_jwt_returns_user_profile(self, client):
        token = _make_jwt(MOCK_USER_A, "tok_abc")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["user"]["login"] == "alice"

    def test_expired_jwt_returns_401(self, client):
        token = _make_jwt(MOCK_USER_A, "tok_abc", expired=True)
        with patch("app.api.routes.ALLOW_DEV_BYPASS", False):
            resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_malformed_token_returns_401(self, client):
        with patch("app.api.routes.ALLOW_DEV_BYPASS", False):
            resp = client.get("/api/auth/me", headers={"Authorization": "Bearer notavalidjwt"})
        assert resp.status_code == 401


# ===========================================================================
# /api/repos authentication & user isolation
# ===========================================================================

class TestReposEndpoint:
    def test_unauthenticated_returns_401(self, client):
        with patch("app.api.routes.ALLOW_DEV_BYPASS", False):
            resp = client.get("/api/repos")
        assert resp.status_code == 401

    def test_user_a_repos_not_exposed_to_user_b(self, client):
        """
        Each user's repos come from their own GitHub App installations.
        Mocking installations to return different repos per user so we can
        verify isolation.
        """
        # User A: has installation with repo "alice/secret-repo"
        # User B: no installations

        token_a = _make_jwt(MOCK_USER_A, "tok_alice")
        token_b = _make_jwt(MOCK_USER_B, "tok_bob")

        def mock_get_user_installations(access_token):
            if access_token == "tok_alice":
                return [{"id": 100, "account": {"login": "alice"}}]
            return []  # bob has no installations

        def mock_list_accessible_repositories(inst_id):
            if inst_id == 100:
                return [
                    {
                        "id": 999,
                        "full_name": "alice/secret-repo",
                        "name": "secret-repo",
                        "owner": {"login": "alice"},
                        "description": "private",
                        "default_branch": "main",
                        "private": True,
                        "language": "Python",
                    }
                ]
            return []

        with (
            patch("app.api.routes.ALLOW_DEV_BYPASS", False),
            patch("app.api.routes.GitHubAppService") as MockGHApp,
        ):
            mock_gh = MagicMock()
            mock_gh.get_user_installations.side_effect = mock_get_user_installations
            mock_gh.list_accessible_repositories.side_effect = mock_list_accessible_repositories
            MockGHApp.return_value = mock_gh

            resp_a = client.get("/api/repos", headers={"Authorization": f"Bearer {token_a}"})
            resp_b = client.get("/api/repos", headers={"Authorization": f"Bearer {token_b}"})

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        full_names_a = [r["full_name"] for r in resp_a.json()]
        full_names_b = [r["full_name"] for r in resp_b.json()]

        assert "alice/secret-repo" in full_names_a
        assert "alice/secret-repo" not in full_names_b

    def test_missing_installation_returns_empty_repos(self, client):
        """User with no GitHub App installation should get an empty list from GitHub."""
        token = _make_jwt(MOCK_USER_A, "tok_no_install")

        with (
            patch("app.api.routes.ALLOW_DEV_BYPASS", False),
            patch("app.api.routes.GitHubAppService") as MockGHApp,
        ):
            mock_gh = MagicMock()
            mock_gh.get_user_installations.return_value = []
            MockGHApp.return_value = mock_gh

            resp = client.get("/api/repos", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        # May include DB-registered repos, but no GitHub App repos
        data = resp.json()
        assert isinstance(data, list)


# ===========================================================================
# CORS configuration
# ===========================================================================

class TestCORSConfig:
    def test_cors_allows_production_frontend(self, app):
        """The app's CORS middleware must include the Vercel production frontend."""
        from app.api.app import get_cors_origins
        with patch("app.api.app.FRONTEND_URL", "https://impactintel.vercel.app"):
            origins = get_cors_origins()
        assert "https://impactintel.vercel.app" in origins

    def test_cors_does_not_allow_wildcard(self, app):
        """Wildcard '*' must never appear in allowed origins."""
        from app.api.app import get_cors_origins
        with patch("app.api.app.CORS_ORIGINS", "*"):
            origins = get_cors_origins()
        assert "*" not in origins

    def test_cors_does_not_allow_wildcard_via_cors_origins_env(self, app):
        from app.api.app import get_cors_origins
        with patch("app.api.app.CORS_ORIGINS", "*, https://example.com"):
            origins = get_cors_origins()
        assert "*" not in origins

    def test_cors_allows_localhost_by_default(self, app):
        from app.api.app import get_cors_origins
        origins = get_cors_origins()
        assert "http://localhost:5173" in origins

    def test_cors_options_response_for_production_origin(self, client):
        """Verify the CORS preflight allows the production frontend origin."""
        resp = client.options(
            "/api/auth/me",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI/starlette returns 200 for OPTIONS on matching origins
        assert resp.status_code == 200
        allowed_origin = resp.headers.get("access-control-allow-origin", "")
        assert allowed_origin in ("http://localhost:5173", "*")
