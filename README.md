# AI-Powered Repository Impact Intelligence System

**College Capstone Project — B.Tech Computer Science and Engineering**

An intelligent platform that maps software repository structures into a fine-grained Code Knowledge Graph and computes the exact structural blast radius of code modifications before changes are merged.

---

## Status: Increments 1, 2, 3, 4, and 5 Complete (Full Frontend & Conversational Graph RAG Platform)

### Supported Entities & Relationships:
* **Node Types**:
  * 📄 `File`: Source code modules.
  * ⚙️ `Function`: Functions, arrow functions, and class methods.
  * 🏛️ `Class`: Object-oriented classes.
  * ⚛️ `Component`: React functional and arrow components.
  * 🌐 `ApiRoute`: Express.js and FastAPI HTTP routes (`GET /...`, `POST /...`).
  * 🧪 `Test`: Jest, Vitest, and Pytest test cases.
* **Relationship Types**:
  * `imports`: Module-to-module dependencies.
  * `defines`: File-to-symbol or class-to-method declarations.
  * `calls`: Function invocations (`caller ➔ callee`).
  * `renders`: React component hierarchy (`parent ➔ child`).
  * `handled_by`: API routes to route handlers (`api_route ➔ handler`).
  * `fetches`: Frontend calls to backend API routes (`frontend ➔ api_route`).
  * `tests`: Test cases to covered functions (`test ➔ tested_function`).

---

## Increment 4: Conversational Repository Intelligence

* **Semantic Code Chunking**: AST-aligned units (functions, classes, components, routes, files) with metadata preservation.
* **Triple-Retrieval Hybrid Fusion**:
  1. **Graph RAG**: Traverses the Code Knowledge Graph (upstream callers/predecessors, downstream callees/successors, tests, and rendering chains).
  2. **BM25 Keyword Search**: Exact symbol identifiers, camelCase and snake_case token matching.
  3. **Vector Similarity**: pgvector-compatible normalized embeddings strictly scoped to the repository boundary.
  * Fused using **Reciprocal Rank Fusion (RRF)**: $RRF(d) = \sum \frac{1}{k + rank(d)}$ with query-intent awareness.
* **LangGraph Orchestration**:
  * Multi-stage pipeline: Query Understanding ➔ Parallel Retrieval ➔ LLM Generation ➔ Evidence-based Claim Verification ➔ Conditional Bounded Retry.
* **Evidence-Based Claim Verification**:
  * Cross-examines all generated statements against retrieved chunks; flags hallucinations and unsupported claims.
* **Conversational Memory**:
  * Repository-scoped short-term history and automatic anaphora resolution (e.g. *"What does the first one do?"*).

---

## Increment 5: Full Frontend & GitHub OAuth Platform

* **GitHub OAuth App Authentication**: Seamless login without requiring GitHub App installation. Signed JWT session tokens with local dev bypass.
* **Repository Hub & Progress Tracking**: Interactive repository selection, AST scanning progress with real-time feedback.
* **Code Knowledge Graph Explorer**: React Flow visualization with on-demand lazy subgraph expansion, caller/dependency badges, and node details inspection.
* **PR Impact Visualizer**: Transitive causal propagation chains, affected components, modified diff files, and recommended test suites.
* **Evidence-Grounded AI Chat UI**: Real-time conversational interface with evidence inspection, claim verification badges, and context-reset conversations.
* **Analysis Audit History & Repository Settings**: Persistent SQLite/PostgreSQL historical audit records, re-indexing controls, and local repository database management.

---

## Canonical Graph Direction & Impact Rules

$$\text{Caller / Dependent} \longrightarrow \text{Dependency / Callee}$$

1. **Symbol-Level Analysis**: Directly pinpoints which specific functions or React components call or render modified symbols.
2. **File-Level Fallback**: Automatically used when changed files lack symbol-level mappings.
3. **Test Depth Independence**: Tests covering affected components are collected into `related_tests` without consuming the 3-level depth traversal limit.
4. **Cycle Safety & Provenance**: Infinite loops are prevented, and full causal paths with line-level evidence are returned.

---

## Quickstart

### Backend

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run all 64 automated backend tests
pytest

# 3. Start FastAPI server
PYTHONPATH=backend uvicorn app.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Backend API Docs: `http://localhost:8000/docs`

### Frontend

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Run automated tests (13 tests)
npm test

# 3. Build production bundle
npm run build

# 4. Start Vite development server
npm run dev
```

Frontend Application: `http://localhost:5173`
