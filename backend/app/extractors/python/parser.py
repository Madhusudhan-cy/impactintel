import ast
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set

from app.core.config import IGNORED_DIRECTORIES
from app.graph.schema import (
    Node,
    NodeType,
    DependencyEdge,
    RelationType,
    ExtractedImport,
    ExtractedSymbol,
    ExtractedCall
)


class PythonExtractor:
    """
    Syntax-aware code extractor for Python source files using Python AST.
    Extracts fine-grained entities:
        - Files, Functions, Classes, Methods, FastAPI Routes, Pytest Tests
    Extracts relationships:
        - imports (File ➔ File)
        - defines (File ➔ Symbol, Class ➔ Method)
        - calls (Caller ➔ Callee)
        - handled_by (ApiRoute ➔ Handler)
        - tests (Test ➔ Tested Function)
    """

    SUPPORTED_EXTENSIONS = {".py"}

    def extract_file(
        self,
        file_path: Path,
        repo_root: Path
    ) -> Tuple[List[Node], List[DependencyEdge], List[ExtractedImport], List[ExtractedCall]]:
        repo_root = repo_root.resolve()
        file_path = file_path.resolve()
        rel_path = file_path.relative_to(repo_root).as_posix()

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return [], [], [], []

        nodes: List[Node] = []
        edges: List[DependencyEdge] = []
        imports: List[ExtractedImport] = []
        calls: List[ExtractedCall] = []

        is_test_file = "test" in file_path.name.lower() or "tests" in file_path.parts
        file_node_type = NodeType.TEST if is_test_file else NodeType.FILE

        file_node = Node(
            id=rel_path,
            type=file_node_type,
            path=rel_path,
            name=rel_path,
            language="python",
            metadata={"size_bytes": len(content.encode("utf-8"))}
        )
        nodes.append(file_node)

        local_symbols: Dict[str, ExtractedSymbol] = {}
        # imported_name -> (target_file_rel_path, original_symbol_name)
        imported_symbols: Dict[str, Tuple[Optional[str], str]] = {}
        fastapi_routes: List[Tuple[str, str, str, int]] = []  # (method, path, func_name, line)

        # 1. First Pass: Collect Imports
        for stmt in tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    imp_name = alias.name
                    as_name = alias.asname or imp_name
                    # Try resolving relative to repo
                    resolved = self._resolve_python_module(imp_name, file_path, repo_root)
                    is_ext = resolved is None
                    imports.append(
                        ExtractedImport(
                            source_file=rel_path,
                            raw_specifier=imp_name,
                            resolved_path=resolved,
                            line_number=stmt.lineno,
                            statement=f"import {imp_name}",
                            is_external=is_ext,
                            is_resolved=not is_ext,
                            default_import=as_name
                        )
                    )
                    if resolved:
                        imported_symbols[as_name] = (resolved, imp_name)

            elif isinstance(stmt, ast.ImportFrom):
                module = stmt.module or ""
                resolved = self._resolve_python_module(module, file_path, repo_root, level=stmt.level)
                is_ext = resolved is None
                imported_names = [alias.name for alias in stmt.names]
                imports.append(
                    ExtractedImport(
                        source_file=rel_path,
                        raw_specifier=f"from {module} import {', '.join(imported_names)}",
                        resolved_path=resolved,
                        line_number=stmt.lineno,
                        statement=f"from {module} import {', '.join(imported_names)}",
                        is_external=is_ext,
                        is_resolved=not is_ext,
                        imported_symbols=imported_names
                    )
                )
                if resolved:
                    for alias in stmt.names:
                        as_name = alias.asname or alias.name
                        imported_symbols[as_name] = (resolved, alias.name)

        # 2. Second Pass: Extract Functions, Classes, and Methods
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = stmt.name
                is_test_func = func_name.startswith("test_") or is_test_file
                sym_type = NodeType.TEST if is_test_func else NodeType.FUNCTION

                func_node = Node(
                    id=f"{rel_path}::{func_name}",
                    type=sym_type,
                    path=rel_path,
                    name=func_name,
                    language="python"
                )
                nodes.append(func_node)
                local_symbols[func_name] = ExtractedSymbol(
                    name=func_name,
                    symbol_type=sym_type,
                    file_path=rel_path,
                    start_line=stmt.lineno,
                    end_line=getattr(stmt, "end_lineno", stmt.lineno)
                )

                # defines edge
                edges.append(
                    DependencyEdge(
                        source=rel_path,
                        target=func_node.id,
                        type=RelationType.DEFINES,
                        file=rel_path,
                        line=stmt.lineno,
                        statement=f"def {func_name}()"
                    )
                )

                # Check FastAPI decorators: e.g. @app.get("/api/...")
                for dec in stmt.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        method = dec.func.attr.upper()
                        if method in ("GET", "POST", "PUT", "DELETE", "PATCH") and dec.args:
                            first_arg = dec.args[0]
                            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                                route_path = first_arg.value
                                fastapi_routes.append((method, route_path, func_name, dec.lineno))

            elif isinstance(stmt, ast.ClassDef):
                cls_name = stmt.name
                cls_node = Node.create_class(rel_path, cls_name, language="python")
                nodes.append(cls_node)
                local_symbols[cls_name] = ExtractedSymbol(
                    name=cls_name,
                    symbol_type=NodeType.CLASS,
                    file_path=rel_path,
                    start_line=stmt.lineno,
                    end_line=getattr(stmt, "end_lineno", stmt.lineno)
                )

                edges.append(
                    DependencyEdge(
                        source=rel_path,
                        target=cls_node.id,
                        type=RelationType.DEFINES,
                        file=rel_path,
                        line=stmt.lineno,
                        statement=f"class {cls_name}:"
                    )
                )

                # Methods inside class
                for item in stmt.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = item.name
                        method_node_id = f"{rel_path}::{cls_name}.{method_name}"
                        method_node = Node(
                            id=method_node_id,
                            type=NodeType.FUNCTION,
                            path=rel_path,
                            name=f"{cls_name}.{method_name}",
                            language="python"
                        )
                        nodes.append(method_node)
                        local_symbols[f"{cls_name}.{method_name}"] = ExtractedSymbol(
                            name=method_name,
                            symbol_type=NodeType.FUNCTION,
                            file_path=rel_path,
                            start_line=item.lineno,
                            end_line=getattr(item, "end_lineno", item.lineno),
                            scope=cls_name
                        )

                        edges.append(
                            DependencyEdge(
                                source=cls_node.id,
                                target=method_node.id,
                                type=RelationType.DEFINES,
                                file=rel_path,
                                line=item.lineno,
                                statement=f"def {method_name}(self):"
                            )
                        )

        # 3. Third Pass: Extract Calls inside Function and Method bodies
        class CallVisitor(ast.NodeVisitor):
            def __init__(self, caller_symbol: str, parent_class: Optional[str] = None):
                self.caller_symbol = caller_symbol
                self.parent_class = parent_class

            def visit_Call(self, node: ast.Call):
                callee_name = None
                if isinstance(node.func, ast.Name):
                    callee_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        callee_name = f"{node.func.value.id}.{node.func.attr}"

                if callee_name:
                    calls.append(
                        ExtractedCall(
                            caller_file=rel_path,
                            caller_symbol=self.caller_symbol,
                            callee_name=callee_name,
                            line_number=node.lineno,
                            statement=f"{callee_name}()"
                        )
                    )
                self.generic_visit(node)

        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                CallVisitor(stmt.name).visit(stmt)
            elif isinstance(stmt, ast.ClassDef):
                for item in stmt.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        CallVisitor(f"{stmt.name}.{item.name}", parent_class=stmt.name).visit(item)

        # 4. Resolve FastAPI Routes -> handled_by edges
        for method, route_path, func_name, line_no in fastapi_routes:
            route_node = Node.create_api_route(
                method,
                route_path,
                rel_path,
                language="python",
                metadata={"start_line": line_no, "end_line": line_no, "statement": f"@{method.lower()}('{route_path}')"}
            )
            nodes.append(route_node)
            handler_id = f"{rel_path}::{func_name}"
            edges.append(
                DependencyEdge(
                    source=route_node.id,
                    target=handler_id,
                    type=RelationType.HANDLED_BY,
                    file=rel_path,
                    line=line_no,
                    statement=f"@{method.lower()}('{route_path}')"
                )
            )

        # 5. Resolve Function Calls -> calls / tests edges
        for call in calls:
            caller_name = call.caller_symbol
            if not caller_name:
                continue

            caller_id = f"{rel_path}::{caller_name}"
            callee_str = call.callee_name
            target_id = None

            # a) self.method() call inside class
            if callee_str.startswith("self.") and "." in caller_name:
                parent_cls = caller_name.split(".")[0]
                method_name = callee_str.split("self.", 1)[1]
                target_id = f"{rel_path}::{parent_cls}.{method_name}"

            # b) direct local function call
            elif callee_str in local_symbols:
                target_id = local_symbols[callee_str].node_id

            # c) imported symbol call
            elif callee_str in imported_symbols:
                target_file, orig_name = imported_symbols[callee_str]
                if target_file:
                    target_id = f"{target_file}::{orig_name}"

            # d) module.func call
            elif "." in callee_str:
                mod_name, func_name = callee_str.split(".", 1)
                if mod_name in imported_symbols:
                    target_file, _ = imported_symbols[mod_name]
                    if target_file:
                        target_id = f"{target_file}::{func_name}"

            if target_id and target_id != caller_id:
                call.resolved_target_id = target_id
                call.is_resolved = True

                edge_type = RelationType.TESTS if is_test_file or caller_name.startswith("test_") else RelationType.CALLS
                edges.append(
                    DependencyEdge(
                        source=caller_id,
                        target=target_id,
                        type=edge_type,
                        file=rel_path,
                        line=call.line_number,
                        statement=call.statement
                    )
                )

        return nodes, edges, imports, calls

    def _resolve_python_module(
        self,
        module_name: str,
        current_file: Path,
        repo_root: Path,
        level: int = 0
    ) -> Optional[str]:
        """Resolve python module import to repository-relative file path."""
        if level > 0:
            # Relative import, e.g. from . import database or from ..services import payment
            target_dir = current_file.parent
            for _ in range(level - 1):
                target_dir = target_dir.parent
            parts = module_name.split(".") if module_name else []
            candidate_file = target_dir.joinpath(*parts).with_suffix(".py")
            if candidate_file.is_file():
                try:
                    return candidate_file.relative_to(repo_root).as_posix()
                except ValueError:
                    return None
            candidate_pkg = target_dir.joinpath(*parts, "__init__.py")
            if candidate_pkg.is_file():
                try:
                    return candidate_pkg.relative_to(repo_root).as_posix()
                except ValueError:
                    return None
            return None

        # Absolute import inside repository (e.g. app.database or services.payment)
        parts = module_name.split(".")
        candidate_file = repo_root.joinpath(*parts).with_suffix(".py")
        if candidate_file.is_file():
            return candidate_file.relative_to(repo_root).as_posix()
        candidate_pkg = repo_root.joinpath(*parts, "__init__.py")
        if candidate_pkg.is_file():
            return candidate_pkg.relative_to(repo_root).as_posix()

        # External package (e.g. os, sys, fastapi, sqlalchemy)
        return None

    def extract_repository(
        self,
        repo_root: Path
    ) -> Tuple[List[Node], List[DependencyEdge], List[ExtractedImport]]:
        repo_root = repo_root.resolve()
        all_nodes: List[Node] = []
        all_edges: List[DependencyEdge] = []
        all_imports: List[ExtractedImport] = []

        for path in repo_root.rglob("*.py"):
            if not path.is_file():
                continue
            if any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue

            file_nodes, file_edges, file_imports, _ = self.extract_file(path, repo_root)
            all_nodes.extend(file_nodes)
            all_edges.extend(file_edges)
            all_imports.extend(file_imports)

            rel_path = path.relative_to(repo_root).as_posix()
            for imp in file_imports:
                if imp.is_resolved and imp.resolved_path:
                    all_edges.append(
                        DependencyEdge(
                            source=rel_path,
                            target=imp.resolved_path,
                            type=RelationType.IMPORTS,
                            file=rel_path,
                            line=imp.line_number,
                            statement=imp.statement
                        )
                    )

        unique_nodes: Dict[str, Node] = {n.id: n for n in all_nodes}
        return list(unique_nodes.values()), all_edges, all_imports
