from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from app.core.config import SUPPORTED_JS_TS_EXTENSIONS, IGNORED_DIRECTORIES
from app.extractors.javascript.resolver import resolve_import_path
from app.graph.schema import (
    Node,
    NodeType,
    DependencyEdge,
    RelationType,
    ExtractedImport,
    ExtractedSymbol,
    ExtractedCall
)


class AdvancedJavaScriptExtractor:
    """
    Advanced syntax-aware code extractor for JavaScript, TypeScript, and JSX/TSX.
    Extracts fine-grained entities:
        - Files, Functions, Classes, React Components, API Routes, Tests
    Extracts fine-grained relationships:
        - imports (File ➔ File)
        - defines (File ➔ Symbol, Class ➔ Method)
        - calls (Caller ➔ Callee)
        - renders (Component ➔ Rendered Component)
        - handled_by (ApiRoute ➔ Controller/Handler)
        - fetches (Frontend Caller ➔ ApiRoute)
        - tests (Test ➔ Tested Function/Component)
    """

    def __init__(self):
        self.js_lang = Language(tsjs.language())
        self.ts_lang = Language(tsts.language_typescript())
        self.tsx_lang = Language(tsts.language_tsx())

        self.js_parser = Parser(self.js_lang)
        self.ts_parser = Parser(self.ts_lang)
        self.tsx_parser = Parser(self.tsx_lang)

    def _get_parser_and_language(self, file_path: Path) -> Tuple[Parser, str]:
        suffix = file_path.suffix.lower()
        if suffix in (".tsx", ".jsx"):
            return self.tsx_parser, "javascript"
        elif suffix == ".ts":
            return self.ts_parser, "typescript"
        return self.js_parser, "javascript"

    def extract_file(
        self,
        file_path: Path,
        repo_root: Path
    ) -> Tuple[List[Node], List[DependencyEdge], List[ExtractedImport], List[ExtractedCall]]:
        """
        Parse a single file and extract all symbols, imports, and intra-file relationships.
        """
        repo_root = repo_root.resolve()
        file_path = file_path.resolve()
        rel_path = file_path.relative_to(repo_root).as_posix()

        try:
            content = file_path.read_bytes()
        except Exception:
            return [], [], [], []

        parser, lang = self._get_parser_and_language(file_path)
        tree = parser.parse(content)

        nodes: List[Node] = []
        edges: List[DependencyEdge] = []
        imports: List[ExtractedImport] = []
        calls: List[ExtractedCall] = []

        # 1. Base File Node
        is_test_file = "test" in file_path.name.lower() or "tests" in file_path.parts
        file_node_type = NodeType.TEST if is_test_file else NodeType.FILE
        file_node = Node(
            id=rel_path,
            type=file_node_type,
            path=rel_path,
            name=rel_path,
            language=lang,
            metadata={"size_bytes": len(content)}
        )
        nodes.append(file_node)

        # Discovered symbols in this file: name -> ExtractedSymbol
        local_symbols: Dict[str, ExtractedSymbol] = {}
        # Imported symbols in this file: imported_identifier -> target_file_rel_path
        imported_symbols: Dict[str, str] = {}
        # JSX renders: list of (parent_symbol, child_component_tag, line, statement)
        jsx_renders: List[Tuple[str, str, int, str]] = []
        # Express route definitions: list of (method, path, handler_name, line, statement)
        express_routes: List[Tuple[str, str, str, int, str]] = []
        # Fetch calls: list of (caller_symbol, method, url, line, statement)
        fetch_calls: List[Tuple[str, str, str, int, str]] = []
        # Tests: list of (test_name, line, statement, test_node_id)
        test_definitions: List[Tuple[str, int, str, str]] = []

        # Current traversal context
        current_scope_stack: List[Tuple[str, str]] = []  # [(symbol_name, symbol_type)]

        def get_current_caller() -> Optional[str]:
            if current_scope_stack:
                return current_scope_stack[-1][0]
            return None

        def visit(node):
            nonlocal imports, calls, local_symbols, imported_symbols, jsx_renders, express_routes, fetch_calls, test_definitions

            node_type = node.type

            # A. IMPORTS
            if node_type in ("import_statement", "export_statement"):
                source_node = node.child_by_field_name("source")
                if source_node:
                    raw_specifier = source_node.text.decode("utf-8", errors="ignore").strip("\"'`")
                    line_no = node.start_point[0] + 1
                    stmt_text = node.text.decode("utf-8", errors="ignore").strip()
                    resolved_path, is_ext, is_res = resolve_import_path(raw_specifier, file_path, repo_root)

                    # Inspect imported identifiers
                    imported_names = []
                    default_name = None
                    is_ns = False
                    ns_alias = None

                    import_clause = None
                    for child in node.children:
                        if child.type == "import_clause":
                            import_clause = child
                            break

                    if import_clause:
                        for child in import_clause.children:
                            if child.type == "identifier":
                                default_name = child.text.decode("utf-8", errors="ignore")
                            elif child.type == "named_imports":
                                for spec in child.children:
                                    if spec.type == "import_specifier":
                                        name_node = spec.child_by_field_name("name") or spec
                                        imported_names.append(name_node.text.decode("utf-8", errors="ignore"))
                            elif child.type == "namespace_import":
                                is_ns = True
                                for sub in child.children:
                                    if sub.type == "identifier":
                                        ns_alias = sub.text.decode("utf-8", errors="ignore")

                    imp_obj = ExtractedImport(
                        source_file=rel_path,
                        raw_specifier=raw_specifier,
                        resolved_path=resolved_path,
                        line_number=line_no,
                        statement=stmt_text,
                        is_external=is_ext,
                        is_resolved=is_res,
                        imported_symbols=imported_names,
                        default_import=default_name,
                        is_namespace=is_ns,
                        namespace_alias=ns_alias
                    )
                    imports.append(imp_obj)

                    # Map imported symbols to target file
                    if is_res and resolved_path:
                        for sym in imported_names:
                            imported_symbols[sym] = resolved_path
                        if default_name:
                            imported_symbols[default_name] = resolved_path
                        if ns_alias:
                            imported_symbols[ns_alias] = resolved_path

            # B. CLASS DECLARATIONS
            elif node_type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    class_name = name_node.text.decode("utf-8", errors="ignore")
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    class_sym = ExtractedSymbol(
                        name=class_name,
                        symbol_type=NodeType.CLASS,
                        file_path=rel_path,
                        start_line=start_line,
                        end_line=end_line
                    )
                    local_symbols[class_name] = class_sym

                    class_node = Node.create_class(rel_path, class_name, language=lang)
                    nodes.append(class_node)
                    # defines edge: File ➔ Class
                    edges.append(
                        DependencyEdge(
                            source=rel_path,
                            target=class_node.id,
                            type=RelationType.DEFINES,
                            file=rel_path,
                            line=start_line,
                            statement=f"class {class_name}"
                        )
                    )

                    current_scope_stack.append((class_name, "class"))
                    # Traverse class body
                    body = node.child_by_field_name("body")
                    if body:
                        for child in body.children:
                            visit(child)
                    current_scope_stack.pop()
                    return

            # C. METHOD DEFINITIONS (Inside Class)
            elif node_type == "method_definition":
                name_node = node.child_by_field_name("name")
                if name_node and current_scope_stack and current_scope_stack[-1][1] == "class":
                    parent_class = current_scope_stack[-1][0]
                    method_name = name_node.text.decode("utf-8", errors="ignore")
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1

                    method_sym = ExtractedSymbol(
                        name=method_name,
                        symbol_type=NodeType.FUNCTION,
                        file_path=rel_path,
                        start_line=start_line,
                        end_line=end_line,
                        scope=parent_class
                    )
                    local_symbols[f"{parent_class}.{method_name}"] = method_sym
                    method_node_id = f"{rel_path}::{parent_class}.{method_name}"
                    method_node = Node(
                        id=method_node_id,
                        type=NodeType.FUNCTION,
                        path=rel_path,
                        name=f"{parent_class}.{method_name}",
                        language=lang
                    )
                    nodes.append(method_node)

                    # defines edge: Class ➔ Method
                    edges.append(
                        DependencyEdge(
                            source=f"{rel_path}::{parent_class}",
                            target=method_node_id,
                            type=RelationType.DEFINES,
                            file=rel_path,
                            line=start_line,
                            statement=f"{method_name}()"
                        )
                    )

                    current_scope_stack.append((f"{parent_class}.{method_name}", "method"))
                    for child in node.children:
                        if child != name_node:
                            visit(child)
                    current_scope_stack.pop()
                    return

            # D. FUNCTION DECLARATIONS & ARROW FUNCTIONS
            elif node_type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    func_name = name_node.text.decode("utf-8", errors="ignore")
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1

                    # Check if React component (PascalCase or returns JSX)
                    is_component = func_name[0].isupper() and not is_test_file
                    sym_type = NodeType.COMPONENT if is_component else NodeType.FUNCTION

                    sym = ExtractedSymbol(
                        name=func_name,
                        symbol_type=sym_type,
                        file_path=rel_path,
                        start_line=start_line,
                        end_line=end_line
                    )
                    local_symbols[func_name] = sym
                    func_node = Node(
                        id=f"{rel_path}::{func_name}",
                        type=sym_type,
                        path=rel_path,
                        name=func_name,
                        language=lang
                    )
                    nodes.append(func_node)

                    # defines edge: File ➔ Function/Component
                    edges.append(
                        DependencyEdge(
                            source=rel_path,
                            target=func_node.id,
                            type=RelationType.DEFINES,
                            file=rel_path,
                            line=start_line,
                            statement=f"function {func_name}()"
                        )
                    )

                    current_scope_stack.append((func_name, "function"))
                    for child in node.children:
                        if child != name_node:
                            visit(child)
                    current_scope_stack.pop()
                    return

            # Arrow function in variable declarator
            elif node_type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                value_node = node.child_by_field_name("value")
                if name_node and value_node and value_node.type in ("arrow_function", "function_expression"):
                    func_name = name_node.text.decode("utf-8", errors="ignore")
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1

                    is_component = func_name[0].isupper() and not is_test_file
                    sym_type = NodeType.COMPONENT if is_component else NodeType.FUNCTION

                    sym = ExtractedSymbol(
                        name=func_name,
                        symbol_type=sym_type,
                        file_path=rel_path,
                        start_line=start_line,
                        end_line=end_line
                    )
                    local_symbols[func_name] = sym
                    func_node = Node(
                        id=f"{rel_path}::{func_name}",
                        type=sym_type,
                        path=rel_path,
                        name=func_name,
                        language=lang
                    )
                    nodes.append(func_node)

                    edges.append(
                        DependencyEdge(
                            source=rel_path,
                            target=func_node.id,
                            type=RelationType.DEFINES,
                            file=rel_path,
                            line=start_line,
                            statement=f"const {func_name} = () =>"
                        )
                    )

                    current_scope_stack.append((func_name, "function"))
                    for child in value_node.children:
                        visit(child)
                    current_scope_stack.pop()
                    return

            # E. JEST / VITEST TESTS: test('...', () => { ... }) or it('...', () => { ... })
            elif node_type == "call_expression":
                func_child = node.child_by_field_name("function")
                args_child = node.child_by_field_name("arguments")
                if func_child and args_child:
                    func_name = func_child.text.decode("utf-8", errors="ignore")
                    line_no = node.start_point[0] + 1
                    stmt_snippet = node.text.decode("utf-8", errors="ignore").splitlines()[0][:80]

                    # 1. Test case definition
                    if func_name in ("test", "it") and len(args_child.named_children) >= 2:
                        first_arg = args_child.named_children[0]
                        if first_arg.type == "string":
                            test_desc = first_arg.text.decode("utf-8", errors="ignore").strip("\"'`")
                            test_node_id = f"{rel_path}::{test_desc}"
                            test_node = Node.create_test(rel_path, test_desc, language=lang)
                            nodes.append(test_node)

                            edges.append(
                                DependencyEdge(
                                    source=rel_path,
                                    target=test_node.id,
                                    type=RelationType.DEFINES,
                                    file=rel_path,
                                    line=line_no,
                                    statement=f"test('{test_desc}')"
                                )
                            )

                            current_scope_stack.append((test_desc, "test"))
                            callback_arg = args_child.named_children[1]
                            visit(callback_arg)
                            current_scope_stack.pop()
                            return

                    # 2. Express route: app.post('/api/...', handler) or router.get(...)
                    if func_child.type == "member_expression":
                        prop = func_child.child_by_field_name("property")
                        if prop and prop.text.decode("utf-8").lower() in ("get", "post", "put", "delete", "patch"):
                            method = prop.text.decode("utf-8").upper()
                            if len(args_child.named_children) >= 2:
                                route_arg = args_child.named_children[0]
                                handler_arg = args_child.named_children[1]
                                if route_arg.type == "string":
                                    route_path = route_arg.text.decode("utf-8").strip("\"'`")
                                    handler_name = handler_arg.text.decode("utf-8").strip()
                                    express_routes.append((method, route_path, handler_name, line_no, stmt_snippet))

                    # 3. Frontend HTTP fetch: fetch('/api/payment', { method: 'POST' })
                    if func_name == "fetch" and len(args_child.named_children) >= 1:
                        url_arg = args_child.named_children[0]
                        if url_arg.type == "string":
                            url_val = url_arg.text.decode("utf-8").strip("\"'`")
                            method_val = "GET"
                            if len(args_child.named_children) >= 2:
                                opts = args_child.named_children[1].text.decode("utf-8")
                                for m in ("POST", "PUT", "DELETE", "PATCH"):
                                    if m in opts.upper():
                                        method_val = m
                                        break
                            caller = get_current_caller() or rel_path
                            fetch_calls.append((caller, method_val, url_val, line_no, stmt_snippet))

                    # 4. Standard Function Call
                    caller = get_current_caller()
                    callee_repr = func_child.text.decode("utf-8", errors="ignore").strip()
                    calls.append(
                        ExtractedCall(
                            caller_file=rel_path,
                            caller_symbol=caller,
                            callee_name=callee_repr,
                            line_number=line_no,
                            statement=stmt_snippet
                        )
                    )

            # F. JSX RENDERING: <PaymentForm /> or <Checkout />
            elif node_type in ("jsx_self_closing_element", "jsx_opening_element"):
                for child in node.children:
                    if child.type == "identifier":
                        tag = child.text.decode("utf-8", errors="ignore")
                        # Component names in React start with an uppercase letter
                        if tag and tag[0].isupper():
                            caller = get_current_caller()
                            line_no = node.start_point[0] + 1
                            stmt_snippet = node.text.decode("utf-8", errors="ignore")[:60]
                            if caller:
                                jsx_renders.append((caller, tag, line_no, stmt_snippet))
                        break

            for child in node.children:
                visit(child)

        visit(tree.root_node)

        # ----------------------------------------------------
        # RESOLUTION PASS: Build fine-grained DependencyEdges
        # ----------------------------------------------------

        # 1. Resolve Express routes -> API Route nodes + handled_by edges
        for method, route_path, handler_name, line_no, stmt in express_routes:
            route_node = Node.create_api_route(
                method,
                route_path,
                rel_path,
                language=lang,
                metadata={"start_line": line_no, "end_line": line_no, "statement": stmt}
            )
            nodes.append(route_node)

            # Resolve handler
            handler_target_id = None
            if handler_name in local_symbols:
                handler_target_id = local_symbols[handler_name].node_id
            elif handler_name in imported_symbols:
                target_file = imported_symbols[handler_name]
                handler_target_id = f"{target_file}::{handler_name}"
            elif "." in handler_name:
                obj_part, method_part = handler_name.split(".", 1)
                if obj_part in imported_symbols:
                    target_file = imported_symbols[obj_part]
                    handler_target_id = f"{target_file}::{method_part}"

            if handler_target_id:
                edges.append(
                    DependencyEdge(
                        source=route_node.id,
                        target=handler_target_id,
                        type=RelationType.HANDLED_BY,
                        file=rel_path,
                        line=line_no,
                        statement=stmt
                    )
                )

        # 2. Resolve JSX renders -> renders edges (Component ➔ Child Component)
        for parent_comp, child_tag, line_no, stmt in jsx_renders:
            parent_id = f"{rel_path}::{parent_comp}"
            target_id = None
            if child_tag in local_symbols:
                target_id = local_symbols[child_tag].node_id
            elif child_tag in imported_symbols:
                target_file = imported_symbols[child_tag]
                target_id = f"{target_file}::{child_tag}"

            if target_id:
                edges.append(
                    DependencyEdge(
                        source=parent_id,
                        target=target_id,
                        type=RelationType.RENDERS,
                        file=rel_path,
                        line=line_no,
                        statement=stmt
                    )
                )

        # 3. Resolve Function Calls -> calls / tests edges
        for call in calls:
            caller_name = call.caller_symbol
            if not caller_name:
                continue

            caller_id = f"{rel_path}::{caller_name}"
            callee_str = call.callee_name
            target_id = None

            # a) this.method() call inside class
            if callee_str.startswith("this.") and "." in caller_name:
                parent_cls = caller_name.split(".")[0]
                method_name = callee_str.split("this.", 1)[1]
                target_id = f"{rel_path}::{parent_cls}.{method_name}"

            # b) direct local call
            elif callee_str in local_symbols:
                target_id = local_symbols[callee_str].node_id

            # c) imported call
            elif callee_str in imported_symbols:
                target_file = imported_symbols[callee_str]
                target_id = f"{target_file}::{callee_str}"

            # d) member call on imported object, e.g. dbConnection.query
            elif "." in callee_str:
                obj_part, method_part = callee_str.split(".", 1)
                if obj_part in imported_symbols:
                    target_file = imported_symbols[obj_part]
                    target_id = f"{target_file}::{method_part}"

            if target_id and target_id != caller_id:
                call.resolved_target_id = target_id
                call.is_resolved = True

                # Determine edge type: tests if inside a test, else calls
                edge_type = RelationType.TESTS if is_test_file or "::test" in caller_id.lower() else RelationType.CALLS
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

    def extract_repository(
        self,
        repo_root: Path
    ) -> Tuple[List[Node], List[DependencyEdge], List[ExtractedImport]]:
        """
        Scan repository, discover all supported JS/TS files, and extract full graph
        including file-level, function-level, class-level, component-level, and test-level entities.
        """
        repo_root = repo_root.resolve()
        all_nodes: List[Node] = []
        all_edges: List[DependencyEdge] = []
        all_imports: List[ExtractedImport] = []

        source_files: List[Path] = []
        for path in repo_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_JS_TS_EXTENSIONS:
                continue
            if any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue
            source_files.append(path)

        for file_path in source_files:
            file_nodes, file_edges, file_imports, _ = self.extract_file(file_path, repo_root)
            all_nodes.extend(file_nodes)
            all_edges.extend(file_edges)
            all_imports.extend(file_imports)

            # Preserve canonical file-level imports edge
            rel_path = file_path.relative_to(repo_root).as_posix()
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

        # De-duplicate nodes by ID
        unique_nodes: Dict[str, Node] = {}
        for n in all_nodes:
            if n.id not in unique_nodes:
                unique_nodes[n.id] = n

        return list(unique_nodes.values()), all_edges, all_imports
