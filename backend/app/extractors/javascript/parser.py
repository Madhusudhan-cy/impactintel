from pathlib import Path
from typing import List, Tuple
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from app.core.config import SUPPORTED_JS_TS_EXTENSIONS, IGNORED_DIRECTORIES
from app.extractors.base import BaseExtractor
from app.extractors.javascript.resolver import resolve_import_path
from app.graph.schema import Node, NodeType, DependencyEdge, RelationType, ExtractedImport


class JavaScriptExtractor(BaseExtractor):
    """
    Syntax-aware extractor using Tree-sitter for JavaScript and TypeScript repositories.
    Extracts file-level import relationships while maintaining precise source line evidence.
    """

    def __init__(self):
        # Initialize Tree-sitter languages and parsers
        self.js_lang = Language(tsjs.language())
        self.ts_lang = Language(tsts.language_typescript())
        self.tsx_lang = Language(tsts.language_tsx())

        self.js_parser = Parser(self.js_lang)
        self.ts_parser = Parser(self.ts_lang)
        self.tsx_parser = Parser(self.tsx_lang)

    def _get_parser_and_language(self, file_path: Path) -> Tuple[Parser, str]:
        suffix = file_path.suffix.lower()
        if suffix == ".tsx":
            return self.tsx_parser, "typescript"
        elif suffix == ".ts":
            return self.ts_parser, "typescript"
        return self.js_parser, "javascript"

    def extract_file(self, file_path: Path, repo_root: Path) -> List[ExtractedImport]:
        """Parse a single file and return all extracted import records."""
        repo_root = repo_root.resolve()
        file_path = file_path.resolve()
        source_rel_path = file_path.relative_to(repo_root).as_posix()

        try:
            content = file_path.read_bytes()
        except Exception:
            return []

        parser, _ = self._get_parser_and_language(file_path)
        tree = parser.parse(content)

        extracted: List[ExtractedImport] = []

        def visit_node(node):
            # 1. import statement: import ... from '...'; or import '...';
            if node.type == "import_statement":
                source_node = node.child_by_field_name("source")
                if source_node:
                    raw_specifier = source_node.text.decode("utf-8", errors="ignore").strip("\"'`")
                    line_no = node.start_point[0] + 1
                    stmt_text = node.text.decode("utf-8", errors="ignore").strip()
                    resolved_path, is_ext, is_res = resolve_import_path(raw_specifier, file_path, repo_root)
                    extracted.append(
                        ExtractedImport(
                            source_file=source_rel_path,
                            raw_specifier=raw_specifier,
                            resolved_path=resolved_path,
                            line_number=line_no,
                            statement=stmt_text,
                            is_external=is_ext,
                            is_resolved=is_res
                        )
                    )
                else:
                    # Side-effect import: import './init.js';
                    for child in node.children:
                        if child.type == "string":
                            raw_specifier = child.text.decode("utf-8", errors="ignore").strip("\"'`")
                            line_no = node.start_point[0] + 1
                            stmt_text = node.text.decode("utf-8", errors="ignore").strip()
                            resolved_path, is_ext, is_res = resolve_import_path(raw_specifier, file_path, repo_root)
                            extracted.append(
                                ExtractedImport(
                                    source_file=source_rel_path,
                                    raw_specifier=raw_specifier,
                                    resolved_path=resolved_path,
                                    line_number=line_no,
                                    statement=stmt_text,
                                    is_external=is_ext,
                                    is_resolved=is_res
                                )
                            )

            # 2. export statement: export ... from '...';
            elif node.type == "export_statement":
                source_node = node.child_by_field_name("source")
                if source_node:
                    raw_specifier = source_node.text.decode("utf-8", errors="ignore").strip("\"'`")
                    line_no = node.start_point[0] + 1
                    stmt_text = node.text.decode("utf-8", errors="ignore").strip()
                    resolved_path, is_ext, is_res = resolve_import_path(raw_specifier, file_path, repo_root)
                    extracted.append(
                        ExtractedImport(
                            source_file=source_rel_path,
                            raw_specifier=raw_specifier,
                            resolved_path=resolved_path,
                            line_number=line_no,
                            statement=stmt_text,
                            is_external=is_ext,
                            is_resolved=is_res
                        )
                    )

            # 3. call expression: require('...') or dynamic import('...')
            elif node.type == "call_expression":
                func = node.child_by_field_name("function")
                args = node.child_by_field_name("arguments")
                if func and args:
                    func_name = func.text.decode("utf-8", errors="ignore")
                    if func_name in ("require", "import") and len(args.named_children) > 0:
                        first_arg = args.named_children[0]
                        if first_arg.type == "string":
                            raw_specifier = first_arg.text.decode("utf-8", errors="ignore").strip("\"'`")
                            line_no = node.start_point[0] + 1
                            stmt_text = node.text.decode("utf-8", errors="ignore").strip()
                            resolved_path, is_ext, is_res = resolve_import_path(raw_specifier, file_path, repo_root)
                            extracted.append(
                                ExtractedImport(
                                    source_file=source_rel_path,
                                    raw_specifier=raw_specifier,
                                    resolved_path=resolved_path,
                                    line_number=line_no,
                                    statement=stmt_text,
                                    is_external=is_ext,
                                    is_resolved=is_res
                                )
                            )

            for child in node.children:
                visit_node(child)

        visit_node(tree.root_node)
        return extracted

    def extract_repository(self, repo_root: Path) -> Tuple[List[Node], List[DependencyEdge], List[ExtractedImport]]:
        """
        Scan repository, discover all supported JS/TS files, extract all import dependencies,
        and construct normalized Node and DependencyEdge representations.
        """
        repo_root = repo_root.resolve()
        nodes: List[Node] = []
        edges: List[DependencyEdge] = []
        all_imports: List[ExtractedImport] = []

        # 1. Discover all JS/TS files in repository
        source_files: List[Path] = []
        for path in repo_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_JS_TS_EXTENSIONS:
                continue
            # Check ignored directories in path parts
            if any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue
            source_files.append(path)

        # 2. Create normalized File nodes
        for file_path in source_files:
            rel_path = file_path.relative_to(repo_root).as_posix()
            _, lang = self._get_parser_and_language(file_path)
            node_type = NodeType.TEST if "test" in file_path.name.lower() or "tests" in file_path.parts else NodeType.FILE
            nodes.append(
                Node(
                    id=rel_path,
                    type=node_type,
                    path=rel_path,
                    language=lang,
                    metadata={"size_bytes": file_path.stat().st_size}
                )
            )

        # 3. Extract imports from each file and build DependencyEdge instances
        for file_path in source_files:
            file_imports = self.extract_file(file_path, repo_root)
            all_imports.extend(file_imports)

            for imp in file_imports:
                # Only internal resolved imports become graph edges
                if imp.is_resolved and imp.resolved_path:
                    edge = DependencyEdge(
                        source=imp.source_file,
                        target=imp.resolved_path,
                        type=RelationType.IMPORTS,
                        file=imp.source_file,
                        line=imp.line_number,
                        statement=imp.statement,
                        confidence=1.0,
                        extractor="tree_sitter"
                    )
                    edges.append(edge)

        return nodes, edges, all_imports
