import pytest
from app.graph.schema import Node, DependencyEdge, NodeType, RelationType
from app.graph.builder import CodeKnowledgeGraph


def test_graph_builder_nodes_and_edges():
    ckg = CodeKnowledgeGraph()

    n1 = Node(id="src/app.js", type=NodeType.FILE, path="src/app.js")
    n2 = Node(id="src/service.js", type=NodeType.FILE, path="src/service.js")
    ckg.add_node(n1)
    ckg.add_node(n2)

    assert ckg.node_count == 2

    edge = DependencyEdge(
        source="src/app.js",
        target="src/service.js",
        type=RelationType.IMPORTS,
        file="src/app.js",
        line=1,
        statement="import service from './service.js';"
    )
    ckg.add_edge(edge)

    assert ckg.edge_count == 1
    assert ckg.graph.has_edge("src/app.js", "src/service.js")

    # Canonical direction verification
    assert not ckg.graph.has_edge("src/service.js", "src/app.js")

    # Check predecessors (who depends on service.js)
    dependents = list(ckg.graph.predecessors("src/service.js"))
    assert dependents == ["src/app.js"]


def test_graph_builder_aggregates_multiple_imports():
    ckg = CodeKnowledgeGraph()

    n1 = Node(id="src/app.js", type=NodeType.FILE, path="src/app.js")
    n2 = Node(id="src/service.js", type=NodeType.FILE, path="src/service.js")
    ckg.add_node(n1)
    ckg.add_node(n2)

    edge1 = DependencyEdge(
        source="src/app.js",
        target="src/service.js",
        type=RelationType.IMPORTS,
        file="src/app.js",
        line=1,
        statement="import { a } from './service.js';"
    )
    edge2 = DependencyEdge(
        source="src/app.js",
        target="src/service.js",
        type=RelationType.IMPORTS,
        file="src/app.js",
        line=5,
        statement="import { b } from './service.js';"
    )

    ckg.add_edge(edge1)
    ckg.add_edge(edge2)

    # Edge count should still be 1 (single directed relationship with multiple evidences)
    assert ckg.edge_count == 1
    evidence = ckg.get_edge_evidence("src/app.js", "src/service.js")
    assert len(evidence) == 2
    assert evidence[0]["line"] == 1
    assert evidence[1]["line"] == 5
