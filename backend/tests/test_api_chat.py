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


def test_api_chat_flow(client, test_db_session, repo_root):
    # 1. Index sample repository
    index_res = client.post(
        "/api/repos/org/shop-repo/index",
        json={"directory_path": str(repo_root), "branch": "main"}
    )
    assert index_res.status_code == 200

    # 2. Ask question via Chat API
    chat_res = client.post(
        "/api/repos/org/shop-repo/chat",
        json={"query": "What does processPayment do?"}
    )
    assert chat_res.status_code == 200
    data = chat_res.json()

    assert "conversation_id" in data
    assert "answer" in data
    assert data["is_verified"] is True
    cid = data["conversation_id"]

    # 3. Ask follow-up question
    followup_res = client.post(
        "/api/repos/org/shop-repo/chat",
        json={"query": "What does the first one do?", "conversation_id": cid}
    )
    assert followup_res.status_code == 200
    f_data = followup_res.json()
    assert f_data["conversation_id"] == cid

    # 4. Retrieve conversation message history
    history_res = client.get(f"/api/repos/org/shop-repo/chat/{cid}")
    assert history_res.status_code == 200
    hist = history_res.json()
    assert hist["conversation_id"] == cid
    assert len(hist["messages"]) >= 4  # 2 user questions, 2 assistant answers
