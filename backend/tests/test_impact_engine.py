from pathlib import Path
import pytest
import networkx as nx

from app.extractors.javascript.parser import JavaScriptExtractor
from app.graph.builder import CodeKnowledgeGraph
from app.impact.engine import find_affected_components


@pytest.fixture(scope="module")
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


@pytest.fixture(scope="module")
def sample_graph(repo_root):
    extractor = JavaScriptExtractor()
    nodes, edges, _ = extractor.extract_repository(repo_root)
    ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)
    return ckg


# Scenario 1: A file with one direct dependent
def test_scenario_1_one_direct_dependent(sample_graph):
    # paymentRoutes.js is directly imported only by app.js
    report = find_affected_components(sample_graph, ["src/routes/paymentRoutes.js"])
    affected_files = [c.file_path for c in report.affected_components]
    assert "src/app.js" in affected_files
    # Direct dependent must have depth 1
    app_comp = next(c for c in report.affected_components if c.file_path == "src/app.js")
    assert app_comp.depth == 1
    assert app_comp.impact_level == "Direct (Depth 1)"


# Scenario 2: A file with multiple direct dependents
def test_scenario_2_multiple_direct_dependents(sample_graph):
    # logger.js is directly imported by paymentService.js and notificationService.js
    report = find_affected_components(sample_graph, ["src/utils/logger.js"])
    direct_dependents = [c.file_path for c in report.affected_components if c.depth == 1]
    assert "src/services/paymentService.js" in direct_dependents
    assert "src/services/notificationService.js" in direct_dependents
    assert len(direct_dependents) >= 2


# Scenario 3: A file with indirect dependents
def test_scenario_3_indirect_dependents(sample_graph):
    # database.js is imported by paymentService.js (direct) -> paymentRoutes.js (indirect) -> app.js (indirect)
    report = find_affected_components(sample_graph, ["src/database/database.js"])
    depth_by_file = {c.file_path: c.depth for c in report.affected_components}

    assert depth_by_file.get("src/services/paymentService.js") == 1
    assert depth_by_file.get("src/routes/paymentRoutes.js") == 2
    assert depth_by_file.get("src/app.js") == 3


# Scenario 4: A changed file with no dependents
def test_scenario_4_file_with_no_dependents(sample_graph):
    # standaloneHelper.js is completely isolated
    report = find_affected_components(sample_graph, ["src/utils/standaloneHelper.js"])
    assert report.total_affected == 0
    assert len(report.affected_components) == 0

    # app.js is the top-level application file and has no callers/dependents
    report_app = find_affected_components(sample_graph, ["src/app.js"])
    assert report_app.total_affected == 0


# Scenario 5: A dependency chain longer than three levels
def test_scenario_5_chain_longer_than_three_levels(sample_graph):
    # Chain: database.js <- level1 <- level2 <- level3 <- level4
    # Max depth is 3: level1 (1), level2 (2), level3 (3) should be included.
    # level4 (depth 4) must be excluded!
    report = find_affected_components(sample_graph, ["src/database/database.js"], max_depth=3)
    affected_files = [c.file_path for c in report.affected_components]

    assert "src/services/deepChain/level1.js" in affected_files
    assert "src/services/deepChain/level2.js" in affected_files
    assert "src/services/deepChain/level3.js" in affected_files
    assert "src/services/deepChain/level4.js" not in affected_files


# Scenario 6: Multiple changed files
def test_scenario_6_multiple_changed_files(sample_graph):
    # Changing both standaloneHelper.js and paymentRoutes.js
    report = find_affected_components(
        sample_graph,
        ["src/utils/standaloneHelper.js", "src/routes/paymentRoutes.js"]
    )
    affected_files = [c.file_path for c in report.affected_components]
    assert "src/app.js" in affected_files
    # Changed files themselves must never appear in affected list
    assert "src/utils/standaloneHelper.js" not in affected_files
    assert "src/routes/paymentRoutes.js" not in affected_files


# Scenario 7: Circular dependency relationships
def test_scenario_7_circular_dependencies(sample_graph):
    # userRoutes.js <-> userService.js
    report = find_affected_components(sample_graph, ["src/services/userService.js"])
    affected_files = [c.file_path for c in report.affected_components]

    assert "src/routes/userRoutes.js" in affected_files
    assert "src/app.js" in affected_files
    # Must not contain userService.js in affected components (the changed file)
    assert "src/services/userService.js" not in affected_files
    # Traversal should complete without infinite recursion


# Scenario 8: An unrelated file that must not appear in the impact results
def test_scenario_8_unrelated_file_exclusion(sample_graph):
    # When database.js changes, notificationService.js and standaloneHelper.js must not appear
    report = find_affected_components(sample_graph, ["src/database/database.js"])
    affected_files = [c.file_path for c in report.affected_components]

    assert "src/services/notificationService.js" not in affected_files
    assert "src/utils/standaloneHelper.js" not in affected_files
    assert "src/utils/logger.js" not in affected_files

    # They should be properly listed in unaffected_files
    assert "src/services/notificationService.js" in report.unaffected_files
    assert "src/utils/standaloneHelper.js" in report.unaffected_files
    assert "src/utils/logger.js" in report.unaffected_files


# Scenario 9: Correct dependency direction
def test_scenario_9_correct_dependency_direction(sample_graph):
    # paymentService.js depends on database.js (paymentService -> database.js).
    # If paymentService.js changes, database.js MUST NOT be affected.
    # Only files that DEPEND on paymentService (paymentRoutes, tests, app) should be affected.
    report = find_affected_components(sample_graph, ["src/services/paymentService.js"])
    affected_files = [c.file_path for c in report.affected_components]

    assert "src/database/database.js" not in affected_files
    assert "src/utils/logger.js" not in affected_files
    assert "src/routes/paymentRoutes.js" in affected_files
    assert "src/app.js" in affected_files


# Scenario 10: Correct dependency path reporting
def test_scenario_10_dependency_path_reporting(sample_graph):
    report = find_affected_components(sample_graph, ["src/database/database.js"])
    app_comp = next(c for c in report.affected_components if c.file_path == "src/app.js")

    expected_path = [
        "src/database/database.js",
        "src/services/paymentService.js",
        "src/routes/paymentRoutes.js",
        "src/app.js"
    ]
    assert app_comp.dependency_path == expected_path
    assert len(app_comp.evidence) > 0
    assert "line" in app_comp.evidence[0]
