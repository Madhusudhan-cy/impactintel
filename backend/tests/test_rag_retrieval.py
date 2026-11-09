from pathlib import Path
import pytest

from app.extractors.unified import MultiLanguageExtractor
from app.graph.builder import CodeKnowledgeGraph
from app.rag.chunker import CodeChunker
from app.rag.bm25 import BM25Retriever
from app.rag.graph_rag import GraphRAGRetriever
from app.rag.hybrid import HybridRetriever


@pytest.fixture(scope="module")
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


@pytest.fixture(scope="module")
def repo_data(repo_root):
    extractor = MultiLanguageExtractor()
    nodes, edges, imports = extractor.extract_repository(repo_root)
    ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)

    chunker = CodeChunker(extractor=extractor)
    chunks = chunker.chunk_repository(repo_root, repository_id=1, commit_sha="abc1234")

    bm25 = BM25Retriever(chunks)
    graph_rag = GraphRAGRetriever(ckg, chunks=chunks)
    hybrid = HybridRetriever(bm25_retriever=bm25, graph_rag_retriever=graph_rag)

    return {
        "ckg": ckg,
        "chunks": chunks,
        "bm25": bm25,
        "graph_rag": graph_rag,
        "hybrid": hybrid
    }


def test_code_chunking_boundaries(repo_data):
    chunks = repo_data["chunks"]
    assert len(chunks) > 15

    symbol_types = {c.symbol_type for c in chunks}
    assert "Function" in symbol_types
    assert "Class" in symbol_types
    assert "Component" in symbol_types
    assert "File" in symbol_types

    # Find processPayment chunk
    pay_chunk = next((c for c in chunks if c.symbol_name == "processPayment"), None)
    assert pay_chunk is not None
    assert pay_chunk.file_path == "src/services/paymentService.js"
    assert "dbConnection.query" in pay_chunk.content


def test_bm25_keyword_retrieval(repo_data):
    bm25 = repo_data["bm25"]
    results = bm25.retrieve("processPayment userId amount", top_k=3)
    assert len(results) > 0

    top_chunk, score = results[0]
    assert score > 0
    # Must retrieve paymentService or paymentRoutes
    assert "payment" in top_chunk.file_path.lower()


def test_graph_rag_structural_retrieval(repo_data):
    graph_rag = repo_data["graph_rag"]
    # Structural retrieval around processPayment
    items = graph_rag.retrieve_subgraph_context("src/services/paymentService.js::processPayment")
    assert len(items) > 0

    node_ids = {it.node_id for it in items}
    # Callers (predecessors)
    assert "src/routes/paymentRoutes.js::handlePaymentRequest" in node_ids
    assert "src/components/Checkout.jsx::handlePay" in node_ids

    # Downstream dependencies (successors)
    assert "src/database/database.js::query" in node_ids

    # Test relationship
    test_item = next((it for it in items if "test" in it.relation_type.lower()), None)
    assert test_item is not None
    assert test_item.direction == "test"


def test_graph_rag_react_component_renders(repo_data):
    graph_rag = repo_data["graph_rag"]
    items = graph_rag.retrieve_subgraph_context("src/components/PaymentForm.jsx::PaymentForm")
    node_ids = {it.node_id for it in items}
    # Checkout renders PaymentForm
    assert "src/components/Checkout.jsx::Checkout" in node_ids


def test_hybrid_rrf_retrieval(repo_data):
    hybrid = repo_data["hybrid"]
    query = "Where is processPayment called and what does it query?"
    fused = hybrid.retrieve(query, top_k=5)

    assert len(fused) > 0
    top = fused[0]
    assert top.rrf_score > 0
    # Verified multi-modal retrieval
    all_sources = set()
    for f in fused:
        all_sources.update(f.retrieval_sources)

    assert "bm25" in all_sources
    assert "graph_rag" in all_sources


def test_pluggable_embedders():
    from app.rag.vector_store import (
        DeterministicHashEmbedder,
        SentenceTransformerEmbedder,
        get_default_embedder
    )

    # Option A: Deterministic local hash embedder
    hash_emb = DeterministicHashEmbedder(dim=384)
    v1 = hash_emb.embed_text("function processPayment()")
    assert len(v1) == 384
    assert hash_emb.model_name == "deterministic-hash-384"

    # Option B: SentenceTransformerEmbedder with graceful local fallback
    st_emb = SentenceTransformerEmbedder(model_name_or_path="sentence-transformers/all-MiniLM-L6-v2", dim=384)
    v2 = st_emb.embed_text("function processPayment()")
    assert len(v2) == 384
    assert st_emb.dimension == 384

    # Pluggable default resolver
    default_emb = get_default_embedder()
    assert default_emb.dimension == 384
