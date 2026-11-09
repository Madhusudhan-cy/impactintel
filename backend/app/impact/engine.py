from collections import deque
from typing import List, Dict, Set, Union, Optional
import networkx as nx

from app.graph.builder import CodeKnowledgeGraph
from app.impact.models import AffectedComponent, ImpactAnalysisReport


def find_affected_components(
    graph_or_ckg: Union[nx.DiGraph, CodeKnowledgeGraph],
    changed_files: List[str],
    max_depth: int = 3
) -> ImpactAnalysisReport:
    """
    Perform reverse dependency traversal to identify all components directly or
    indirectly affected by changes to one or more files or fine-grained symbols.

    Canonical Edge Direction:
        Caller / Dependent (source) ➔ Dependency (target)

    Traversal Rules:
        1. Changed entities are at depth 0 and excluded from affected results.
        2. Direct dependents are at depth 1.
        3. Indirect dependents are at depth 2 and 3.
        4. Traversal strictly halts at max_depth (default 3) for functional dependencies.
        5. 'tests' relationships do NOT consume the 3-level depth limit and are
           collected in related_tests without further propagating functional impact.
        6. Cycles are resolved safely using shortest-path visited tracking.
        7. If symbol IDs (e.g. 'file::symbol') are provided, analysis_level is 'symbol-level';
           otherwise, falls back to 'file-level'.
    """
    if isinstance(graph_or_ckg, CodeKnowledgeGraph):
        graph = graph_or_ckg.graph
    else:
        graph = graph_or_ckg

    # Normalize changed items
    normalized_changed: List[str] = [cf.strip() for cf in changed_files if cf.strip()]
    changed_set: Set[str] = set(normalized_changed)

    # Determine analysis level
    is_symbol_level = any("::" in item or " " in item for item in normalized_changed)
    analysis_level = "symbol-level" if is_symbol_level else "file-level"

    # Queue holds: (current_node, current_depth, path_from_changed_file)
    queue: deque = deque()
    # visited maps node_id -> minimum depth at which it was discovered
    visited: Dict[str, int] = {}
    related_tests_set: Set[str] = set()

    for item in normalized_changed:
        if item in graph:
            visited[item] = 0
            queue.append((item, 0, [item]))
        else:
            # If a file was changed, also seed all symbols defined by this file
            for node_id in graph.nodes:
                if node_id.startswith(f"{item}::"):
                    visited[node_id] = 0
                    queue.append((node_id, 0, [item, node_id]))

    # affected_map maps affected_node_id -> dict(depth, path, evidence, entity_type)
    affected_map: Dict[str, Dict] = {}

    while queue:
        curr_node, curr_depth, curr_path = queue.popleft()

        # Check all incoming edges (predecessors are the callers/dependents)
        for predecessor in graph.predecessors(curr_node):
            if predecessor in changed_set:
                continue

            edge_data = graph[predecessor][curr_node]
            edge_type = edge_data.get("type", "imports")
            edge_evidence = edge_data.get("evidence", [])

            # Special Rule: 'tests' relationships do not consume depth limit
            if edge_type == "tests" or graph.nodes.get(predecessor, {}).get("type") == "Test":
                related_tests_set.add(predecessor)
                # Tests do not propagate downstream functional impact, so we do not queue them
                continue

            # Standard functional dependency: enforce max_depth
            if curr_depth >= max_depth:
                continue

            next_depth = curr_depth + 1
            next_path = curr_path + [predecessor]

            if predecessor not in visited or next_depth < visited[predecessor]:
                visited[predecessor] = next_depth
                pred_type = graph.nodes.get(predecessor, {}).get("type", "File")
                affected_map[predecessor] = {
                    "depth": next_depth,
                    "path": next_path,
                    "evidence": edge_evidence,
                    "entity_type": pred_type
                }
                queue.append((predecessor, next_depth, next_path))

    # Sort primarily by depth (closest first), then alphabetically by entity name
    sorted_affected_keys = sorted(
        affected_map.keys(),
        key=lambda k: (affected_map[k]["depth"], k)
    )

    affected_components: List[AffectedComponent] = []
    for node_id in sorted_affected_keys:
        info = affected_map[node_id]
        d = info["depth"]
        impact_level = "Direct (Depth 1)" if d == 1 else f"Indirect (Depth {d})"
        affected_components.append(
            AffectedComponent(
                file_path=node_id,
                entity_type=info["entity_type"],
                depth=d,
                impact_level=impact_level,
                dependency_path=info["path"],
                evidence=info["evidence"]
            )
        )

    all_nodes = set(graph.nodes)
    affected_set = set(affected_map.keys())
    unaffected_files = sorted(list(all_nodes - affected_set - changed_set - related_tests_set))

    return ImpactAnalysisReport(
        changed_files=normalized_changed,
        analysis_level=analysis_level,
        max_depth=max_depth,
        total_affected=len(affected_components),
        affected_components=affected_components,
        related_tests=sorted(list(related_tests_set)),
        unaffected_files=unaffected_files
    )
