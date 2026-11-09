from pathlib import Path
import pytest
from app.extractors.javascript.advanced_parser import AdvancedJavaScriptExtractor
from app.graph.schema import NodeType, RelationType


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


@pytest.fixture
def extractor():
    return AdvancedJavaScriptExtractor()


def test_function_and_class_extraction(repo_root, extractor):
    db_file = repo_root / "src" / "database" / "database.js"
    nodes, edges, imports, calls = extractor.extract_file(db_file, repo_root)

    node_ids = {n.id: n for n in nodes}
    # Class node
    assert "src/database/database.js::Database" in node_ids
    assert node_ids["src/database/database.js::Database"].type == NodeType.CLASS

    # Methods
    assert "src/database/database.js::Database.connect" in node_ids
    assert "src/database/database.js::Database.query" in node_ids

    # defines relationships
    edge_pairs = {(e.source, e.target, e.type) for e in edges}
    assert (
        "src/database/database.js",
        "src/database/database.js::Database",
        RelationType.DEFINES
    ) in edge_pairs
    assert (
        "src/database/database.js::Database",
        "src/database/database.js::Database.query",
        RelationType.DEFINES
    ) in edge_pairs


def test_calls_resolution(repo_root, extractor):
    payment_file = repo_root / "src" / "services" / "paymentService.js"
    nodes, edges, imports, calls = extractor.extract_file(payment_file, repo_root)

    edge_pairs = {(e.source, e.target, e.type) for e in edges}
    # processPayment calls dbConnection.query -> resolved to Database.query
    assert (
        "src/services/paymentService.js::processPayment",
        "src/database/database.js::query",
        RelationType.CALLS
    ) in edge_pairs

    # processPayment calls logInfo
    assert (
        "src/services/paymentService.js::processPayment",
        "src/utils/logger.js::logInfo",
        RelationType.CALLS
    ) in edge_pairs


def test_react_component_renders_extraction(repo_root, extractor):
    checkout_file = repo_root / "src" / "components" / "Checkout.jsx"
    nodes, edges, imports, calls = extractor.extract_file(checkout_file, repo_root)

    node_types = {n.id: n.type for n in nodes}
    assert node_types.get("src/components/Checkout.jsx::Checkout") == NodeType.COMPONENT
    assert node_types.get("src/components/Checkout.jsx::handlePay") == NodeType.FUNCTION

    edge_pairs = {(e.source, e.target, e.type) for e in edges}
    # Checkout renders PaymentForm
    assert (
        "src/components/Checkout.jsx::Checkout",
        "src/components/PaymentForm.jsx::PaymentForm",
        RelationType.RENDERS
    ) in edge_pairs


def test_test_relationship_extraction(repo_root, extractor):
    test_file = repo_root / "tests" / "payment.test.js"
    nodes, edges, imports, calls = extractor.extract_file(test_file, repo_root)

    # Test function calls processPayment -> tests relationship
    edge_pairs = {(e.source, e.target, e.type) for e in edges}
    assert (
        "tests/payment.test.js::testProcessPayment",
        "src/services/paymentService.js::processPayment",
        RelationType.TESTS
    ) in edge_pairs
