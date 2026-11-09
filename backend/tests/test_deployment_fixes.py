import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

from app.api.app import get_cors_origins
from app.db.session import normalize_database_url, create_configured_engine, init_db
from app.services.github_app import GitHubAppService


def test_root_gitignore_excludes_required_patterns():
    """Verify root .gitignore exists and properly covers all sensitive and generated patterns."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    gitignore_path = root_dir / ".gitignore"
    assert gitignore_path.exists(), "Root .gitignore must exist"

    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    # Check sensitive files
    assert ".env" in lines
    assert "*.pem" in lines
    assert "*.key" in lines

    # Check SQLite databases
    assert "*.db" in lines or "repo_impact.db" in lines

    # Check node modules and dist
    assert any("node_modules" in line for line in lines)
    assert any("dist" in line for line in lines)

    # Check Python artifacts
    assert any("__pycache__" in line for line in lines)
    assert any(".venv" in line for line in lines)


def test_cors_origin_parsing_and_security():
    """Verify CORS origins are parsed explicitly, trailing slashes removed, and wildcards excluded."""
    with patch("app.api.app.FRONTEND_URL", "https://impactintel.vercel.app/"), \
         patch("app.api.app.CORS_ORIGINS", "https://preview.vercel.app, *, https://custom-domain.com/"):
        origins = get_cors_origins()

        # Trailing slash stripped
        assert "https://impactintel.vercel.app" in origins
        assert "https://impactintel.vercel.app/" not in origins

        # Additional origins included
        assert "https://preview.vercel.app" in origins
        assert "https://custom-domain.com" in origins
        assert "https://custom-domain.com/" not in origins

        # Wildcard * must be rejected to protect credentialed requests
        assert "*" not in origins

        # Default local origins preserved
        assert "http://localhost:5173" in origins
        assert "http://localhost:3000" in origins


def test_database_url_normalization():
    """Verify legacy postgres:// schemes are normalized for SQLAlchemy 2.0 with the installed psycopg2 driver."""
    # postgres:// normalized to postgresql+psycopg2://
    raw_neon = "postgres://alex:secret@ep-cool-fog-1234.us-east-2.aws.neon.tech/neondb?sslmode=require"
    normalized = normalize_database_url(raw_neon)
    assert normalized.startswith("postgresql+psycopg2://")
    assert "postgres://" not in normalized[:12]

    # generic postgresql:// normalized to postgresql+psycopg2://
    generic_pg = "postgresql://alex:secret@localhost:5432/repo_impact"
    assert normalize_database_url(generic_pg) == "postgresql+psycopg2://alex:secret@localhost:5432/repo_impact"

    # sqlite unchanged
    sqlite_url = "sqlite:///./repo_impact.db"
    assert normalize_database_url(sqlite_url) == sqlite_url

    # empty string handled
    assert normalize_database_url("") == ""


def test_database_engine_pooling_configuration():
    """Verify connection pooling settings for PostgreSQL engines."""
    postgres_url = "postgresql://user:pass@localhost:5432/testdb"
    engine = create_configured_engine(postgres_url)

    # Engine pool should have pre_ping and recycle configured
    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 300


def test_init_db_creates_vector_extension_on_postgres():
    """Verify init_db executes CREATE EXTENSION vector when PostgreSQL dialect is used."""
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("app.db.session.Base.metadata.create_all") as mock_create_all:
        init_db(target_engine=mock_engine)
        assert mock_conn.execute.called
        # Check text of execute call
        call_arg = str(mock_conn.execute.call_args[0][0])
        assert "CREATE EXTENSION IF NOT EXISTS vector" in call_arg
        assert mock_conn.commit.called
        assert mock_create_all.called


def test_init_db_skips_vector_extension_on_sqlite():
    """Verify init_db does not attempt CREATE EXTENSION on SQLite."""
    sqlite_engine = create_engine("sqlite:///:memory:")
    init_db(target_engine=sqlite_engine)
    # Succeeds cleanly without postgres-specific extension call


def test_init_db_handles_extension_error_gracefully():
    """Verify init_db catches vector extension errors and continues with table initialization."""
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = Exception("Permission denied to create extension")
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("app.db.session.Base.metadata.create_all") as mock_create_all:
        # Should not raise exception, logs warning instead
        init_db(target_engine=mock_engine)
        assert mock_create_all.called


def test_github_app_path_import_and_key_file_loading():
    """Verify GITHUB_PRIVATE_KEY_PATH loads private key correctly using pathlib Path."""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".pem") as f:
        f.write("-----BEGIN MOCK KEY-----\nMOCK_PRIVATE_KEY_DATA\n-----END MOCK KEY-----\n")
        tmp_key_path = f.name

    try:
        with patch("app.services.github_app.GITHUB_PRIVATE_KEY", ""), \
             patch("app.services.github_app.GITHUB_PRIVATE_KEY_PATH", tmp_key_path):
            service = GitHubAppService(app_id="12345")
            assert "MOCK_PRIVATE_KEY_DATA" in service.private_key
    finally:
        if os.path.exists(tmp_key_path):
            os.remove(tmp_key_path)
