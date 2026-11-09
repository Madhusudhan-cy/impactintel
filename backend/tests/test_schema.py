from app.graph.schema import (
    Node,
    DependencyEdge,
    NodeType,
    RelationType,
    ExtractedImport,
    ExtractedSymbol,
    ExtractedCall
)


def test_node_schema_creation():
    node = Node(
        id="src/services/paymentService.js",
        type=NodeType.FILE,
        path="src/services/paymentService.js",
        language="javascript",
        metadata={"lines": 42}
    )
    assert node.id == "src/services/paymentService.js"
    assert node.type == NodeType.FILE
    assert node.language == "javascript"
    assert node.metadata["lines"] == 42


def test_fine_grained_node_helpers():
    func_node = Node.create_function("src/services/paymentService.js", "processPayment")
    assert func_node.id == "src/services/paymentService.js::processPayment"
    assert func_node.type == NodeType.FUNCTION
    assert func_node.name == "processPayment"

    class_node = Node.create_class("src/database/database.js", "Database")
    assert class_node.id == "src/database/database.js::Database"
    assert class_node.type == NodeType.CLASS

    comp_node = Node.create_component("src/components/Checkout.jsx", "Checkout")
    assert comp_node.id == "src/components/Checkout.jsx::Checkout"
    assert comp_node.type == NodeType.COMPONENT

    route_node = Node.create_api_route("POST", "/api/payment", "src/routes/paymentRoutes.js")
    assert route_node.id == "POST /api/payment"
    assert route_node.type == NodeType.API_ROUTE

    test_node = Node.create_test("tests/payment.test.js", "testProcessPayment")
    assert test_node.id == "tests/payment.test.js::testProcessPayment"
    assert test_node.type == NodeType.TEST


def test_edge_schema_creation():
    edge = DependencyEdge(
        source="src/routes/paymentRoutes.js",
        target="src/services/paymentService.js",
        type=RelationType.IMPORTS,
        file="src/routes/paymentRoutes.js",
        line=2,
        statement="import { processPayment } from '../services/paymentService.js';",
        confidence=1.0,
        extractor="tree_sitter"
    )
    assert edge.source == "src/routes/paymentRoutes.js"
    assert edge.target == "src/services/paymentService.js"
    assert edge.type == RelationType.IMPORTS
    assert edge.line == 2


def test_extracted_import_schema():
    record = ExtractedImport(
        source_file="src/app.js",
        raw_specifier="express",
        resolved_path=None,
        line_number=1,
        statement="import express from 'express';",
        is_external=True,
        is_resolved=False,
        default_import="express"
    )
    assert record.is_external is True
    assert record.is_resolved is False
    assert record.default_import == "express"


def test_extracted_symbol_and_call():
    sym = ExtractedSymbol(
        name="processPayment",
        symbol_type=NodeType.FUNCTION,
        file_path="src/services/paymentService.js",
        start_line=5,
        end_line=15,
        is_exported=True
    )
    assert sym.node_id == "src/services/paymentService.js::processPayment"
    assert sym.is_exported is True

    call = ExtractedCall(
        caller_file="src/routes/paymentRoutes.js",
        caller_symbol="handlePaymentRequest",
        callee_name="processPayment",
        line_number=6,
        statement="processPayment(userId, amount)"
    )
    assert call.callee_name == "processPayment"
    assert call.is_resolved is False
