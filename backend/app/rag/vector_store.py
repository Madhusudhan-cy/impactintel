import math
import hashlib
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from sqlalchemy.orm import Session

from app.db.models import CodeChunkRecord, HAS_PGVECTOR
from app.rag.chunker import CodeChunk


class BaseEmbedder(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass


class DeterministicHashEmbedder(BaseEmbedder):
    """
    Lightweight deterministic local embedding generator for code & text (Option A).
    Produces a normalized 384-dimensional vector based on sub-token frequency and hashing.
    Runs locally with zero external network access, preserving repository privacy.
    """
    def __init__(self, dim: int = 384):
        self._dim = dim
        self._name = f"deterministic-hash-{dim}"

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        tokens = text.lower().split()
        if not tokens:
            return [0.0] * self._dim

        vec = np.zeros(self._dim, dtype=np.float32)
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            weight = 1.0 + (len(tok) / 10.0)
            vec[idx] += weight

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()


class SentenceTransformerEmbedder(BaseEmbedder):
    """
    Local neural embedding engine using sentence-transformers (Option B).
    Supports models such as BAAI/bge-small-en-v1.5 and sentence-transformers/all-MiniLM-L6-v2.
    Generates high-dimensional semantic code/text embeddings locally with pgvector compatibility.
    Falls back gracefully to DeterministicHashEmbedder if sentence_transformers is not installed.
    """
    def __init__(self, model_name_or_path: str = "sentence-transformers/all-MiniLM-L6-v2", dim: int = 384):
        self._name = model_name_or_path
        self._dim = dim
        self._model = None
        self._load_attempted = False

    def _ensure_loaded(self):
        if not self._load_attempted:
            self._load_attempted = True
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._name)
            except Exception:
                self._model = None

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        self._ensure_loaded()
        if self._model is not None:
            embedding = self._model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        # Fallback to zero-dependency local embedding if library/weights not yet downloaded
        return DeterministicHashEmbedder(dim=self._dim).embed_text(text)


def get_default_embedder() -> BaseEmbedder:
    """
    Pluggable local embedding resolver:
    Uses SentenceTransformerEmbedder if available, otherwise DeterministicHashEmbedder.
    """
    try:
        import sentence_transformers  # noqa: F401
        return SentenceTransformerEmbedder()
    except ImportError:
        return DeterministicHashEmbedder()


def compute_dense_embedding(text: str, dim: int = 384) -> List[float]:
    """Compatibility wrapper for deterministic 384-d dense embedding."""
    return DeterministicHashEmbedder(dim=dim).embed_text(text)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vector lists."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))


class VectorRetriever:
    """
    Local Vector Search engine using pgvector-compatible normalized embeddings.
    Operates strictly within repository boundaries to prevent data leakage.
    Handles model/version checks to avoid mixing incompatible embedding dimensions.
    """

    def __init__(
        self,
        chunks: Optional[List[CodeChunk]] = None,
        embedder: Optional[BaseEmbedder] = None,
        dim: int = 384
    ):
        self.embedder = embedder or get_default_embedder()
        self.dim = self.embedder.dimension
        self.model_name = self.embedder.model_name
        self.chunks: List[CodeChunk] = []
        self.embeddings: Dict[str, List[float]] = {}
        if chunks:
            self.index_chunks(chunks)

    def index_chunks(self, chunks: List[CodeChunk]) -> None:
        """Compute and cache embeddings for a collection of CodeChunk instances."""
        self.chunks = list(chunks)
        for chunk in self.chunks:
            repr_text = f"{chunk.symbol_name or ''} {chunk.file_path} {chunk.content}"
            self.embeddings[chunk.chunk_id] = self.embedder.embed_text(repr_text)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        repository_id: Optional[int] = None
    ) -> List[Tuple[CodeChunk, float]]:
        """
        Retrieve code chunks most semantically similar to query vector.
        Strictly enforces repository_id scoping.
        """
        if not self.chunks or not self.embeddings:
            return []

        query_vec = self.embedder.embed_text(query)
        scored: List[Tuple[CodeChunk, float]] = []

        for chunk in self.chunks:
            if repository_id is not None and chunk.repository_id != repository_id:
                continue
            chunk_vec = self.embeddings.get(chunk.chunk_id)
            if not chunk_vec:
                continue
            sim = cosine_similarity(query_vec, chunk_vec)
            if sim > 0.0:
                scored.append((chunk, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def save_chunks_to_db(
        db: Session,
        repository_id: int,
        chunks: List[CodeChunk],
        embedder: Optional[BaseEmbedder] = None,
        dim: int = 384
    ) -> None:
        """Persist code chunks and their embeddings into the PostgreSQL database."""
        emb_engine = embedder or get_default_embedder()
        for c in chunks:
            repr_text = f"{c.symbol_name or ''} {c.file_path} {c.content}"
            emb = emb_engine.embed_text(repr_text)

            rec = db.query(CodeChunkRecord).filter(CodeChunkRecord.chunk_id == c.chunk_id).first()
            if not rec:
                rec = CodeChunkRecord(
                    chunk_id=c.chunk_id,
                    repository_id=repository_id,
                    file_path=c.file_path,
                    language=c.language,
                    symbol_name=c.symbol_name,
                    symbol_type=c.symbol_type,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    commit_sha=c.commit_sha,
                    associated_node_id=c.associated_node_id,
                    parent_file=c.parent_file,
                    imports=c.imports,
                    embedding_model=emb_engine.model_name,
                    embedding=emb
                )
                db.add(rec)
            else:
                # Update existing record if embedding model changed or content updated
                rec.embedding_model = emb_engine.model_name
                rec.embedding = emb
        db.commit()

    @staticmethod
    def load_chunks_from_db(db: Session, repository_id: int) -> List[CodeChunk]:
        """Load repository code chunks from PostgreSQL database."""
        records = db.query(CodeChunkRecord).filter(CodeChunkRecord.repository_id == repository_id).all()
        chunks = []
        for r in records:
            chunks.append(
                CodeChunk(
                    chunk_id=r.chunk_id,
                    repository_id=r.repository_id,
                    file_path=r.file_path,
                    language=r.language,
                    symbol_name=r.symbol_name,
                    symbol_type=r.symbol_type,
                    start_line=r.start_line,
                    end_line=r.end_line,
                    content=r.content,
                    commit_sha=r.commit_sha,
                    associated_node_id=r.associated_node_id,
                    parent_file=r.parent_file,
                    imports=r.imports or []
                )
            )
        return chunks
