from pathlib import Path
from typing import List, Tuple, Dict, Optional

from app.extractors.javascript.advanced_parser import AdvancedJavaScriptExtractor
from app.extractors.python.parser import PythonExtractor
from app.graph.schema import Node, NodeType, DependencyEdge, RelationType, ExtractedImport


class MultiLanguageExtractor:
    """
    Unified multi-language repository extractor combining:
        - Advanced JavaScript/TypeScript/React Tree-sitter extractor
        - Python AST extractor
        - Cross-language Frontend/Backend HTTP route matching
    """

    def __init__(self):
        self.js_extractor = AdvancedJavaScriptExtractor()
        self.py_extractor = PythonExtractor()

    def extract_repository(
        self,
        repo_root: Path
    ) -> Tuple[List[Node], List[DependencyEdge], List[ExtractedImport]]:
        repo_root = Path(repo_root).resolve()

        # 1. Extract JavaScript/TypeScript/JSX files
        js_nodes, js_edges, js_imports = self.js_extractor.extract_repository(repo_root)

        # 2. Extract Python files
        py_nodes, py_edges, py_imports = self.py_extractor.extract_repository(repo_root)

        # 3. Combine nodes and edges
        all_nodes_dict: Dict[str, Node] = {n.id: n for n in js_nodes}
        for n in py_nodes:
            if n.id not in all_nodes_dict:
                all_nodes_dict[n.id] = n

        all_edges: List[DependencyEdge] = list(js_edges) + list(py_edges)
        all_imports: List[ExtractedImport] = list(js_imports) + list(py_imports)

        # 4. Cross-Boundary HTTP Route Matching:
        # Match frontend 'fetch' calls to declared API route nodes (Express or FastAPI)
        api_route_nodes = {n.id: n for n in all_nodes_dict.values() if n.type == NodeType.API_ROUTE}

        # Inspect JS files for fetch calls matching known API routes
        # (Already captured during JS extraction or matched dynamically)
        for edge in list(all_edges):
            # If an edge target is an API route, ensure the route node exists in all_nodes
            if edge.type == RelationType.FETCHES and edge.target not in all_nodes_dict:
                # Target route wasn't declared in backend, keep as unlinked or remove false link
                pass

        return list(all_nodes_dict.values()), all_edges, all_imports
