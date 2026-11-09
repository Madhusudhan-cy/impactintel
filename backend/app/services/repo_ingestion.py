import logging
import os
import shutil
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional, Set

import httpx
from fastapi import HTTPException, status

from app.core.config import IGNORED_DIRECTORIES
from app.services.github_app import GitHubAppService

logger = logging.getLogger(__name__)

# Limits and safety constraints
DEFAULT_DOWNLOAD_TIMEOUT = 30.0  # seconds
MAX_ARCHIVE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB compressed archive limit
MAX_EXTRACTED_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB total uncompressed limit
MAX_FILE_COUNT = 5000  # Maximum number of files to extract

# Non-source / media / binary file extensions to exclude from extraction
IRRELEVANT_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav",
    ".zip", ".tar", ".gz", ".tgz", ".rar", ".7z", ".bz2",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".map", ".min.js.map", ".min.css.map"
}


@dataclass
class RemoteRepositoryContext:
    """Encapsulates retrieved remote repository details."""
    directory_path: Path
    branch: str
    commit_sha: str
    installation_id: Optional[int]


def safe_extract_tarball(
    tar_path: Path,
    dest_dir: Path,
    max_file_count: int = MAX_FILE_COUNT,
    max_extracted_size: int = MAX_EXTRACTED_SIZE_BYTES,
    ignored_dirs: Optional[Set[str]] = None,
    irrelevant_exts: Optional[Set[str]] = None
) -> int:
    """
    Safely extract a tarball into dest_dir with path traversal protection,
    exclusion of generated / irrelevant files, and file count / size limits.

    Returns the number of extracted regular files.
    """
    dest_resolved = dest_dir.resolve()
    ignored = ignored_dirs or IGNORED_DIRECTORIES
    irrelevant = irrelevant_exts or IRRELEVANT_EXTENSIONS

    total_extracted_bytes = 0
    file_count = 0

    with tarfile.open(tar_path, mode="r:*") as tar:
        for member in tar.getmembers():
            # 1. Skip non-regular files (reject symlinks, hardlinks, devices, fifos)
            if not (member.isreg() or member.isdir()):
                continue

            # 2. Strict directory traversal protection (Tar Slip prevention)
            member_path = Path(member.name)
            if ".." in member_path.parts:
                raise ValueError(f"Directory traversal detected in archive entry: {member.name}")

            target_path = (dest_resolved / member_path).resolve()
            if not target_path.is_relative_to(dest_resolved):
                raise ValueError(f"Path traversal detected: {member.name} resolves outside destination directory")

            # 3. Exclude generated and ignored directories (e.g. node_modules, dist, .git)
            # The top-level folder is typically owner-repo-sha; check all parts
            parts = member_path.parts
            sub_parts = parts[1:] if len(parts) > 1 else parts
            if any(p in ignored for p in sub_parts):
                continue

            # 4. Exclude irrelevant non-source file extensions
            name_lower = member.name.lower()
            if any(name_lower.endswith(ext) for ext in irrelevant):
                continue

            # 5. Check and enforce file count and size limits
            if member.isreg():
                file_count += 1
                if file_count > max_file_count:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Repository file count exceeds limit of {max_file_count} files"
                    )

                total_extracted_bytes += member.size
                if total_extracted_bytes > max_extracted_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Extracted repository size exceeds limit of {max_extracted_size // (1024 * 1024)}MB"
                    )

                # Extract file safely
                target_path.parent.mkdir(parents=True, exist_ok=True)
                source_f = tar.extractfile(member)
                if source_f:
                    with open(target_path, "wb") as out_f:
                        shutil.copyfileobj(source_f, out_f)
            elif member.isdir():
                target_path.mkdir(parents=True, exist_ok=True)

    return file_count


@contextmanager
def retrieve_remote_repository(
    owner: str,
    repo: str,
    branch: Optional[str] = "main",
    commit_sha: Optional[str] = "HEAD",
    github_service: Optional[GitHubAppService] = None,
    download_timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    max_archive_size: int = MAX_ARCHIVE_SIZE_BYTES,
    max_extracted_size: int = MAX_EXTRACTED_SIZE_BYTES,
    max_file_count: int = MAX_FILE_COUNT,
) -> Generator[RemoteRepositoryContext, None, None]:
    """
    Context manager to securely retrieve, validate, and extract a remote GitHub repository.
    Enforces GitHub App authorization, safe extraction, size limits, and automatic cleanup.
    """
    gh = github_service or GitHubAppService()
    full_name = f"{owner}/{repo}"

    # 1. Validate GitHub repository access through the authorized GitHub App
    token: Optional[str] = None
    installation_id: Optional[int] = None

    if gh.app_id and gh.private_key:
        try:
            installation_id = gh.get_repository_installation(owner, repo)
        except Exception as err:
            logger.error(f"Error checking GitHub App installation for {full_name}: {err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to verify GitHub App installation: {err}"
            )

        if not installation_id:
            logger.warning(f"GitHub App not authorized or installed on repository '{full_name}'")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"GitHub App is not authorized or installed on repository '{full_name}'. Please install the app on GitHub first."
            )

        try:
            token = gh.get_installation_access_token(installation_id)
        except Exception as err:
            logger.error(f"Failed to obtain installation token for {full_name}: {err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to obtain GitHub App installation token: {err}"
            )
    else:
        # If GitHub App is not configured, verify repository exists via public GitHub API
        try:
            gh.get_repository(owner, repo)
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Repository '{full_name}' was not found on GitHub."
                )
            raise HTTPException(
                status_code=err.response.status_code,
                detail=f"GitHub repository check failed: {err}"
            )
        except Exception as err:
            logger.warning(f"Could not verify public repository metadata ({err}); proceeding with download attempt")

    # 2. Track exact repository branch and commit SHA
    target_branch = branch if branch and branch != "HEAD" else "main"
    if not branch or branch == "HEAD":
        try:
            repo_meta = gh.get_repository(owner, repo, installation_id=installation_id)
            target_branch = repo_meta.get("default_branch", "main")
        except Exception:
            target_branch = "main"

    exact_commit_sha = commit_sha
    if not commit_sha or commit_sha == "HEAD":
        try:
            resolved_sha = gh.resolve_commit_sha(owner, repo, target_branch, installation_id=installation_id)
            if resolved_sha:
                exact_commit_sha = resolved_sha
            else:
                exact_commit_sha = "HEAD"
        except Exception as err:
            logger.warning(f"Could not resolve exact commit SHA for {full_name}@{target_branch}: {err}")
            exact_commit_sha = "HEAD"

    # 3. Create secure temporary directory with guaranteed automatic cleanup
    with tempfile.TemporaryDirectory(prefix=f"impactintel_{owner}_{repo}_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        tar_path = temp_dir / "archive.tar.gz"
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        ref_for_download = exact_commit_sha if exact_commit_sha and exact_commit_sha != "HEAD" else target_branch
        tarball_url = f"{gh.base_url}/repos/{owner}/{repo}/tarball/{ref_for_download}"

        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # 4. Stream download with timeout and archive size limit
        try:
            with httpx.Client(follow_redirects=True, timeout=download_timeout) as client:
                with client.stream("GET", tarball_url, headers=headers) as response:
                    if response.status_code == 404:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Repository archive for '{full_name}' ref '{ref_for_download}' not found on GitHub."
                        )
                    if response.status_code == 401 or response.status_code == 403:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied to repository '{full_name}' archive."
                        )
                    response.raise_for_status()

                    # Check Content-Length if provided
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > max_archive_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"Repository archive size exceeds maximum limit of {max_archive_size // (1024 * 1024)}MB"
                        )

                    total_bytes = 0
                    with open(tar_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            total_bytes += len(chunk)
                            if total_bytes > max_archive_size:
                                raise HTTPException(
                                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                                    detail=f"Repository archive size exceeds limit of {max_archive_size // (1024 * 1024)}MB"
                                )
                            f.write(chunk)
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Download timed out after {download_timeout}s while retrieving repository archive from GitHub."
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to download repository archive: {exc}"
            )

        # 5. Safe tarball extraction with traversal protection and exclusions
        try:
            safe_extract_tarball(
                tar_path=tar_path,
                dest_dir=extract_dir,
                max_file_count=max_file_count,
                max_extracted_size=max_extracted_size
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error during tarball extraction for {full_name}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to safely extract repository archive: {exc}"
            )

        # 6. Locate repository root inside extracted directory
        # GitHub tarballs nest contents inside a top-level directory: owner-repo-sha
        subdirs = [p for p in extract_dir.iterdir() if p.is_dir()]
        if len(subdirs) == 1 and not (extract_dir / "package.json").exists() and not (extract_dir / "src").exists():
            repo_root = subdirs[0]
        else:
            repo_root = extract_dir

        logger.info(
            f"Successfully retrieved repository '{full_name}' branch '{target_branch}' "
            f"commit '{exact_commit_sha[:7] if exact_commit_sha else 'HEAD'}' into temporary directory"
        )

        yield RemoteRepositoryContext(
            directory_path=repo_root,
            branch=target_branch,
            commit_sha=exact_commit_sha,
            installation_id=installation_id
        )
