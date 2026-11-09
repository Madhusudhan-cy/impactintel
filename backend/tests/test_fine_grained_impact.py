from pathlib import Path
import pytest
from app.extractors.unified import MultiLanguageExtractor
from app.graph.builder import CodeKnowledgeGraph
from app.impact.engine import find_affected_components


@pytest.fixture(scope="module")
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


@pytest.fixture(scope="module")
def full_graph(repo_root):
    extractor = MultiLanguageExtractor()
    nodes, edges, _ = extractor.extract_repository(repo_root)
    ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)
    return ckg


def test_fine_grained_function_impact(full_graph):
    # Change specific function: Database.query
    report = find_affected_components(
        full_graph,
        ["src/database/database.js::query"]
    )
    assert report.analysis_level == "symbol-level"

    affected_ids = [c.file_path for c in report.affected_components]
    # processPayment directly calls query (Depth 1)
    assert "src/services/paymentService.js::processPayment" in affected_ids

    # handlePaymentRequest calls processPayment (Depth 2)
    assert "src/routes/paymentRoutes.js::handlePaymentRequest" in affected_ids

    # Checkout handlePay calls processPayment (Depth 2)
    assert "src/components/Checkout.jsx::handlePay" in affected_ids

    # Test relationship is captured in related_tests without consuming depth budget
    assert "tests/payment.test.js::testProcessPayment" in report.related_tests
    # And test node is not in affected_components
    assert "tests/payment.test.js::testProcessPayment" not in affected_ids


def test_react_component_impact(full_graph):
    # Change child component: PaymentForm
    report = find_affected_components(
        full_graph,
        ["src/components/PaymentForm.jsx::PaymentForm"]
    )
    assert report.analysis_level == "symbol-level"
    affected_ids = [c.file_path for c in report.affected_components]

    # Checkout renders PaymentForm (Depth 1)
    assert "src/components/Checkout.jsx::Checkout" in affected_ids


def test_file_level_fallback(full_graph):
    # When file path without symbol is passed, falls back to file-level analysis
    report = find_affected_components(
        full_graph,
        ["src/database/database.js"]
    )
    assert report.analysis_level == "file-level"
    assert report.total_affected > 0
