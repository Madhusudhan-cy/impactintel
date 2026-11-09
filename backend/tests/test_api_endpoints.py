import hmac
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.app import app
from app.db.session import Base, get_db


@pytest.fixture
def test_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


def test_healthcheck(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_invalid_signature(client):
    payload = json.dumps({"zen": "Keep it logically awesome."}).encode("utf-8")
    headers = {
        "X-GitHub-Event": "ping",
        "X-Hub-Signature-256": "sha256=invalid_hash_value_here",
        "Content-Type": "application/json"
    }
    import app.api.routes as routes
    original_secret = routes.GITHUB_WEBHOOK_SECRET
    routes.GITHUB_WEBHOOK_SECRET = "super_secret_test_key"
    try:
        response = client.post("/api/webhooks/github", content=payload, headers=headers)
        assert response.status_code == 401
    finally:
        routes.GITHUB_WEBHOOK_SECRET = original_secret


def test_webhook_ping_valid_signature(client):
    payload_dict = {"zen": "Mind your craft."}
    payload_bytes = json.dumps(payload_dict).encode("utf-8")

    import app.api.routes as routes
    secret = "test_key_123"
    routes.GITHUB_WEBHOOK_SECRET = secret

    try:
        sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        headers = {
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": f"sha256={sig}",
            "X-GitHub-Delivery": "delivery-uuid-001",
            "Content-Type": "application/json"
        }
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "pong", "zen": "Mind your craft."}

        # Test duplicate delivery deduplication
        response_dup = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)
        assert response_dup.status_code == 200
        assert response_dup.json()["status"] == "ignored"
    finally:
        routes.GITHUB_WEBHOOK_SECRET = "dev_webhook_secret"


def test_end_to_end_manual_pr_analysis_and_history(client, test_db_session, repo_root):
    # 1. Index sample repository via API
    index_res = client.post(
        "/api/repos/testorg/sample-repo/index",
        json={
            "directory_path": str(repo_root),
            "branch": "main",
            "commit_sha": "c0ffee112233"
        }
    )
    assert index_res.status_code == 200
    assert index_res.json()["status"] == "INDEXED"
    assert index_res.json()["total_nodes"] >= 15
    assert index_res.json()["total_edges"] >= 13

    # 2. Check indexing status endpoint
    status_res = client.get("/api/repos/testorg/sample-repo/index/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "INDEXED"
    assert status_res.json()["commit_sha"] == "c0ffee112233"

    # 3. Perform manual PR analysis on modified database.js and unmapped README.md
    analysis_res = client.post(
        "/api/repos/testorg/sample-repo/pulls/42/analyze",
        json={
            "pr_title": "Fix connection pool in database.js",
            "base_branch": "main",
            "base_commit_sha": "c0ffee112233",
            "head_commit_sha": "f00baa445566",
            "changed_files": [
                {"filename": "src/database/database.js", "status": "modified"},
                {"filename": "README.md", "status": "modified"}  # Non-graph file
            ]
        }
    )
    assert analysis_res.status_code == 200
    data = analysis_res.json()

    assert data["pr_number"] == 42
    assert data["status"] == "COMPLETED"
    assert data["total_affected"] == 7  # Level 1 (2), Level 2 (3), Level 3 (2)

    affected_paths = [c["file_path"] for c in data["affected_components"]]
    assert "src/services/paymentService.js" in affected_paths
    assert "src/routes/paymentRoutes.js" in affected_paths
    assert "src/app.js" in affected_paths
    assert "src/utils/logger.js" not in affected_paths

    # Verify unmapped files
    assert any("README.md" in u for u in data["unmapped_files"])

    # 4. Check PR analyses history list
    list_res = client.get("/api/repos/testorg/sample-repo/pulls")
    assert list_res.status_code == 200
    pr_list = list_res.json()
    assert len(pr_list) == 1
    assert pr_list[0]["pr_number"] == 42
    assert pr_list[0]["total_affected"] == 7

    # 5. Check specific PR analysis retrieval
    get_res = client.get("/api/repos/testorg/sample-repo/pulls/42")
    assert get_res.status_code == 200
    pr_detail = get_res.json()
    assert pr_detail["pr_number"] == 42
    assert pr_detail["report"]["total_affected"] == 7
    assert len(pr_detail["report"]["affected_components"]) == 7


def test_github_oauth_and_graph_explorer(client, test_db_session, repo_root):
    # 1. Auth URL generation
    auth_url_res = client.get("/api/auth/github/url")
    assert auth_url_res.status_code == 200
    assert "url" in auth_url_res.json()
    assert "state" in auth_url_res.json()

    # 2. Auth me endpoint
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["authenticated"] is True
    assert "user" in me_res.json()

    # 3. Index sample repo
    idx_res = client.post(
        "/api/repos/testorg/sample-repo/index",
        json={"directory_path": str(repo_root), "branch": "main"}
    )
    assert idx_res.status_code == 200

    # 4. List repositories
    repos_res = client.get("/api/repos")
    assert repos_res.status_code == 200
    repos = repos_res.json()
    assert any("sample-repo" in r["full_name"] for r in repos)

    # 5. Graph summary
    graph_res = client.get("/api/repos/testorg/sample-repo/graph/summary")
    assert graph_res.status_code == 200
    assert graph_res.json()["total_nodes"] > 10

    # 6. Graph search
    search_res = client.get("/api/repos/testorg/sample-repo/graph/nodes?q=processPayment")
    assert search_res.status_code == 200
    assert search_res.json()["count"] >= 1

    # 7. Graph neighbors for React Flow
    neighbors_res = client.get("/api/repos/testorg/sample-repo/graph/neighbors")
    assert neighbors_res.status_code == 200
    data = neighbors_res.json()
    assert len(data["nodes"]) > 0
    assert "center_node_id" in data
