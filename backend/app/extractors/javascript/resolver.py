from pathlib import Path
from typing import Optional, Tuple
from app.core.config import SUPPORTED_JS_TS_EXTENSIONS


def is_relative_import(specifier: str) -> bool:
    """Check if the import specifier points to a relative internal path."""
    return specifier.startswith("./") or specifier.startswith("../") or specifier == "." or specifier == ".."


def resolve_import_path(
    specifier: str,
    current_file_path: Path,
    repo_root: Path
) -> Tuple[Optional[str], bool, bool]:
    """
    Resolve an import specifier to a repository-relative file path.

    Returns:
        (resolved_path, is_external, is_resolved)
        - resolved_path: relative path from repo_root (e.g. 'src/database/database.js') or None
        - is_external: True if third-party package (e.g. 'express', 'axios')
        - is_resolved: True if internal relative import matched a real file on disk
    """
    cleaned_specifier = specifier.strip("'\"` \t\r\n")

    # If it is not a relative import, treat it as an external package
    if not is_relative_import(cleaned_specifier):
        return None, True, False

    # Compute target candidate path based on current file's parent folder
    base_dir = current_file_path.parent
    candidate = (base_dir / cleaned_specifier).resolve()

    # 1. Exact match (e.g., './database.js' with extension provided)
    if candidate.is_file():
        try:
            rel = candidate.relative_to(repo_root.resolve()).as_posix()
            return rel, False, True
        except ValueError:
            return None, False, False

    # 2. Match with supported extensions (e.g. './database' -> './database.js')
    for ext in SUPPORTED_JS_TS_EXTENSIONS:
        ext_candidate = candidate.with_name(candidate.name + ext)
        if ext_candidate.is_file():
            try:
                rel = ext_candidate.relative_to(repo_root.resolve()).as_posix()
                return rel, False, True
            except ValueError:
                return None, False, False

    # 3. Directory index resolution (e.g. './services' -> './services/index.js')
    if candidate.is_dir():
        for ext in SUPPORTED_JS_TS_EXTENSIONS:
            index_candidate = candidate / f"index{ext}"
            if index_candidate.is_file():
                try:
                    rel = index_candidate.relative_to(repo_root.resolve()).as_posix()
                    return rel, False, True
                except ValueError:
                    return None, False, False

    # Could not resolve to any real internal file
    return None, False, False
