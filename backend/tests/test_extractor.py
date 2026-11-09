from pathlib import Path
import pytest
from app.extractors.javascript.parser import JavaScriptExtractor
from app.extractors.javascript.resolver import resolve_import_path, is_relative_import
from app.graph.schema import Node, DependencyEdge, NodeType, RelationType, ExtractedImport


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent.parent / "sample-repository"


@pytest.fixture
def extractor():
    return JavaScriptExtractor()


def test_is_relative_import():
    assert is_relative_import("./service.js") is True
    assert is_relative_import("../utils/logger.js") is True
    assert is_relative_import("axios") is False
    assert is_relative_import("express") is False
    assert is_relative_import("@company/auth") is False


def test_resolver_relative_file_found(repo_root):
    current_file = repo_root / "src" / "services" / "paymentService.js"
    rel_path, is_ext, is_res = resolve_import_path("../database/database.js", current_file, repo_root)
    assert rel_path == "src/database/database.js"
    assert is_ext is False
    assert is_res is True


def test_resolver_without_extension(repo_root):
    current_file = repo_root / "src" / "services" / "paymentService.js"
    rel_path, is_ext, is_res = resolve_import_path("../database/database", current_file, repo_root)
    assert rel_path == "src/database/database.js"
    assert is_ext is False
    assert is_res is True


def test_resolver_external_package(repo_root):
    current_file = repo_root / "src" / "services" / "paymentService.js"
    rel_path, is_ext, is_res = resolve_import_path("axios", current_file, repo_root)
    assert rel_path is None
    assert is_ext is True
    assert is_res is False


def test_resolver_unresolved_internal(repo_root):
    current_file = repo_root / "src" / "utils" / "brokenHelper.js"
    rel_path, is_ext, is_res = resolve_import_path("./nonExistentFile.js", current_file, repo_root)
    assert rel_path is None
    assert is_ext is False
    assert is_res is False


def test_extractor_sample_repository(repo_root, extractor):
    nodes, edges, all_imports = extractor.extract_repository(repo_root)

    # 1. Check discovered nodes
    node_ids = {n.id for n in nodes}
    assert "src/database/database.js" in node_ids
    assert "src/services/paymentService.js" in node_ids
    assert "src/routes/paymentRoutes.js" in node_ids
    assert "src/app.js" in node_ids
    assert "src/utils/standaloneHelper.js" in node_ids

    # 2. Check canonical edge direction: Caller/Dependent -> Dependency
    edge_pairs = {(e.source, e.target) for e in edges}
    assert ("src/services/paymentService.js", "src/database/database.js") in edge_pairs
    assert ("src/routes/paymentRoutes.js", "src/services/paymentService.js") in edge_pairs
    assert ("src/app.js", "src/routes/paymentRoutes.js") in edge_pairs

    # Verify edge direction is NOT inverted
    assert ("src/database/database.js", "src/services/paymentService.js") not in edge_pairs

    # 3. Check external packages are excluded from edges
    external_specifiers = {i.raw_specifier for i in all_imports if i.is_external}
    assert "axios" in external_specifiers
    assert "express" in external_specifiers
    for edge in edges:
        assert edge.target not in ("axios", "express")

    # 4. Check unresolved imports are captured but excluded from edges
    unresolved_imports = [i for i in all_imports if not i.is_external and not i.is_resolved]
    assert len(unresolved_imports) >= 1
    assert any(u.raw_specifier == "./nonExistentFile.js" for u in unresolved_imports)
    for edge in edges:
        assert "nonExistentFile.js" not in edge.target
