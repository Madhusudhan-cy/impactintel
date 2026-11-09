from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON, Text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from app.db.session import Base

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class VectorType(TypeDecorator):
    """
    Dual-engine vector type:
    Uses pgvector's Vector(dim) when executing against PostgreSQL,
    and falls back to JSON when executing on SQLite / in-memory test databases.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 384, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and HAS_PGVECTOR:
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    full_name = Column(String(255), unique=True, index=True, nullable=False)  # e.g., "owner/repo"
    owner = Column(String(255), nullable=False)
    default_branch = Column(String(100), default="main", nullable=False)
    installation_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    commit_indices = relationship("CommitIndex", back_populates="repository", cascade="all, delete-orphan")
    pr_analyses = relationship("PullRequestAnalysisRecord", back_populates="repository", cascade="all, delete-orphan")
    chunks = relationship("CodeChunkRecord", back_populates="repository", cascade="all, delete-orphan")
    conversations = relationship("ConversationRecord", back_populates="repository", cascade="all, delete-orphan")


class CommitIndex(Base):
    __tablename__ = "commit_indices"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    branch = Column(String(100), nullable=False)
    commit_sha = Column(String(64), index=True, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, INDEXING, INDEXED, FAILED
    total_nodes = Column(Integer, default=0, nullable=False)
    total_edges = Column(Integer, default=0, nullable=False)
    indexed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="commit_indices")
    nodes = relationship("GraphNodeRecord", back_populates="commit_index", cascade="all, delete-orphan")
    edges = relationship("GraphEdgeRecord", back_populates="commit_index", cascade="all, delete-orphan")


class GraphNodeRecord(Base):
    __tablename__ = "graph_nodes"

    id = Column(Integer, primary_key=True, index=True)
    commit_index_id = Column(Integer, ForeignKey("commit_indices.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(512), index=True, nullable=False)  # repo-relative path or symbol ID
    node_type = Column(String(50), default="File", nullable=False)  # File, Function, Class, Component, ApiRoute, Test
    language = Column(String(50), default="javascript", nullable=False)
    meta_data = Column(JSON, default=dict, nullable=False)

    commit_index = relationship("CommitIndex", back_populates="nodes")


class GraphEdgeRecord(Base):
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, index=True)
    commit_index_id = Column(Integer, ForeignKey("commit_indices.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(512), index=True, nullable=False)  # Dependent / caller
    target = Column(String(512), index=True, nullable=False)  # Dependency / callee
    edge_type = Column(String(50), default="imports", nullable=False)
    file = Column(String(512), nullable=False)
    line = Column(Integer, nullable=True)
    statement = Column(String(1024), nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    extractor = Column(String(50), default="tree_sitter", nullable=False)
    evidence = Column(JSON, default=list, nullable=False)

    commit_index = relationship("CommitIndex", back_populates="edges")


class PullRequestAnalysisRecord(Base):
    __tablename__ = "pr_analyses"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pr_number = Column(Integer, index=True, nullable=False)
    pr_title = Column(String(512), default="", nullable=False)
    base_branch = Column(String(100), nullable=False)
    base_commit_sha = Column(String(64), nullable=False)
    head_commit_sha = Column(String(64), nullable=False)
    status = Column(String(50), default="COMPLETED", nullable=False)  # ANALYZING, COMPLETED, FAILED
    total_affected = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="pr_analyses")
    impact_report = relationship("ImpactReportRecord", back_populates="pr_analysis", uselist=False, cascade="all, delete-orphan")


class ImpactReportRecord(Base):
    __tablename__ = "impact_reports"

    id = Column(Integer, primary_key=True, index=True)
    pr_analysis_id = Column(Integer, ForeignKey("pr_analyses.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    changed_files = Column(JSON, default=list, nullable=False)
    affected_components = Column(JSON, default=list, nullable=False)
    unaffected_files = Column(JSON, default=list, nullable=False)
    unmapped_files = Column(JSON, default=list, nullable=False)
    total_affected = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pr_analysis = relationship("PullRequestAnalysisRecord", back_populates="impact_report")


class CodeChunkRecord(Base):
    """Stores indexed code chunks with metadata and embedding vectors."""
    __tablename__ = "code_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String(64), unique=True, index=True, nullable=False)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(512), index=True, nullable=False)
    language = Column(String(50), nullable=False)
    symbol_name = Column(String(255), nullable=True, index=True)
    symbol_type = Column(String(50), default="File", nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    commit_sha = Column(String(64), index=True, nullable=False)
    associated_node_id = Column(String(512), nullable=True, index=True)
    parent_file = Column(String(512), nullable=False)
    imports = Column(JSON, default=list, nullable=False)
    embedding_model = Column(String(100), default="deterministic-hash-384", nullable=False)
    embedding = Column(VectorType(384), nullable=True)  # Vector representation (vector(384) in PostgreSQL, JSON in SQLite)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="chunks")


class ConversationRecord(Base):
    """Stores conversation history scoped to repository."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), unique=True, index=True, nullable=False)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    messages = Column(JSON, default=list, nullable=False)  # [{"role": "user"|"assistant", "content": "..."}]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    repository = relationship("Repository", back_populates="conversations")
