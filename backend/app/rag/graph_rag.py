from typing import List, Dict, Any, Optional, Set, Tuple
import networkx as nx

from app.graph.builder import CodeKnowledgeGraph
from app.graph.schema import NodeType, RelationType
from app.rag.chunker import CodeChunk


class GraphContextItem:
    def __init__(
        self,
        node_id: str,
        node_type: str,
        file_path: str,
        relation_type: str,
        direction: str,  # "caller" (upstream) or "dependency" (downstream) or "test"
        source_node: Optional[str] = None,
        target_node: Optional[str] = None,
        statement: Optional[str] = None,
        line: Optional[int] = None,
        confidence: float = 1.0,
        evidence: Optional[List[Dict[str, Any]]] = None,
        chunk: Optional[CodeChunk] = None
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.file_path = file_path
        self.relation_type = relation_type
        self.direction = direction
        self.source_node = source_node or node_id
        self.target_node = target_node or node_id
        self.statement = statement
        self.line = line
        self.confidence = confidence
        self.evidence = evidence or []
        self.chunk = chunk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "file_path": self.file_path,
            "relation_type": self.relation_type,
            "direction": self.direction,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "statement": self.statement,
            "line": self.line,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "chunk_id": self.chunk.chunk_id if self.chunk else None
        }


class GraphRAGRetriever:
    """
    Structural Graph RAG retriever operating on the existing Code Knowledge Graph.
    Retrieves incoming callers, outgoing callees, rendering hierarchies, and test relationships.
    """

    def __init__(
        self,
        ckg_or_graph: Any,
        chunks: Optional[List[CodeChunk]] = None
    ):
        if isinstance(ckg_or_graph, CodeKnowledgeGraph):
            self.graph = ckg_or_graph.graph
        else:
            self.graph = ckg_or_graph

        # Map node_id -> CodeChunk for seamless context injection
        self.chunk_by_node: Dict[str, CodeChunk] = {}
        if chunks:
            for c in chunks:
                if c.associated_node_id:
                    self.chunk_by_node[c.associated_node_id] = c

    def find_entity_nodes(self, query: str) -> List[str]:
        """Match query terms against node IDs or symbol names in the graph."""
        query_lower = query.lower()
        matched = []
        for node_id, data in self.graph.nodes(data=True):
            # Exact or substring match in node ID
            if "::" in node_id:
                symbol = node_id.split("::", 1)[1].lower()
                if symbol in query_lower or query_lower in symbol:
                    matched.append(node_id)
            elif node_id.lower() in query_lower:
                matched.append(node_id)
        return matched

    def retrieve_subgraph_context(
        self,
        target_node_id: str,
        include_callers: bool = True,
        include_callees: bool = True,
        include_tests: bool = True,
        max_hops: int = 2
    ) -> List[GraphContextItem]:
        """
        Extract direct and 2-hop structural context around a target node.
        
        Canonical edge direction:
            Caller / Dependent (source) ➔ Dependency (target)
            
        Therefore:
            - graph.predecessors(node): Upstream Callers / Dependents
            - graph.successors(node): Downstream Callee Dependencies
        """
        if target_node_id not in self.graph:
            return []

        results: List[GraphContextItem] = []
        visited_edges: Set[Tuple[str, str, str]] = set()

        # 0. Primary Anchor Entity Node (the target itself)
        target_chunk = self.chunk_by_node.get(target_node_id)
        target_type = self.graph.nodes.get(target_node_id, {}).get("type", "Symbol")
        target_path = self.graph.nodes.get(target_node_id, {}).get("path", target_node_id.split("::")[0])
        results.append(
            GraphContextItem(
                node_id=target_node_id,
                node_type=target_type,
                file_path=target_path,
                relation_type="defines",
                direction="target",
                source_node=target_path,
                target_node=target_node_id,
                chunk=target_chunk
            )
        )

        # 1. Retrieve Upstream Dependents (Callers / Components that render / Handlers)
        if include_callers:
            for pred in self.graph.predecessors(target_node_id):
                edge_data = self.graph[pred][target_node_id]
                rel_type = edge_data.get("type", "calls")
                evidence = edge_data.get("evidence", [])
                stmt = evidence[0]["statement"] if evidence and "statement" in evidence[0] else None
                line = evidence[0]["line"] if evidence and "line" in evidence[0] else None

                edge_key = (pred, target_node_id, rel_type)
                if edge_key not in visited_edges:
                    visited_edges.add(edge_key)
                    direction = "test" if rel_type == "tests" else "caller"
                    pred_type = self.graph.nodes.get(pred, {}).get("type", "Symbol")
                    pred_path = self.graph.nodes.get(pred, {}).get("path", pred.split("::")[0])
                    conf = edge_data.get("confidence", 1.0)
                    results.append(
                        GraphContextItem(
                            node_id=pred,
                            node_type=pred_type,
                            file_path=pred_path,
                            relation_type=rel_type,
                            direction=direction,
                            source_node=pred,
                            target_node=target_node_id,
                            statement=stmt,
                            line=line,
                            confidence=conf,
                            evidence=evidence,
                            chunk=self.chunk_by_node.get(pred)
                        )
                    )

        # 2. Retrieve Downstream Dependencies (What does this function/component call or use?)
        if include_callees:
            for succ in self.graph.successors(target_node_id):
                edge_data = self.graph[target_node_id][succ]
                rel_type = edge_data.get("type", "calls")
                evidence = edge_data.get("evidence", [])
                stmt = evidence[0]["statement"] if evidence and "statement" in evidence[0] else None
                line = evidence[0]["line"] if evidence and "line" in evidence[0] else None

                edge_key = (target_node_id, succ, rel_type)
                if edge_key not in visited_edges:
                    visited_edges.add(edge_key)
                    succ_type = self.graph.nodes.get(succ, {}).get("type", "Symbol")
                    succ_path = self.graph.nodes.get(succ, {}).get("path", succ.split("::")[0])
                    conf = edge_data.get("confidence", 1.0)
                    results.append(
                        GraphContextItem(
                            node_id=succ,
                            node_type=succ_type,
                            file_path=succ_path,
                            relation_type=rel_type,
                            direction="dependency",
                            source_node=target_node_id,
                            target_node=succ,
                            statement=stmt,
                            line=line,
                            confidence=conf,
                            evidence=evidence,
                            chunk=self.chunk_by_node.get(succ)
                        )
                    )

        return results

    def retrieve(self, query: str) -> List[GraphContextItem]:
        """Convenience method to resolve query entities and retrieve their structural graph context."""
        matched_nodes = self.find_entity_nodes(query)
        all_items: List[GraphContextItem] = []
        seen_nodes: Set[str] = set()

        for node_id in matched_nodes:
            items = self.retrieve_subgraph_context(node_id)
            for it in items:
                if it.node_id not in seen_nodes:
                    seen_nodes.add(it.node_id)
                    all_items.append(it)

        return all_items
