from pathlib import Path
import pytest

from app.extractors.unified import MultiLanguageExtractor
from app.graph.builder import CodeKnowledgeGraph
from app.rag.chunker import CodeChunker
from app.rag.bm25 import BM25Retriever
from app.rag.graph_rag import GraphRAGRetriever
from app.rag.vector_store import VectorRetriever
from app.rag.hybrid import HybridRetriever
from app.rag.workflow import ConversationalRAGOrchestrator
from app.rag.verifier import EvidenceVerifier
from app.rag.memory import ConversationManager


@pytest.fixture(scope="module")
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


@pytest.fixture(scope="module")
def orchestrator(repo_root):
    extractor = MultiLanguageExtractor()
    nodes, edges, _ = extractor.extract_repository(repo_root)
    ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)

    chunker = CodeChunker(extractor=extractor)
    chunks = chunker.chunk_repository(repo_root, repository_id=1)

    bm25 = BM25Retriever(chunks)
    graph_rag = GraphRAGRetriever(ckg, chunks=chunks)
    vector = VectorRetriever(chunks)
    hybrid = HybridRetriever(bm25_retriever=bm25, graph_rag_retriever=graph_rag, vector_retriever=vector)

    memory = ConversationManager()
    return ConversationalRAGOrchestrator(
        hybrid_retriever=hybrid,
        memory_manager=memory
    )


def test_full_langgraph_workflow_execution(orchestrator):
    query = "What does processPayment do and what does it call?"
    response = orchestrator.ask(query, repository_id=1)

    assert "conversation_id" in response
    assert response["is_verified"] is True
    assert "processPayment" in response["answer"]
    assert "src/services/paymentService.js" in response["answer"]
    assert len(response["retrieval_evidence"]) > 0


def test_claim_verifier_flags_hallucination():
    verifier = EvidenceVerifier()
    # Mock evidence mentioning processPayment and Database.query
    from app.rag.hybrid import FusedEvidence
    mock_evidence = [
        FusedEvidence(
            chunk_id="chunk_1",
            file_path="src/services/paymentService.js",
            symbol_name="processPayment",
            symbol_type="Function",
            start_line=5,
            end_line=15,
            content="export function processPayment(userId, amount) { return dbConnection.query('INSERT...'); }",
            rrf_score=0.03
        )
    ]

    # Answer containing supported claims and an unsupported claim about Stripe and Bitcoin
    answer = (
        "processPayment inserts a payment record using dbConnection.query. "
        "The system processes transactions using Stripe and Bitcoin cryptocurrency gateway."
    )

    result = verifier.verify_answer(answer, mock_evidence)
    assert result.is_verified is False
    assert len(result.unsupported_claims) >= 1
    assert any("Bitcoin" in u for u in result.unsupported_claims)
    assert result.corrected_answer is not None
    assert "⚠️ Verification Note" in result.corrected_answer


def test_conversational_memory_followup_resolution(orchestrator):
    # First turn
    turn1 = orchestrator.ask("Which components call processPayment?", repository_id=1)
    cid = turn1["conversation_id"]

    # Follow-up turn using anaphora
    turn2 = orchestrator.ask("What does the first one do?", repository_id=1, conversation_id=cid)

    assert turn2["conversation_id"] == cid
    # Anaphora should be resolved in resolved_query
    assert "first one" not in turn2["resolved_query"]


def test_repository_authorization_boundary(orchestrator):
    # Turn on repository 1
    turn1 = orchestrator.ask("What does Database do?", repository_id=1)
    cid = turn1["conversation_id"]

    # Attempting to access conversation on repository 2 should raise PermissionError
    with pytest.raises(PermissionError, match="belongs to a different repository"):
        orchestrator.ask("Followup", repository_id=2, conversation_id=cid)
