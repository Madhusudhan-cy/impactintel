from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import Repository, CommitIndex, GraphNodeRecord, GraphEdgeRecord
from app.db.repository_store import RepositoryStore
from app.extractors.javascript.parser import JavaScriptExtractor
from app.graph.builder import CodeKnowledgeGraph
from app.impact.engine import find_affected_components


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


def test_repository_store_crud(in_memory_db):
    repo = RepositoryStore.get_or_create_repository(
        in_memory_db,
        full_name="acme/payment-service",
        default_branch="main",
        installation_id=12345
    )
    assert repo.id is not None
    assert repo.full_name == "acme/payment-service"
    assert repo.owner == "acme"
    assert repo.name == "payment-service"
    assert repo.installation_id == 12345


def test_save_and_reconstruct_graph_from_db(in_memory_db, repo_root):
    # 1. Extract from sample-repository
    extractor = JavaScriptExtractor()
    nodes, edges, _ = extractor.extract_repository(repo_root)
    original_ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)

    # 2. Persist to database
    repo = RepositoryStore.get_or_create_repository(in_memory_db, "acme/sample-repo")
    commit_sha = "c0ffee123456"
    commit_index = RepositoryStore.save_graph(
        db=in_memory_db,
        repository_id=repo.id,
        branch="main",
        commit_sha=commit_sha,
        ckg=original_ckg
    )

    assert commit_index.id is not None
    assert commit_index.total_nodes == original_ckg.node_count
    assert commit_index.total_edges == original_ckg.edge_count
    assert commit_index.status == "INDEXED"

    # Verify rows in DB
    node_rows = in_memory_db.query(GraphNodeRecord).filter(GraphNodeRecord.commit_index_id == commit_index.id).all()
    edge_rows = in_memory_db.query(GraphEdgeRecord).filter(GraphEdgeRecord.commit_index_id == commit_index.id).all()
    assert len(node_rows) == original_ckg.node_count
    assert len(edge_rows) == original_ckg.edge_count

    # 3. Reconstruct CodeKnowledgeGraph from database
    reconstructed_ckg, loaded_index = RepositoryStore.load_graph(
        db=in_memory_db,
        repository_id=repo.id,
        commit_sha=commit_sha
    )
    assert reconstructed_ckg is not None
    assert loaded_index.commit_sha == commit_sha
    assert reconstructed_ckg.node_count == original_ckg.node_count
    assert reconstructed_ckg.edge_count == original_ckg.edge_count

    # 4. Verify reverse dependency impact analysis on DB-reconstructed graph
    report = find_affected_components(reconstructed_ckg, ["src/database/database.js"])
    affected_files = [c.file_path for c in report.affected_components]

    assert "src/services/paymentService.js" in affected_files
    assert "src/routes/paymentRoutes.js" in affected_files
    assert "src/app.js" in affected_files
    assert "src/utils/logger.js" not in affected_files
