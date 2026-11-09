import logging
from pathlib import Path
from typing import Optional, Union, Any
from sqlalchemy.orm import Session

from app.db.models import Repository, CommitIndex
from app.db.repository_store import RepositoryStore
from app.extractors.unified import MultiLanguageExtractor
from app.graph.builder import CodeKnowledgeGraph

logger = logging.getLogger(__name__)


class RepositoryIndexer:
    """
    Orchestrates repository indexing by employing multi-language AST extraction
    (JavaScript/TypeScript/React and Python) and NetworkX graph construction,
    persisting the resulting fine-grained Code Knowledge Graph into PostgreSQL.
    """

    def __init__(self, extractor: Optional[Any] = None):
        self.extractor = extractor or MultiLanguageExtractor()

    def index_directory(
        self,
        db: Session,
        full_name: str,
        directory_path: Path,
        branch: str = "main",
        commit_sha: str = "HEAD",
        installation_id: Optional[int] = None
    ) -> CommitIndex:
        """
        Index a local repository directory, extract all fine-grained symbols,
        calls, rendering relationships, and routes, and persist to PostgreSQL.
        """
        directory_path = Path(directory_path).resolve()
        if not directory_path.is_dir():
            raise FileNotFoundError(f"Repository directory does not exist: {directory_path}")

        # 1. Ensure repository record exists in DB
        repo = RepositoryStore.get_or_create_repository(
            db=db,
            full_name=full_name,
            default_branch=branch,
            installation_id=installation_id
        )

        # 2. Extract using MultiLanguageExtractor
        nodes, edges, all_imports = self.extractor.extract_repository(directory_path)

        # 3. Assemble NetworkX Code Knowledge Graph
        ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)

        # 4. Persist to PostgreSQL via RepositoryStore
        commit_index = RepositoryStore.save_graph(
            db=db,
            repository_id=repo.id,
            branch=branch,
            commit_sha=commit_sha,
            ckg=ckg,
            status="INDEXED"
        )

        return commit_index
