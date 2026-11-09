import re
from typing import List, Tuple, Optional, Dict
from rank_bm25 import BM25Okapi

from app.rag.chunker import CodeChunk


def tokenize_code(text: str) -> List[str]:
    """
    Code-aware tokenizer for BM25 keyword search.
    Preserves exact tokens while extracting camelCase and snake_case sub-identifiers.
    """
    tokens = []
    raw_tokens = re.findall(r"[a-zA-Z0-9_]+", text)
    for tok in raw_tokens:
        tok_lower = tok.lower()
        tokens.append(tok_lower)

        # Snake_case splitting
        if "_" in tok:
            for part in tok.split("_"):
                if part:
                    tokens.append(part.lower())

        # CamelCase splitting
        camel_parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z0-9]|\b)", tok)
        if len(camel_parts) > 1:
            for part in camel_parts:
                tokens.append(part.lower())

    return tokens


class BM25Retriever:
    """
    BM25 keyword search engine for code chunks.
    Indexed chunks are scoped to repository_id and ranked using BM25Okapi.
    """

    def __init__(self, chunks: Optional[List[CodeChunk]] = None):
        self.chunks: List[CodeChunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self._corpus_tokens: List[List[str]] = []
        if chunks:
            self.index_chunks(chunks)

    def index_chunks(self, chunks: List[CodeChunk]) -> None:
        """Build the BM25 search index over a collection of CodeChunk instances."""
        self.chunks = list(chunks)
        self._corpus_tokens = []
        for chunk in self.chunks:
            # Combine content, file_path, and symbol_name for rich keyword indexing
            full_text = f"{chunk.file_path} {chunk.symbol_name or ''} {chunk.content}"
            tokens = tokenize_code(full_text)
            self._corpus_tokens.append(tokens)

        if self._corpus_tokens:
            self.bm25 = BM25Okapi(self._corpus_tokens)
        else:
            self.bm25 = None

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        repository_id: Optional[int] = None
    ) -> List[Tuple[CodeChunk, float]]:
        """
        Search code chunks using BM25, returning top_k results with scores.
        """
        if not self.bm25 or not self.chunks:
            return []

        query_tokens = tokenize_code(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Pair chunks with scores
        scored_chunks = []
        for idx, score in enumerate(scores):
            if score <= 0.0:
                continue
            chunk = self.chunks[idx]
            if repository_id is not None and chunk.repository_id != repository_id:
                continue
            scored_chunks.append((chunk, float(score)))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]
