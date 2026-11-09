# Backend — Repository Impact Intelligence Engine

This backend implements the static analysis, fine-grained graph impact engine, PostgreSQL persistence, and GitHub integration for the **AI-Powered Repository Impact Intelligence System**.

## Architectural Highlights

* **Multi-Language AST Parsers**:
  * JavaScript, TypeScript, JSX/TSX Concrete Syntax Tree parsing via `tree-sitter`.
  * Python Abstract Syntax Tree parsing via Python `ast`.
* **Fine-Grained Code Knowledge Graph**:
  * Nodes: `File`, `Function`, `Class`, `Component` (React), `ApiRoute` (Express / FastAPI), `Test` (Jest / Vitest / Pytest).
  * Relationships: `imports`, `defines`, `calls`, `renders`, `handled_by`, `fetches`, `tests`.
  * Canonical Direction: `Caller / Dependent ➔ Dependency / Callee`.
* **Reverse Impact Engine**:
  * Symbol-level traversal: identifies calling functions, rendering components, and handling routes.
  * File-level fallback: automatically used when PR changes do not map to individual symbols.
  * Test preservation rule: `tests` relationships do not consume the 3-level depth limit and are gathered into `related_tests`.
* **Database & GitHub Integration**:
  * PostgreSQL persistence with automatic graph reconstruction.
  * GitHub App JWT & scoped installation token authentication.
  * Webhook listener with HMAC SHA-256 signature verification.

## Directory Structure

* `app/core/`: Configuration, security verification, supported extensions.
* `app/db/`: SQLAlchemy ORM models, session management, and `RepositoryStore`.
* `app/extractors/`:
  * `javascript/`: Tree-sitter import resolver & `AdvancedJavaScriptExtractor`.
  * `python/`: Python AST `PythonExtractor`.
  * `unified.py`: Multi-language extraction orchestrator.
* `app/graph/`: Normalized schema models and NetworkX `CodeKnowledgeGraph` builder.
* `app/impact/`: Fine-grained reverse dependency traversal engine and impact models.
* `app/services/`:
  * `github_app.py`: GitHub App authentication & API client.
  * `indexer.py`: Multi-language repository indexing pipeline.
  * `pr_analyzer.py`: PR change mapping & impact analysis coordinator.
* `app/api/`: FastAPI web server with OpenAPI Swagger documentation.
* `app/main.py`: CLI pipeline entrypoint.
* `tests/`: Automated pytest test suites (42 test cases).

## Quickstart

### 1. Run Automated Tests
```bash
source .venv/bin/activate
PYTHONPATH=backend pytest backend/tests/ -v
```

### 2. Run CLI Impact Analysis
```bash
# Fine-grained symbol-level analysis
PYTHONPATH=backend python backend/app/main.py --repo sample-repository --changed src/database/database.js::query

# React component rendering analysis
PYTHONPATH=backend python backend/app/main.py --repo sample-repository --changed src/components/PaymentForm.jsx::PaymentForm
```

### 3. Start Backend FastAPI Server
```bash
PYTHONPATH=backend uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation: `http://localhost:8000/docs`.
