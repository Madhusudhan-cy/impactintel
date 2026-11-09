from pathlib import Path
import pytest
from app.extractors.python.parser import PythonExtractor
from app.graph.schema import NodeType, RelationType


@pytest.fixture
def temp_py_repo(tmp_path):
    # Create sample Python project structure
    src = tmp_path / "src"
    src.mkdir()
    services = src / "services"
    services.mkdir()
    api = src / "api"
    api.mkdir()

    # services/payment.py
    (services / "payment.py").write_text("""
def validate_amount(amount):
    return amount > 0

class PaymentProcessor:
    def verify(self):
        return True

    def process_charge(self, amount):
        self.verify()
        return validate_amount(amount)
""")

    # api/routes.py
    (api / "routes.py").write_text("""
from src.services.payment import validate_amount

# FastAPI mock
class MockApp:
    def post(self, path):
        def dec(fn): return fn
        return dec

app = MockApp()

@app.post("/api/charge")
def charge_endpoint():
    validate_amount(100)
""")

    # tests/test_payment.py
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_payment.py").write_text("""
from src.services.payment import validate_amount

def test_validate_positive():
    validate_amount(50)
""")
    return tmp_path


def test_python_extractor_functions_and_classes(temp_py_repo):
    extractor = PythonExtractor()
    nodes, edges, imports = extractor.extract_repository(temp_py_repo)

    node_ids = {n.id: n for n in nodes}
    assert "src/services/payment.py::validate_amount" in node_ids
    assert node_ids["src/services/payment.py::validate_amount"].type == NodeType.FUNCTION

    assert "src/services/payment.py::PaymentProcessor" in node_ids
    assert node_ids["src/services/payment.py::PaymentProcessor"].type == NodeType.CLASS
    assert "src/services/payment.py::PaymentProcessor.verify" in node_ids
    assert "src/services/payment.py::PaymentProcessor.process_charge" in node_ids


def test_python_calls_and_fastapi_routes(temp_py_repo):
    extractor = PythonExtractor()
    nodes, edges, imports = extractor.extract_repository(temp_py_repo)

    edge_tuples = {(e.source, e.target, e.type) for e in edges}

    # self.verify call
    assert (
        "src/services/payment.py::PaymentProcessor.process_charge",
        "src/services/payment.py::PaymentProcessor.verify",
        RelationType.CALLS
    ) in edge_tuples

    # call to imported function in routes.py
    assert (
        "src/api/routes.py::charge_endpoint",
        "src/services/payment.py::validate_amount",
        RelationType.CALLS
    ) in edge_tuples

    # FastAPI route: POST /api/charge -> handled_by charge_endpoint
    assert (
        "POST /api/charge",
        "src/api/routes.py::charge_endpoint",
        RelationType.HANDLED_BY
    ) in edge_tuples

    # Pytest test: test_validate_positive -> tests validate_amount
    assert (
        "tests/test_payment.py::test_validate_positive",
        "src/services/payment.py::validate_amount",
        RelationType.TESTS
    ) in edge_tuples
