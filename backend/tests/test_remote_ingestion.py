import io
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.db.repository_store import RepositoryStore
from app.services.github_app import GitHubAppService
from app.services.repo_ingestion import (
    safe_extract_tarball,
    retrieve_remote_repository,
    MAX_FILE_COUNT,
    MAX_EXTRACTED_SIZE_BYTES
)
from app.services.indexer import RepositoryIndexer


def _create_test_tarball(files: dict, base_prefix: str = "test-repo-sha/") -> io.BytesIO:
    """Helper to build an in-memory tarball archive with specified member files."""
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        for rel_path, content in files.items():
            full_member_name = f"{base_prefix}{rel_path}" if base_prefix else rel_path
            data = content.encode("utf-8") if isinstance(content, str) else content
            ti = tarfile.TarInfo(name=full_member_name)
            ti.size = len(data)
            ti.type = tarfile.REGTYPE
            tar.addfile(ti, io.BytesIO(data))
    bio.seek(0)
    return bio


def test_safe_extract_tarball_normal():
    """Verify standard repository files extract cleanly."""
    files = {
        "package.json": '{"name": "test-pkg"}',
        "src/index.js": "export const hello = () => 'world';",
        "src/components/App.jsx": "export default function App() { return <div>App</div>; }"
    }
    bio = _create_test_tarball(files)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = Path(tmp_dir) / "test.tar.gz"
        tar_path.write_bytes(bio.getvalue())
        dest_dir = Path(tmp_dir) / "extracted"
        dest_dir.mkdir()

        count = safe_extract_tarball(tar_path, dest_dir)
        assert count == 3
        assert (dest_dir / "test-repo-sha" / "package.json").exists()
        assert (dest_dir / "test-repo-sha" / "src" / "index.js").exists()


def test_safe_extract_tarball_prevents_directory_traversal():
    """Verify tar slip path traversal attempts are blocked."""
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        evil_data = b"malicious_payload"
        ti = tarfile.TarInfo(name="test-repo/../../etc/cron.d/evil")
        ti.size = len(evil_data)
        ti.type = tarfile.REGTYPE
        tar.addfile(ti, io.BytesIO(evil_data))
    bio.seek(0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = Path(tmp_dir) / "evil.tar.gz"
        tar_path.write_bytes(bio.getvalue())
        dest_dir = Path(tmp_dir) / "extracted"
        dest_dir.mkdir()

        with pytest.raises(ValueError, match="traversal detected"):
            safe_extract_tarball(tar_path, dest_dir)


def test_safe_extract_tarball_skips_symlinks():
    """Verify symlinks are skipped to prevent symlink attacks."""
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w:gz") as tar:
        # Add normal file
        normal_data = b"console.log('hi');"
        ti1 = tarfile.TarInfo(name="repo/src/index.js")
        ti1.size = len(normal_data)
        ti1.type = tarfile.REGTYPE
        tar.addfile(ti1, io.BytesIO(normal_data))

        # Add symlink pointing to /etc/passwd
        ti2 = tarfile.TarInfo(name="repo/evil_link")
        ti2.type = tarfile.SYMTYPE
        ti2.linkname = "/etc/passwd"
        tar.addfile(ti2)
    bio.seek(0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = Path(tmp_dir) / "symlink.tar.gz"
        tar_path.write_bytes(bio.getvalue())
        dest_dir = Path(tmp_dir) / "extracted"
        dest_dir.mkdir()

        count = safe_extract_tarball(tar_path, dest_dir)
        assert count == 1
        assert not (dest_dir / "repo" / "evil_link").exists()


def test_safe_extract_tarball_excludes_generated_and_irrelevant_files():
    """Verify node_modules, .git, dist, and image/media binaries are excluded."""
    files = {
        "src/main.js": "console.log('source');",
        "node_modules/lodash/index.js": "module.exports = {};",
        "dist/bundle.js": "var x = 1;",
        "assets/logo.png": b"\x89PNG\r\n\x1a\n",
        "binary.exe": b"MZ\x90\x00",
        "fonts/font.woff2": b"wOF2"
    }
    bio = _create_test_tarball(files)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = Path(tmp_dir) / "repo.tar.gz"
        tar_path.write_bytes(bio.getvalue())
        dest_dir = Path(tmp_dir) / "extracted"
        dest_dir.mkdir()

        count = safe_extract_tarball(tar_path, dest_dir)
        assert count == 1  # Only src/main.js
        assert (dest_dir / "test-repo-sha" / "src" / "main.js").exists()
        assert not (dest_dir / "test-repo-sha" / "node_modules").exists()
        assert not (dest_dir / "test-repo-sha" / "dist").exists()
        assert not (dest_dir / "test-repo-sha" / "assets" / "logo.png").exists()


def test_safe_extract_tarball_enforces_file_count_limit():
    """Verify archives exceeding file count limit raise HTTP 413."""
    files = {f"src/file_{i}.js": f"// file {i}" for i in range(15)}
    bio = _create_test_tarball(files)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = Path(tmp_dir) / "many_files.tar.gz"
        tar_path.write_bytes(bio.getvalue())
        dest_dir = Path(tmp_dir) / "extracted"
        dest_dir.mkdir()

        with pytest.raises(HTTPException) as exc_info:
            safe_extract_tarball(tar_path, dest_dir, max_file_count=10)
        assert exc_info.value.status_code == 413
        assert "file count exceeds limit" in exc_info.value.detail


def test_safe_extract_tarball_enforces_extracted_size_limit():
    """Verify archives exceeding extracted size limit raise HTTP 413."""
    files = {"src/big_file.js": "x" * 2000}
    bio = _create_test_tarball(files)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = Path(tmp_dir) / "large.tar.gz"
        tar_path.write_bytes(bio.getvalue())
        dest_dir = Path(tmp_dir) / "extracted"
        dest_dir.mkdir()

        with pytest.raises(HTTPException) as exc_info:
            safe_extract_tarball(tar_path, dest_dir, max_extracted_size=1000)
        assert exc_info.value.status_code == 413
        assert "size exceeds limit" in exc_info.value.detail


def test_retrieve_remote_repository_validates_github_app_authorization():
    """Verify GitHub App installation check denies unauthorized repositories with HTTP 403."""
    mock_gh = MagicMock(spec=GitHubAppService)
    mock_gh.app_id = "12345"
    mock_gh.private_key = "fake_private_key"
    mock_gh.base_url = "https://api.github.com"
    # App is NOT installed on this repo
    mock_gh.get_repository_installation.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        with retrieve_remote_repository("unauthorized-owner", "secret-repo", github_service=mock_gh):
            pass

    assert exc_info.value.status_code == 403
    assert "GitHub App is not authorized or installed" in exc_info.value.detail


def test_retrieve_remote_repository_automatic_cleanup_and_exact_sha():
    """Verify temporary directory is automatically removed and exact branch & commit SHA are tracked."""
    files = {
        "src/app.js": "console.log('remote repo');",
        "package.json": '{"name": "remote-app"}'
    }
    tar_bytes = _create_test_tarball(files, base_prefix="owner-repo-a1b2c3d4/").getvalue()

    mock_gh = MagicMock(spec=GitHubAppService)
    mock_gh.app_id = "12345"
    mock_gh.private_key = "fake_private_key"
    mock_gh.base_url = "https://api.github.com"
    mock_gh.get_repository_installation.return_value = 9999
    mock_gh.get_installation_access_token.return_value = "ghs_test_installation_token"
    mock_gh.get_repository.return_value = {"default_branch": "prod"}
    mock_gh.resolve_commit_sha.return_value = "a1b2c3d4e5f678901234567890abcdef12345678"

    # Mock streaming download response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": str(len(tar_bytes))}
    mock_resp.iter_bytes.return_value = [tar_bytes]
    mock_resp.raise_for_status = MagicMock()

    captured_temp_path = None

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.stream.return_value.__enter__.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with retrieve_remote_repository(
            owner="owner",
            repo="repo",
            branch="prod",
            commit_sha="HEAD",
            github_service=mock_gh
        ) as remote_ctx:
            captured_temp_path = remote_ctx.directory_path
            assert captured_temp_path.exists()
            assert (captured_temp_path / "package.json").exists()
            assert remote_ctx.branch == "prod"
            assert remote_ctx.commit_sha == "a1b2c3d4e5f678901234567890abcdef12345678"
            assert remote_ctx.installation_id == 9999

    # Verify automatic cleanup of temporary directory after exiting with-block
    assert not captured_temp_path.exists(), "Temporary directory must be cleaned up automatically"


def test_graph_data_isolated_by_repository_id():
    """Verify graph data remains strictly isolated between distinct repository records."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Create two distinct repositories
        repo_a = RepositoryStore.get_or_create_repository(db, "org/frontend-app", default_branch="main")
        repo_b = RepositoryStore.get_or_create_repository(db, "org/backend-service", default_branch="main")
        assert repo_a.id != repo_b.id

        # Index repo A in temp dir
        with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
            path_a = Path(dir_a)
            (path_a / "src").mkdir()
            (path_a / "src" / "component.js").write_text("export function ComponentA() { return 1; }", encoding="utf-8")

            path_b = Path(dir_b)
            (path_b / "src").mkdir()
            (path_b / "src" / "service.js").write_text("export function ServiceB() { return 2; }", encoding="utf-8")

            indexer = RepositoryIndexer()
            idx_a = indexer.index_directory(db, repo_a.full_name, path_a, branch="main", commit_sha="sha_a")
            idx_b = indexer.index_directory(db, repo_b.full_name, path_b, branch="main", commit_sha="sha_b")

            # Load graphs for each repository
            ckg_a, _ = RepositoryStore.load_graph(db, repository_id=repo_a.id, commit_sha="sha_a")
            ckg_b, _ = RepositoryStore.load_graph(db, repository_id=repo_b.id, commit_sha="sha_b")

            nodes_a = set(ckg_a.graph.nodes())
            nodes_b = set(ckg_b.graph.nodes())

            # Verify no cross-contamination between repository graphs
            assert any("ComponentA" in n for n in nodes_a)
            assert not any("ComponentA" in n for n in nodes_b)

            assert any("ServiceB" in n for n in nodes_b)
            assert not any("ServiceB" in n for n in nodes_a)
    finally:
        db.close()
