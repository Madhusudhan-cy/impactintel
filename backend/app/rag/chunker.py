import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.graph.schema import Node, NodeType
from app.extractors.unified import MultiLanguageExtractor


class CodeChunk(BaseModel):
    """
    Normalized code chunk for conversational retrieval (Vector, BM25, and Graph RAG).
    Aligned with AST semantic boundaries (functions, classes, components, files).
    """
    chunk_id: str
    repository_id: int
    file_path: str
    language: str
    symbol_name: Optional[str] = None
    symbol_type: str = "File"
    start_line: int
    end_line: int
    content: str
    commit_sha: str = "HEAD"
    associated_node_id: Optional[str] = None
    parent_file: str
    imports: List[str] = Field(default_factory=list)
    extractor: str = "ast"


class CodeChunker:
    """
    Semantic AST-aligned code chunker.
    Extracts meaningful units (functions, methods, classes, components, files)
    instead of arbitrary fixed-token splits.
    """

    def __init__(self, extractor: Optional[MultiLanguageExtractor] = None):
        self.extractor = extractor or MultiLanguageExtractor()

    def chunk_file(
        self,
        file_path: Path,
        repo_root: Path,
        repository_id: int = 1,
        commit_sha: str = "HEAD"
    ) -> List[CodeChunk]:
        """Chunk a single file using AST semantic boundaries."""
        repo_root = Path(repo_root).resolve()
        file_path = Path(file_path).resolve()
        rel_path = file_path.relative_to(repo_root).as_posix()

        try:
            full_content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        lines = full_content.splitlines()
        chunks: List[CodeChunk] = []

        # Determine language and run appropriate AST extractor
        is_python = file_path.suffix.lower() == ".py"
        if is_python:
            nodes, edges, imports, calls = self.extractor.py_extractor.extract_file(file_path, repo_root)
            lang = "python"
        else:
            nodes, edges, imports, calls = self.extractor.js_extractor.extract_file(file_path, repo_root)
            lang = "typescript" if file_path.suffix.lower() in (".ts", ".tsx") else "javascript"

        imported_specifiers = [i.raw_specifier for i in imports]

        # 1. Generate semantic chunks for each discovered symbol (function, method, class, component)
        non_file_nodes = [n for n in nodes if n.type != NodeType.FILE]

        for node in non_file_nodes:
            # Check lines from metadata if present or search source
            start_line = node.metadata.get("start_line", 1)
            end_line = node.metadata.get("end_line", len(lines))

            # Bound checking
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            chunk_text = "\n".join(lines[start_idx:end_idx]).strip()
            if not chunk_text:
                continue

            chunk_hash = hashlib.sha256(f"{rel_path}:{node.id}:{start_line}:{end_line}".encode()).hexdigest()[:16]
            chunk_id = f"chunk_{repository_id}_{chunk_hash}"

            chunks.append(
                CodeChunk(
                    chunk_id=chunk_id,
                    repository_id=repository_id,
                    file_path=rel_path,
                    language=lang,
                    symbol_name=node.name,
                    symbol_type=node.type.value,
                    start_line=start_line,
                    end_line=end_line,
                    content=chunk_text,
                    commit_sha=commit_sha,
                    associated_node_id=node.id,
                    parent_file=rel_path,
                    imports=imported_specifiers,
                    extractor="tree_sitter" if not is_python else "python_ast"
                )
            )

            # Handle large functions or classes (> 80 lines) via overlapping semantic sub-windows
            total_symbol_lines = end_idx - start_idx
            if total_symbol_lines > 80:
                sub_window = 50
                overlap = 15
                step = sub_window - overlap
                for offset in range(0, total_symbol_lines, step):
                    sub_start = start_idx + offset
                    sub_end = min(end_idx, sub_start + sub_window)
                    sub_text = "\n".join(lines[sub_start:sub_end]).strip()
                    if not sub_text or sub_start >= end_idx:
                        break
                    sub_start_line = sub_start + 1
                    sub_end_line = sub_end
                    sub_hash = hashlib.sha256(f"{rel_path}:{node.id}:{sub_start_line}:{sub_end_line}".encode()).hexdigest()[:16]
                    chunks.append(
                        CodeChunk(
                            chunk_id=f"chunk_{repository_id}_{sub_hash}",
                            repository_id=repository_id,
                            file_path=rel_path,
                            language=lang,
                            symbol_name=f"{node.name} (L{sub_start_line}-{sub_end_line})",
                            symbol_type=node.type.value,
                            start_line=sub_start_line,
                            end_line=sub_end_line,
                            content=sub_text,
                            commit_sha=commit_sha,
                            associated_node_id=node.id,
                            parent_file=rel_path,
                            imports=imported_specifiers,
                            extractor="tree_sitter" if not is_python else "python_ast"
                        )
                    )

        # 2. Also generate file-level overview chunk
        file_hash = hashlib.sha256(f"{rel_path}:file:1:{len(lines)}".encode()).hexdigest()[:16]
        file_chunk_id = f"chunk_{repository_id}_{file_hash}"
        # Keep full content or top 100 lines for overview
        file_overview = "\n".join(lines[:100]).strip()
        chunks.append(
            CodeChunk(
                chunk_id=file_chunk_id,
                repository_id=repository_id,
                file_path=rel_path,
                language=lang,
                symbol_name=rel_path,
                symbol_type="File",
                start_line=1,
                end_line=len(lines),
                content=file_overview,
                commit_sha=commit_sha,
                associated_node_id=rel_path,
                parent_file=rel_path,
                imports=imported_specifiers,
                extractor="tree_sitter" if not is_python else "python_ast"
            )
        )

        return chunks

    def chunk_repository(
        self,
        repo_root: Path,
        repository_id: int = 1,
        commit_sha: str = "HEAD"
    ) -> List[CodeChunk]:
        """Scan and chunk all supported source files in the repository."""
        repo_root = Path(repo_root).resolve()
        all_chunks: List[CodeChunk] = []

        from app.core.config import SUPPORTED_JS_TS_EXTENSIONS, IGNORED_DIRECTORIES
        supported_exts = SUPPORTED_JS_TS_EXTENSIONS.union({".py"})

        for file_path in repo_root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in supported_exts:
                continue
            if any(part in IGNORED_DIRECTORIES for part in file_path.parts):
                continue

            file_chunks = self.chunk_file(file_path, repo_root, repository_id=repository_id, commit_sha=commit_sha)
            all_chunks.extend(file_chunks)

        return all_chunks
