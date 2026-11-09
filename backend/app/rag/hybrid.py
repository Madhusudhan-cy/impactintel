from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from pydantic import BaseModel, Field

from app.rag.chunker import CodeChunk
from app.rag.bm25 import BM25Retriever
from app.rag.graph_rag import GraphRAGRetriever, GraphContextItem


class FusedEvidence(BaseModel):
    """
    Combined evidence record produced by Reciprocal Rank Fusion (RRF)
    across Graph RAG, BM25, and Vector search.
    """
    chunk_id: str
    file_path: str
    language: str = "javascript"
    symbol_name: Optional[str] = None
    symbol_type: str = "File"
    start_line: int
    end_line: int
    content: str
    rrf_score: float
    retrieval_sources: List[str] = Field(default_factory=list)  # ["graph_rag", "bm25", "vector"]
    graph_context: Optional[Dict[str, Any]] = None


class HybridRetriever:
    """
    Coordinates multi-modal code retrieval combining:
        1. Graph RAG (structural callers, callees, renders, and tests)
        2. BM25 (exact keyword & identifier search)
        3. Vector Search (semantic similarity, when enabled)
    Fuses results using Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        graph_rag_retriever: GraphRAGRetriever,
        vector_retriever: Optional[Any] = None,
        reranker: Optional[Callable[[str, List[FusedEvidence]], List[FusedEvidence]]] = None,
        rrf_k: int = 60
    ):
        self.bm25 = bm25_retriever
        self.graph_rag = graph_rag_retriever
        self.vector = vector_retriever
        self.reranker = reranker
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        repository_id: Optional[int] = None
    ) -> List[FusedEvidence]:
        """
        Execute parallel hybrid retrieval across Graph RAG, BM25, and Vector search,
        then fuse rankings using Reciprocal Rank Fusion (RRF).
        """
        # 1. BM25 Keyword Search
        bm25_results: List[Tuple[CodeChunk, float]] = self.bm25.retrieve(
            query=query,
            top_k=top_k * 2,
            repository_id=repository_id
        )

        # 2. Graph RAG Structural Search
        graph_items: List[GraphContextItem] = self.graph_rag.retrieve(query=query)

        # 3. Vector Similarity Search (if configured)
        vector_results: List[Tuple[CodeChunk, float]] = []
        if self.vector:
            try:
                vector_results = self.vector.retrieve(query=query, top_k=top_k * 2, repository_id=repository_id)
            except Exception:
                vector_results = []

        # RRF Scoring Map: chunk_id -> dict
        chunk_map: Dict[str, CodeChunk] = {}
        source_map: Dict[str, Set[str]] = {}
        rrf_scores: Dict[str, float] = {}
        graph_meta: Dict[str, Dict[str, Any]] = {}

        # Fuse BM25 ranks
        for rank, (chunk, _) in enumerate(bm25_results, 1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            source_map.setdefault(cid, set()).add("bm25")
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (self.rrf_k + rank)

        # Fuse Graph RAG ranks
        for rank, g_item in enumerate(graph_items, 1):
            if g_item.chunk:
                cid = g_item.chunk.chunk_id
                chunk_map[cid] = g_item.chunk
                source_map.setdefault(cid, set()).add("graph_rag")
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (self.rrf_k + rank)
                graph_meta[cid] = g_item.to_dict()

        # Fuse Vector Search ranks
        for rank, (chunk, _) in enumerate(vector_results, 1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            source_map.setdefault(cid, set()).add("vector")
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (self.rrf_k + rank)

        # Query Intent-aware ranking adjustments:
        from app.rag.bm25 import tokenize_code
        query_tokens = set(tokenize_code(query.lower()))

        # 1. Definition Intent: Prioritize exact symbol definition chunk over call sites/tests
        is_def_query = bool({"defined", "definition", "where", "declare", "declaration"}.intersection(query_tokens))
        if is_def_query:
            for cid, chunk in chunk_map.items():
                if chunk.symbol_name and chunk.symbol_name.lower() in query_tokens and chunk.symbol_type != "File":
                    rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 0.1

        # 2. API Route Intent: Prioritize route declaration files and handlers
        is_route_query = bool({"route", "routes", "api", "endpoint", "post", "get", "put", "delete"}.intersection(query_tokens))
        if is_route_query:
            for cid, chunk in chunk_map.items():
                if "route" in chunk.file_path.lower() or chunk.symbol_type == "ApiRoute":
                    rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 0.05

        # Sort chunks by fused RRF score
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        fused_evidence: List[FusedEvidence] = []
        for cid in sorted_chunk_ids[:top_k]:
            c = chunk_map[cid]
            fused_evidence.append(
                FusedEvidence(
                    chunk_id=c.chunk_id,
                    file_path=c.file_path,
                    language=c.language,
                    symbol_name=c.symbol_name,
                    symbol_type=c.symbol_type,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    rrf_score=round(rrf_scores[cid], 6),
                    retrieval_sources=sorted(list(source_map.get(cid, []))),
                    graph_context=graph_meta.get(cid)
                )
            )

        # Optional Reranking stage if configured
        if self.reranker:
            try:
                fused_evidence = self.reranker(query, fused_evidence)
            except Exception:
                pass

        return fused_evidence[:top_k]
