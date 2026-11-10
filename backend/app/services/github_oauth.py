import hashlib
import hmac as hmac_lib
import secrets
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
import jwt
import httpx
import logging

from app.core.config import (
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_OAUTH_REDIRECT_URI,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    SESSION_EXPIRE_HOURS,
    GITHUB_API_BASE_URL,
    ALLOW_DEV_BYPASS
)

logger = logging.getLogger(__name__)


class GitHubOAuthService:
    """
    Handles GitHub OAuth App authentication flow:
    - Authorization URL generation with CSRF state
    - Authorization code exchange for OAuth access token
    - Authenticated user profile retrieval
    - Accessible user repository listing
    - Signed JWT application session management
    - Offline local developer mode fallback
    """

    @staticmethod
    def generate_oauth_state() -> str:
        """Generate a self-validating HMAC-signed OAuth state token for CSRF protection."""
        nonce = secrets.token_urlsafe(24)
        mac = hmac_lib.new(JWT_SECRET_KEY.encode(), nonce.encode(), hashlib.sha256).hexdigest()[:16]
        return f"{nonce}.{mac}"

    @staticmethod
    def validate_oauth_state(state: Optional[str]) -> bool:
        """Validate OAuth state token HMAC signature."""
        if not state or "." not in state:
            return False
        try:
            nonce, received_mac = state.rsplit(".", 1)
            expected_mac = hmac_lib.new(JWT_SECRET_KEY.encode(), nonce.encode(), hashlib.sha256).hexdigest()[:16]
            return hmac_lib.compare_digest(expected_mac, received_mac)
        except Exception:
            return False

    @staticmethod
    def get_authorization_url(state: str) -> str:
        """Generate GitHub App user authorization URL with properly URL-encoded parameters.

        Note: The ``scope`` parameter is intentionally omitted.  This application
        uses a **GitHub App** (client_id prefix ``Iv23``), and GitHub Apps do not
        support dynamic OAuth scope parameters in the authorization URL.  Permissions
        are configured statically in the GitHub App settings dashboard.  Passing
        ``scope`` to a GitHub App authorization URL causes GitHub to return a 404.
        """
        if not GITHUB_CLIENT_ID:
            if ALLOW_DEV_BYPASS:
                # Dev fallback redirect
                return f"/auth/callback?{urlencode({'code': 'mock_dev_code', 'state': state})}"
            raise ValueError("GITHUB_CLIENT_ID is not configured. Cannot generate authorization URL.")

        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_OAUTH_REDIRECT_URI,
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    @staticmethod
    def exchange_code_for_token(code: str) -> Optional[str]:
        """Exchange OAuth authorization code for GitHub access token."""
        if ALLOW_DEV_BYPASS and (code.startswith("mock_dev_code") or not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET):
            return "mock_oauth_token_dev"
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            return None

        url = "https://github.com/login/oauth/access_token"
        headers = {"Accept": "application/json"}
        payload = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_OAUTH_REDIRECT_URI
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                return data.get("access_token")
        except Exception as e:
            logger.error(f"Failed to exchange GitHub OAuth code: {e}")
            return None

    @staticmethod
    def get_user_profile(access_token: str) -> Dict[str, Any]:
        """Retrieve the authenticated GitHub user's profile."""
        if ALLOW_DEV_BYPASS and access_token.startswith("mock_oauth_token"):
            return {
                "id": 1001,
                "login": "dev-user",
                "name": "Local Developer",
                "email": "dev@localhost",
                "avatar_url": "https://avatars.githubusercontent.com/u/583231",
                "html_url": "https://github.com",
                "bio": "Developer testing AI Repository Impact Intelligence"
            }

        url = f"{GITHUB_API_BASE_URL}/user"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=headers)
                res.raise_for_status()
                data = res.json()
                return {
                    "id": data.get("id"),
                    "login": data.get("login"),
                    "name": data.get("name") or data.get("login"),
                    "email": data.get("email"),
                    "avatar_url": data.get("avatar_url"),
                    "html_url": data.get("html_url"),
                    "bio": data.get("bio")
                }
        except Exception as e:
            logger.error(f"Failed to fetch GitHub user profile: {e}")
            raise

    @staticmethod
    def get_user_repositories(access_token: str) -> List[Dict[str, Any]]:
        """Retrieve repositories accessible through the user's OAuth authorization."""
        if ALLOW_DEV_BYPASS and access_token.startswith("mock_oauth_token"):
            return [
                {
                    "id": 1,
                    "name": "shop-repo",
                    "full_name": "org/shop-repo",
                    "owner": "org",
                    "description": "Multi-tier sample e-commerce application (React + Express/FastAPI)",
                    "default_branch": "main",
                    "private": False,
                    "language": "JavaScript",
                    "languages": ["JavaScript", "Python"],
                    "updated_at": "2026-11-09T08:00:00Z",
                    "indexed": True
                }
            ]

        url = f"{GITHUB_API_BASE_URL}/user/repos?per_page=100&sort=updated"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=headers)
                res.raise_for_status()
                repos = res.json()
                results = []
                for r in repos:
                    results.append({
                        "id": r.get("id"),
                        "name": r.get("name"),
                        "full_name": r.get("full_name"),
                        "owner": r.get("owner", {}).get("login"),
                        "description": r.get("description") or "",
                        "default_branch": r.get("default_branch", "main"),
                        "private": r.get("private", False),
                        "language": r.get("language") or "Other",
                        "updated_at": r.get("updated_at")
                    })
                return results
        except Exception as e:
            logger.error(f"Failed to fetch user repositories: {e}")
            return []

    @staticmethod
    def create_session_jwt(user: Dict[str, Any], access_token: str) -> str:
        """Create signed JWT session token."""
        exp = int(time.time()) + (SESSION_EXPIRE_HOURS * 3600)
        payload = {
            "sub": str(user.get("id", user.get("login"))),
            "user": user,
            "access_token": access_token,
            "exp": exp
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_session_jwt(token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate session JWT token."""
        try:
            return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except Exception:
            return None
