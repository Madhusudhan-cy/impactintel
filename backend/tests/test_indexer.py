from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import Repository, CommitIndex, GraphNodeRecord, GraphEdgeRecord
from app.services.indexer import RepositoryIndexer


@pytest.fixture
def db_session():
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


def test_indexer_indexes_sample_repository(db_session, repo_root):
    indexer = RepositoryIndexer()
    commit_index = indexer.index_directory(
        db=db_session,
        full_name="org/sample-repo",
        directory_path=repo_root,
        branch="main",
        commit_sha="a1b2c3d4e5f6"
    )

    assert commit_index.id is not None
    assert commit_index.status == "INDEXED"
    assert commit_index.total_nodes >= 15
    assert commit_index.total_edges >= 13

    # Verify repository was created
    repo = db_session.query(Repository).filter(Repository.full_name == "org/sample-repo").first()
    assert repo is not None
    assert repo.default_branch == "main"

    # Verify nodes and edges in database
    node_count = db_session.query(GraphNodeRecord).filter(GraphNodeRecord.commit_index_id == commit_index.id).count()
    edge_count = db_session.query(GraphEdgeRecord).filter(GraphEdgeRecord.commit_index_id == commit_index.id).count()
    assert node_count >= 15
    assert edge_count >= 13


def test_indexer_non_existent_directory(db_session):
    indexer = RepositoryIndexer()
    with pytest.raises(FileNotFoundError):
        indexer.index_directory(
            db=db_session,
            full_name="org/non-existent",
            directory_path=Path("/tmp/non_existent_dir_99999")
        )
