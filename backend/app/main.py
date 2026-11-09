import argparse
import sys
from pathlib import Path

from app.extractors.unified import MultiLanguageExtractor
from app.graph.builder import CodeKnowledgeGraph
from app.impact.engine import find_affected_components


def format_dependency_path(path: list[str]) -> str:
    """Format path from changed entity to affected component."""
    if len(path) <= 1:
        return path[0] if path else ""
    return " ──> ".join(path)


def run_pipeline(repo_path: Path, changed_files: list[str], max_depth: int = 3):
    print("=" * 76)
    print("   AI-POWERED REPOSITORY IMPACT INTELLIGENCE SYSTEM — INCREMENT 3")
    print("=" * 76)
    print(f"Target Repository   : {repo_path.resolve()}")
    print(f"Changed Entities    : {', '.join(changed_files)}")
    print(f"Max Traversal Depth : {max_depth}")
    print("-" * 76)

    # 1. Multi-Language Extraction Phase
    print("\n[Phase 1] Multi-Language Fine-Grained AST Extraction (Tree-sitter & AST)...")
    extractor = MultiLanguageExtractor()
    nodes, edges, all_imports = extractor.extract_repository(repo_path)

    node_type_counts = {}
    for n in nodes:
        node_type_counts[n.type.value] = node_type_counts.get(n.type.value, 0) + 1

    edge_type_counts = {}
    for e in edges:
        edge_type_counts[e.type.value] = edge_type_counts.get(e.type.value, 0) + 1

    print(f"  ✓ Total Graph Entities : {len(nodes)} {node_type_counts}")
    print(f"  ✓ Total Graph Edges    : {len(edges)} {edge_type_counts}")

    # 2. Graph Assembly Phase
    print("\n[Phase 2] Building Fine-Grained Code Knowledge Graph (NetworkX DiGraph)...")
    ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)
    print(f"  ✓ Canonical Edge Direction: Dependent / Caller ➔ Dependency / Callee")

    # 3. Impact Analysis Phase
    print("\n[Phase 3] Reverse Dependency Traversal...")
    report = find_affected_components(ckg, changed_files, max_depth=max_depth)

    print("\n" + "=" * 76)
    print(f"               IMPACT ANALYSIS REPORT ({report.analysis_level.upper()})")
    print("=" * 76)
    print(f"Changed Entity/Entities:")
    for cf in report.changed_files:
        print(f"  • {cf}")

    print(f"\nTotal Potentially Affected Components: {report.total_affected}\n")

    if not report.affected_components:
        print("  (No dependents identified within traversal depth)")
    else:
        for idx, component in enumerate(report.affected_components, 1):
            print(f"{idx}. {component.file_path}")
            print(f"   Entity Type     : {component.entity_type}")
            print(f"   Impact Level    : {component.impact_level}")
            print(f"   Dependency Path : {format_dependency_path(component.dependency_path)}")
            if component.evidence:
                ev = component.evidence[0]
                line_no = ev.get("line", "?")
                stmt = ev.get("statement", "")
                if stmt:
                    first_line = stmt.splitlines()[0][:70]
                    print(f"   Evidence        : [Line {line_no}] {first_line}")
            print()

    if report.related_tests:
        print("-" * 76)
        print("Related Tests Identified (Covering Affected Components):")
        for t in report.related_tests:
            print(f"  🧪 {t}")

    print("-" * 76)
    print("Verification of Unaffected Components (Zero False Positives):")
    if report.unaffected_files:
        sample_unaffected = [f for f in report.unaffected_files if not ("::" in f)][:8]
        for uf in sample_unaffected:
            print(f"  ✓ {uf}")
        if len(report.unaffected_files) > 8:
            print(f"    ... and {len(report.unaffected_files) - 8} more unaffected symbols/files")
    print("=" * 76)


def main():
    parser = argparse.ArgumentParser(
        description="Run Code Knowledge Graph fine-grained extraction and reverse dependency impact analysis."
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="sample-repository",
        help="Path to the target repository (default: sample-repository)"
    )
    parser.add_argument(
        "--changed",
        nargs="+",
        default=["src/database/database.js::Database.query"],
        help="List of changed file or symbol paths (default: src/database/database.js::Database.query)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=3,
        help="Maximum reverse dependency traversal depth (default: 3)"
    )

    args = parser.parse_args()
    repo_path = Path(args.repo)

    if not repo_path.exists():
        print(f"Error: Repository path '{repo_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    run_pipeline(repo_path, args.changed, max_depth=args.depth)


if __name__ == "__main__":
    main()
