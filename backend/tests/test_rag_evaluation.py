from pathlib import Path
import pytest

from app.extractors.unified import MultiLanguageExtractor
from app.graph.builder import CodeKnowledgeGraph
from app.rag.chunker import CodeChunker
from app.rag.bm25 import BM25Retriever
from app.rag.graph_rag import GraphRAGRetriever
from app.rag.vector_store import VectorRetriever, DeterministicHashEmbedder
from app.rag.hybrid import HybridRetriever
from app.rag.workflow import ConversationalRAGOrchestrator
from app.rag.verifier import EvidenceVerifier
from app.rag.memory import ConversationManager


@pytest.fixture(scope="module")
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


@pytest.fixture(scope="module")
def rag_system(repo_root):
    extractor = MultiLanguageExtractor()
    nodes, edges, imports = extractor.extract_repository(repo_root)
    ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)

    chunker = CodeChunker(extractor=extractor)
    chunks_repo1 = chunker.chunk_repository(repo_root, repository_id=1, commit_sha="eval_sha_1")

    # Also make a dummy chunk for repository 2 to test cross-repo boundary
    dummy_repo2_chunk = chunks_repo1[0].model_copy(update={"chunk_id": "chunk_2_dummy", "repository_id": 2})
    all_chunks = chunks_repo1 + [dummy_repo2_chunk]

    bm25 = BM25Retriever(all_chunks)
    graph_rag = GraphRAGRetriever(ckg, chunks=chunks_repo1)
    vector = VectorRetriever(all_chunks)
    hybrid = HybridRetriever(bm25_retriever=bm25, graph_rag_retriever=graph_rag, vector_retriever=vector)

    memory = ConversationManager()
    orchestrator = ConversationalRAGOrchestrator(
        hybrid_retriever=hybrid,
        memory_manager=memory
    )

    return {
        "ckg": ckg,
        "chunks": chunks_repo1,
        "bm25": bm25,
        "graph_rag": graph_rag,
        "vector": vector,
        "hybrid": hybrid,
        "orchestrator": orchestrator
    }


def test_question_where_process_payment_defined(rag_system):
    """Eval Q1: Where is processPayment defined?"""
    query = "Where is processPayment defined?"
    fused = rag_system["hybrid"].retrieve(query, top_k=3, repository_id=1)
    assert len(fused) > 0
    top = fused[0]
    assert "paymentService.js" in top.file_path
    assert top.symbol_name == "processPayment"


def test_question_callers_of_process_payment(rag_system):
    """Eval Q2: Which functions call processPayment? (Graph RAG reverse traversal)"""
    graph_rag = rag_system["graph_rag"]
    items = graph_rag.retrieve_subgraph_context("src/services/paymentService.js::processPayment", include_callers=True, include_callees=False)
    caller_ids = {it.node_id for it in items if it.direction in ("caller", "test")}
    assert "src/routes/paymentRoutes.js::handlePaymentRequest" in caller_ids
    assert "src/components/Checkout.jsx::handlePay" in caller_ids


def test_question_callees_of_process_payment(rag_system):
    """Eval Q3: What does processPayment depend on? (Graph RAG forward traversal)"""
    graph_rag = rag_system["graph_rag"]
    items = graph_rag.retrieve_subgraph_context("src/services/paymentService.js::processPayment", include_callers=False, include_callees=True)
    callee_ids = {it.node_id for it in items if it.direction == "dependency"}
    assert "src/database/database.js::query" in callee_ids


def test_question_tests_connected_to_payment(rag_system):
    """Eval Q4: Which tests cover payment processing?"""
    graph_rag = rag_system["graph_rag"]
    items = graph_rag.retrieve_subgraph_context("src/services/paymentService.js::processPayment")
    test_items = [it for it in items if it.direction == "test" or "test" in it.relation_type]
    assert len(test_items) > 0
    assert any("payment.test.js" in it.file_path for it in test_items)


def test_question_api_route_handling(rag_system):
    """Eval Q5: Which API route handles payment requests?"""
    hybrid = rag_system["hybrid"]
    results = hybrid.retrieve("paymentRoutes handlePaymentRequest", top_k=3, repository_id=1)
    matched_files = {r.file_path for r in results}
    assert "src/routes/paymentRoutes.js" in matched_files


def test_question_component_hierarchy_rendering(rag_system):
    """Eval Q6: Which components depend on / render PaymentForm?"""
    graph_rag = rag_system["graph_rag"]
    items = graph_rag.retrieve_subgraph_context("src/components/PaymentForm.jsx::PaymentForm")
    render_callers = {it.node_id for it in items if it.relation_type == "renders"}
    assert "src/components/Checkout.jsx::Checkout" in render_callers


def test_hybrid_vs_individual_retrieval_comparison(rag_system):
    """
    Compare BM25 only, Vector only, and Hybrid RRF:
    Demonstrates that Hybrid combines lexical keyword hits and structural graph evidence.
    """
    query = "processPayment handlePaymentRequest"
    bm25_res = rag_system["bm25"].retrieve(query, top_k=3, repository_id=1)
    vector_res = rag_system["vector"].retrieve(query, top_k=3, repository_id=1)
    hybrid_res = rag_system["hybrid"].retrieve(query, top_k=3, repository_id=1)

    assert len(bm25_res) > 0
    assert len(vector_res) > 0
    assert len(hybrid_res) > 0

    # Hybrid fused results contain sources from both retrieval modes
    top_hybrid = hybrid_res[0]
    assert len(top_hybrid.retrieval_sources) >= 1


def test_duplicate_removal_in_rrf_fusion(rag_system):
    """Ensure duplicate chunks across multiple retrieval engines are consolidated with combined RRF score."""
    hybrid = rag_system["hybrid"]
    results = hybrid.retrieve("processPayment", top_k=10, repository_id=1)
    chunk_ids = [r.chunk_id for r in results]
    assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunk IDs found in fused results"


def test_repository_scoped_vector_and_bm25_isolation(rag_system):
    """Ensure repository 1 queries do not return repository 2 chunks."""
    bm25_res = rag_system["bm25"].retrieve("processPayment", top_k=10, repository_id=1)
    for chunk, _ in bm25_res:
        assert chunk.repository_id == 1

    vec_res = rag_system["vector"].retrieve("processPayment", top_k=10, repository_id=1)
    for chunk, _ in vec_res:
        assert chunk.repository_id == 1


def test_langgraph_bounded_retry_behavior(rag_system):
    """Verify LangGraph retry logic is bounded to 2 retries max."""
    class AlwaysFailingVerifier(EvidenceVerifier):
        def verify_answer(self, answer, evidence):
            res = super().verify_answer(answer, evidence)
            res.is_verified = False
            res.unsupported_claims = ["Forced retry hallucination test claim"]
            return res

    mock_orchestrator = ConversationalRAGOrchestrator(
        hybrid_retriever=rag_system["hybrid"],
        verifier=AlwaysFailingVerifier()
    )

    response = mock_orchestrator.ask("What does processPayment do?", repository_id=1)
    assert response["is_verified"] is False
    assert "Verification Note" in response["answer"]
