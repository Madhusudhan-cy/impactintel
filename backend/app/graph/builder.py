from typing import List, Dict, Any, Optional
import networkx as nx
from app.graph.schema import Node, DependencyEdge


class CodeKnowledgeGraph:
    """
    In-memory Code Knowledge Graph built on NetworkX DiGraph.
    
    Canonical edge direction:
        Caller / Dependent (source) ➔ Dependency (target)
        
    Why nx.DiGraph:
    In file-level dependency analysis, a file either depends on another file or does not.
    Using DiGraph ensures standard DAG and traversal semantics while allowing us to aggregate
    multiple import statements between the same pair of files into an 'evidence' list attribute
    on the single directed edge.
    """

    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()

    def add_node(self, node: Node) -> None:
        """Add a normalized node to the graph with metadata attributes."""
        self.graph.add_node(
            node.id,
            type=node.type.value,
            path=node.path,
            language=node.language,
            **node.metadata
        )

    def add_edge(self, edge: DependencyEdge) -> None:
        """
        Add a directed dependency edge.
        If an edge already exists between source and target, aggregate the evidence.
        """
        evidence_item = {
            "line": edge.line,
            "statement": edge.statement,
            "confidence": edge.confidence,
            "extractor": edge.extractor,
            "metadata": edge.metadata
        }

        if self.graph.has_edge(edge.source, edge.target):
            # Aggregate evidence for existing edge
            edge_data = self.graph[edge.source][edge.target]
            edge_data["evidence"].append(evidence_item)
        else:
            self.graph.add_edge(
                edge.source,
                edge.target,
                type=edge.type.value,
                file=edge.file,
                evidence=[evidence_item]
            )

    @classmethod
    def from_nodes_and_edges(cls, nodes: List[Node], edges: List[DependencyEdge]) -> "CodeKnowledgeGraph":
        """Factory method to construct a graph from extracted nodes and edges."""
        ckg = cls()
        for node in nodes:
            ckg.add_node(node)
        for edge in edges:
            ckg.add_edge(edge)
        return ckg

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if node_id in self.graph:
            return self.graph.nodes[node_id]
        return None

    def get_edge_evidence(self, source: str, target: str) -> List[Dict[str, Any]]:
        """Retrieve all import evidence between source (dependent) and target (dependency)."""
        if self.graph.has_edge(source, target):
            return self.graph[source][target].get("evidence", [])
        return []
