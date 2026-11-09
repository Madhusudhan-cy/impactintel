import os
from pathlib import Path

# Supported file extensions for JavaScript/TypeScript extraction
SUPPORTED_JS_TS_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs"
}

# Directories to ignore during repository scanning
IGNORED_DIRECTORIES = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "coverage",
    ".venv",
    "__pycache__"
}

# Database Configuration
# Defaults to PostgreSQL, with automatic SQLite fallback for local test environments
DEFAULT_POSTGRES_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/repo_impact"
DEFAULT_SQLITE_URL = "sqlite:///./repo_impact.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

# GitHub App Configuration
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY", "")
GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "dev_webhook_secret")
GITHUB_API_BASE_URL = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")

# GitHub OAuth App Configuration (Increment 5)
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/github/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_jwt_secret_key_repo_impact_2026")
JWT_ALGORITHM = "HS256"
SESSION_EXPIRE_HOURS = 24
