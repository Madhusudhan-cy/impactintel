from typing import List, Dict, Any, Optional
import json
import logging
import secrets
from pathlib import Path
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import GITHUB_WEBHOOK_SECRET, FRONTEND_URL, ALLOW_DEV_BYPASS, GITHUB_APP_SLUG
from app.core.security import verify_github_signature
from app.db.session import get_db
from app.db.models import Repository, CommitIndex, PullRequestAnalysisRecord, ImpactReportRecord, ConversationRecord
from app.db.repository_store import RepositoryStore
from app.services.github_app import GitHubAppService
from app.services.github_oauth import GitHubOAuthService
from app.services.indexer import RepositoryIndexer
from app.services.pr_analyzer import PullRequestImpactService
from app.services.repo_ingestion import retrieve_remote_repository

from app.rag.chunker import CodeChunker
from app.rag.bm25 import BM25Retriever
from app.rag.graph_rag import GraphRAGRetriever
from app.rag.vector_store import VectorRetriever
from app.rag.hybrid import HybridRetriever
from app.rag.workflow import ConversationalRAGOrchestrator
from app.rag.memory import ConversationManager

logger = logging.getLogger(__name__)

api_router = APIRouter()

# Processed webhook delivery cache for deduplication
_PROCESSED_DELIVERIES: set = set()

# Conversational memory manager
_CONVERSATION_MANAGER = ConversationManager()


# Pydantic Request Models
class ManualAnalysisRequest(BaseModel):
    changed_files: List[Dict[str, Any]] = Field(
        ...,
        description="List of file objects, e.g. [{'filename': 'src/database/database.js', 'status': 'modified'}]"
    )
    pr_title: str = "Manual PR Analysis"
    base_branch: str = "main"
    base_commit_sha: str = "HEAD"
    head_commit_sha: str = "manual"
    post_comment: bool = False


class IndexRepositoryRequest(BaseModel):
    directory_path: Optional[str] = None  # If local path provided (e.g. sample-repository)
    branch: str = "main"
    commit_sha: str = "HEAD"


# 1. Healthcheck
@api_router.get("/health")
def healthcheck():
    return {"status": "ok", "service": "Repository Impact Intelligence API"}


# 2. GitHub Webhook Endpoint
@api_router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None)
):
    """
    Handle GitHub webhook deliveries with signature verification,
    deduplication, and event routing.
    """
    body_bytes = await request.body()

    # 1. Signature Verification
    if GITHUB_WEBHOOK_SECRET and GITHUB_WEBHOOK_SECRET != "dev_webhook_secret":
        if not verify_github_signature(body_bytes, x_hub_signature_256, GITHUB_WEBHOOK_SECRET):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub webhook signature"
            )

    # 2. Delivery Deduplication
    if x_github_delivery:
        if x_github_delivery in _PROCESSED_DELIVERIES:
            return {"status": "ignored", "reason": "duplicate delivery"}
        _PROCESSED_DELIVERIES.add(x_github_delivery)
        if len(_PROCESSED_DELIVERIES) > 5000:
            _PROCESSED_DELIVERIES.clear()

    # 3. Payload parsing
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed JSON: {e}")

    event_type = x_github_event or "unknown"

    # Ping event
    if event_type == "ping":
        return {"status": "pong", "zen": payload.get("zen")}

    # Installation event
    if event_type == "installation":
        action = payload.get("action")
        inst_id = payload.get("installation", {}).get("id")
        repos = payload.get("repositories", [])
        for r in repos:
            full_name = r.get("full_name")
            if full_name:
                RepositoryStore.get_or_create_repository(db, full_name, installation_id=inst_id)
        return {"status": "processed", "event": "installation", "action": action}

    # Pull Request event
    if event_type == "pull_request":
        action = payload.get("action")
        if action not in ("opened", "synchronize", "reopened"):
            return {"status": "ignored", "reason": f"unhandled PR action: {action}"}

        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})
        full_name = repo_data.get("full_name")
        pr_number = pr_data.get("number")
        pr_title = pr_data.get("title", "")
        base_branch = pr_data.get("base", {}).get("ref", "main")
        base_sha = pr_data.get("base", {}).get("sha", "HEAD")
        head_sha = pr_data.get("head", {}).get("sha", "unknown")
        inst_id = payload.get("installation", {}).get("id")

        if not full_name or not pr_number:
            raise HTTPException(status_code=400, detail="Missing repository full_name or PR number")

        # Update installation ID if present
        repo = RepositoryStore.get_or_create_repository(db, full_name, default_branch=base_branch, installation_id=inst_id)

        # Retrieve changed files
        github_service = GitHubAppService()
        try:
            changed_files = github_service.get_pull_request_files(
                owner=repo.owner,
                repo=repo.name,
                pull_number=pr_number,
                installation_id=inst_id
            )
        except Exception as e:
            logger.warning(f"Could not fetch PR files from GitHub API ({e}); checking payload")
            changed_files = []

        # Coordinate PR impact analysis
        analyzer = PullRequestImpactService(github_service=github_service)
        try:
            record, report, unmapped = analyzer.analyze_pull_request(
                db=db,
                full_name=full_name,
                pr_number=pr_number,
                pr_title=pr_title,
                base_branch=base_branch,
                base_commit_sha=base_sha,
                head_commit_sha=head_sha,
                changed_files_info=changed_files,
                post_github_comment=True
            )
            return {
                "status": "analyzed",
                "pr_number": pr_number,
                "total_affected": report.total_affected,
                "unmapped_files": len(unmapped)
            }
        except Exception as e:
            logger.error(f"Error analyzing PR #{pr_number}: {e}")
            return {"status": "error", "detail": str(e)}

    return {"status": "acknowledged", "event": event_type}


# 3. Repository Indexing Trigger
@api_router.post("/repos/{owner}/{repo}/index")
def trigger_index(
    owner: str,
    repo: str,
    payload: IndexRepositoryRequest,
    db: Session = Depends(get_db)
):
    full_name = f"{owner}/{repo}"
    indexer = RepositoryIndexer()

    # 1. Explicit local directory path provided (e.g. testing)
    if payload.directory_path:
        dir_path = Path(payload.directory_path)
        if not dir_path.exists():
            raise HTTPException(status_code=404, detail=f"Target directory '{payload.directory_path}' not found")
        commit_index = indexer.index_directory(
            db=db,
            full_name=full_name,
            directory_path=dir_path,
            branch=payload.branch,
            commit_sha=payload.commit_sha
        )
    # 2. Local fallback for sample-repository only when development bypass is explicitly enabled
    elif ALLOW_DEV_BYPASS and (full_name in ("org/shop-repo", "testorg/sample-repo")) and Path("sample-repository").exists():
        commit_index = indexer.index_directory(
            db=db,
            full_name=full_name,
            directory_path=Path("sample-repository"),
            branch=payload.branch,
            commit_sha=payload.commit_sha
        )
    # 3. Secure remote repository ingestion through authorized GitHub App
    else:
        with retrieve_remote_repository(
            owner=owner,
            repo=repo,
            branch=payload.branch,
            commit_sha=payload.commit_sha
        ) as remote_ctx:
            commit_index = indexer.index_directory(
                db=db,
                full_name=full_name,
                directory_path=remote_ctx.directory_path,
                branch=remote_ctx.branch,
                commit_sha=remote_ctx.commit_sha,
                installation_id=remote_ctx.installation_id
            )

    return {
        "status": commit_index.status,
        "repository": full_name,
        "branch": commit_index.branch,
        "commit_sha": commit_index.commit_sha,
        "total_nodes": commit_index.total_nodes,
        "total_edges": commit_index.total_edges,
        "indexed_at": commit_index.indexed_at.isoformat()
    }


# 4. Check Indexing Status
@api_router.get("/repos/{owner}/{repo}/index/status")
def get_indexing_status(owner: str, repo: str, db: Session = Depends(get_db)):
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not registered")

    commit_index = (
        db.query(CommitIndex)
        .filter(CommitIndex.repository_id == repository.id)
        .order_by(CommitIndex.indexed_at.desc())
        .first()
    )

    if not commit_index:
        return {"status": "NOT_INDEXED", "repository": full_name}

    return {
        "status": commit_index.status,
        "repository": full_name,
        "branch": commit_index.branch,
        "commit_sha": commit_index.commit_sha,
        "total_nodes": commit_index.total_nodes,
        "total_edges": commit_index.total_edges,
        "indexed_at": commit_index.indexed_at.isoformat()
    }


# 5. Manual Pull Request Impact Analysis Endpoint
@api_router.post("/repos/{owner}/{repo}/pulls/{pr_number}/analyze")
def manual_analyze_pr(
    owner: str,
    repo: str,
    pr_number: int,
    payload: ManualAnalysisRequest,
    db: Session = Depends(get_db)
):
    full_name = f"{owner}/{repo}"
    analyzer = PullRequestImpactService()

    try:
        record, report, unmapped = analyzer.analyze_pull_request(
            db=db,
            full_name=full_name,
            pr_number=pr_number,
            pr_title=payload.pr_title,
            base_branch=payload.base_branch,
            base_commit_sha=payload.base_commit_sha,
            head_commit_sha=payload.head_commit_sha,
            changed_files_info=payload.changed_files,
            post_github_comment=payload.post_comment
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "pr_number": record.pr_number,
        "pr_title": record.pr_title,
        "base_branch": record.base_branch,
        "base_commit_sha": record.base_commit_sha,
        "head_commit_sha": record.head_commit_sha,
        "status": record.status,
        "total_affected": report.total_affected,
        "affected_components": [c.model_dump() for c in report.affected_components],
        "unaffected_files": report.unaffected_files,
        "unmapped_files": unmapped
    }


# 6. List PR Analyses History
@api_router.get("/repos/{owner}/{repo}/pulls")
def list_pr_analyses(owner: str, repo: str, db: Session = Depends(get_db)):
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not found")

    records = RepositoryStore.list_pr_analyses(db, repository.id)
    return [
        {
            "id": r.id,
            "pr_number": r.pr_number,
            "pr_title": r.pr_title,
            "base_branch": r.base_branch,
            "status": r.status,
            "total_affected": r.total_affected,
            "created_at": r.created_at.isoformat()
        }
        for r in records
    ]


# 7. Retrieve Specific PR Analysis with Full Report
@api_router.get("/repos/{owner}/{repo}/pulls/{pr_number}")
def get_pr_analysis(owner: str, repo: str, pr_number: int, db: Session = Depends(get_db)):
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not found")

    record = RepositoryStore.get_pr_analysis(db, repository.id, pr_number)
    if not record:
        raise HTTPException(status_code=404, detail=f"Analysis for PR #{pr_number} not found")

    report = record.impact_report
    return {
        "pr_number": record.pr_number,
        "pr_title": record.pr_title,
        "base_branch": record.base_branch,
        "base_commit_sha": record.base_commit_sha,
        "head_commit_sha": record.head_commit_sha,
        "status": record.status,
        "created_at": record.created_at.isoformat(),
        "total_affected": record.total_affected,
        "report": {
            "total_affected": report.total_affected if report else 0,
            "changed_files": report.changed_files if report else [],
            "affected_components": report.affected_components if report else [],
            "unaffected_files": report.unaffected_files if report else [],
            "unmapped_files": report.unmapped_files if report else []
        }
    }


# Pydantic Chat Request
class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


# 8. Conversational Repository Intelligence Endpoint
@api_router.post("/repos/{owner}/{repo}/chat")
def chat_with_repository(
    owner: str,
    repo: str,
    payload: ChatRequest,
    db: Session = Depends(get_db)
):
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not found. Please index it first.")

    # Load stored graph
    ckg, commit_index = RepositoryStore.load_graph(db, repository.id)
    if not ckg:
        raise HTTPException(status_code=400, detail=f"Repository '{full_name}' has no indexed graph. Run indexing first.")

    # Load or generate chunks
    chunks = VectorRetriever.load_chunks_from_db(db, repository.id)
    if not chunks:
        # Fallback to chunking sample-repository or local directory
        chunker = CodeChunker()
        repo_dir = Path("sample-repository")
        if repo_dir.exists():
            chunks = chunker.chunk_repository(repo_dir, repository_id=repository.id)
            VectorRetriever.save_chunks_to_db(db, repository.id, chunks)

    # Initialize Hybrid Retrieval stack
    bm25 = BM25Retriever(chunks)
    graph_rag = GraphRAGRetriever(ckg, chunks=chunks)
    vector = VectorRetriever(chunks)
    hybrid = HybridRetriever(bm25_retriever=bm25, graph_rag_retriever=graph_rag, vector_retriever=vector)

    orchestrator = ConversationalRAGOrchestrator(
        hybrid_retriever=hybrid,
        memory_manager=_CONVERSATION_MANAGER
    )

    try:
        response = orchestrator.ask(
            query=payload.query,
            repository_id=repository.id,
            conversation_id=payload.conversation_id
        )

        # Persist conversation turn to database
        cid = response["conversation_id"]
        conv_record = db.query(ConversationRecord).filter(ConversationRecord.conversation_id == cid).first()
        messages_snapshot = _CONVERSATION_MANAGER.get_history(cid, repository.id)
        if not conv_record:
            conv_record = ConversationRecord(
                conversation_id=cid,
                repository_id=repository.id,
                messages=messages_snapshot
            )
            db.add(conv_record)
        else:
            conv_record.messages = messages_snapshot
        db.commit()

        return response
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Chat workflow error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 9. Retrieve Conversation History
@api_router.get("/repos/{owner}/{repo}/chat/{conversation_id}")
def get_chat_history(
    owner: str,
    repo: str,
    conversation_id: str,
    db: Session = Depends(get_db)
):
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not found")

    history = _CONVERSATION_MANAGER.get_history(conversation_id, repository.id)
    if not history:
        # Check DB persistent record
        conv_record = db.query(ConversationRecord).filter(
            ConversationRecord.conversation_id == conversation_id,
            ConversationRecord.repository_id == repository.id
        ).first()
        if conv_record:
            history = conv_record.messages or []

    return {
        "conversation_id": conversation_id,
        "repository": full_name,
        "messages": history
    }


# ============================================================================
# 10. GitHub OAuth Authentication & Session Endpoints (Increment 5)
# ============================================================================

def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Extract authenticated user from JWT Bearer token if present."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split("Bearer ", 1)[1]
    decoded = GitHubOAuthService.decode_session_jwt(token)
    if not decoded:
        return None
    return decoded.get("user")


@api_router.get("/auth/github/url")
def get_github_auth_url():
    """Generate GitHub OAuth authorization URL with CSRF protection."""
    state = secrets.token_urlsafe(16)
    url = GitHubOAuthService.get_authorization_url(state=state)
    return {"url": url, "state": state}


@api_router.get("/auth/github/callback")
def github_auth_callback(
    code: str,
    state: Optional[str] = None
):
    """
    Handle GitHub OAuth callback, exchange code for access token,
    fetch user profile, and issue signed JWT session.
    """
    access_token = GitHubOAuthService.exchange_code_for_token(code)
    if not access_token:
        return RedirectResponse(f"{FRONTEND_URL}/auth/callback?error=access_denied")

    try:
        user = GitHubOAuthService.get_user_profile(access_token)
    except Exception as e:
        logger.error(f"Error retrieving GitHub profile: {e}")
        return RedirectResponse(f"{FRONTEND_URL}/auth/callback?error=profile_fetch_failed")

    jwt_token = GitHubOAuthService.create_session_jwt(user, access_token)
    return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={jwt_token}")


@api_router.get("/auth/me")
def get_current_user_profile(authorization: Optional[str] = Header(None)):
    """Retrieve current authenticated user profile."""
    user = get_current_user_optional(authorization)
    if not user:
        if ALLOW_DEV_BYPASS:
            # Provide default local developer profile only in dev mode
            return {
                "authenticated": True,
                "user": {
                    "id": 1001,
                    "login": "dev-user",
                    "name": "Local Developer",
                    "email": "dev@localhost",
                    "avatar_url": "https://avatars.githubusercontent.com/u/583231",
                    "html_url": "https://github.com",
                    "bio": "Local developer testing AI Repository Impact Intelligence"
                }
            }
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"authenticated": True, "user": user}


@api_router.post("/auth/logout")
def logout():
    """Invalidate frontend session."""
    return {"status": "logged_out"}


# ============================================================================
# 11. Repository Listing & Management Endpoints
# ============================================================================

@api_router.get("/repos/installation/status")
def get_installation_status(authorization: Optional[str] = Header(None)):
    """Check GitHub App installation status for the authenticated user."""
    user = get_current_user_optional(authorization)
    if not user:
        if ALLOW_DEV_BYPASS:
            return {
                "has_installations": True,
                "installation_count": 1,
                "install_url": f"https://github.com/apps/{GITHUB_APP_SLUG or 'impactintel'}/installations/new",
                "installations": [{"id": 1, "account": "dev-user"}]
            }
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    gh = GitHubAppService()
    install_url = gh.get_install_url()

    access_token = None
    if authorization and authorization.startswith("Bearer "):
        decoded = GitHubOAuthService.decode_session_jwt(authorization.split("Bearer ", 1)[1])
        if decoded:
            access_token = decoded.get("access_token")

    installations = []
    if access_token and not access_token.startswith("mock_"):
        try:
            installations = gh.get_user_installations(access_token)
        except Exception as e:
            logger.warning(f"Could not fetch user installations: {e}")

    has_installations = len(installations) > 0
    return {
        "has_installations": has_installations,
        "installation_count": len(installations),
        "install_url": install_url,
        "installations": [
            {"id": i.get("id"), "account": i.get("account", {}).get("login")}
            for i in installations
        ]
    }


@api_router.get("/repos")
def list_repositories(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """List repositories registered in the platform and accessible to the user."""
    user = get_current_user_optional(authorization)
    if not user and not ALLOW_DEV_BYPASS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # Build DB-indexed repos map for enrichment
    db_repos = {r.full_name: r for r in db.query(Repository).all()}
    results = []

    def _enrich_with_db(full_name: str, base: dict) -> dict:
        """Merge GitHub App repo data with DB indexing status."""
        r = db_repos.get(full_name)
        if r:
            latest_idx = (
                db.query(CommitIndex)
                .filter(CommitIndex.repository_id == r.id)
                .order_by(CommitIndex.indexed_at.desc())
                .first()
            )
            base.update({
                "id": r.id,
                "default_branch": r.default_branch,
                "indexing_status": latest_idx.status if latest_idx else "NOT_INDEXED",
                "indexed_at": latest_idx.indexed_at.isoformat() if latest_idx else None,
                "total_nodes": latest_idx.total_nodes if latest_idx else 0,
                "total_edges": latest_idx.total_edges if latest_idx else 0,
            })
        else:
            base.setdefault("indexing_status", "NOT_INDEXED")
            base.setdefault("indexed_at", None)
            base.setdefault("total_nodes", 0)
            base.setdefault("total_edges", 0)
        return base

    # Fetch from GitHub App installations when real auth is present
    access_token = None
    if authorization and authorization.startswith("Bearer "):
        decoded = GitHubOAuthService.decode_session_jwt(authorization.split("Bearer ", 1)[1])
        if decoded:
            access_token = decoded.get("access_token")

    if access_token and not access_token.startswith("mock_"):
        gh = GitHubAppService()
        try:
            installations = gh.get_user_installations(access_token)
            seen_full_names = set()
            for inst in installations:
                inst_id = inst.get("id")
                if not inst_id:
                    continue
                try:
                    repos = gh.list_accessible_repositories(inst_id)
                    for repo in repos:
                        fn = repo.get("full_name", "")
                        if fn and fn not in seen_full_names:
                            seen_full_names.add(fn)
                            results.append(_enrich_with_db(fn, {
                                "id": repo.get("id"),
                                "name": repo.get("name"),
                                "full_name": fn,
                                "owner": repo.get("owner", {}).get("login"),
                                "description": repo.get("description") or "",
                                "default_branch": repo.get("default_branch", "main"),
                                "private": repo.get("private", False),
                                "language": repo.get("language") or "Other",
                                "languages": [repo.get("language")] if repo.get("language") else [],
                            }))
                except Exception as e:
                    logger.warning(f"Failed to list repos for installation {inst_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch user installations: {e}")

    # Also surface any DB-registered repos the user may have added manually
    for full_name, r in db_repos.items():
        if not any(res["full_name"] == full_name for res in results):
            latest_idx = (
                db.query(CommitIndex)
                .filter(CommitIndex.repository_id == r.id)
                .order_by(CommitIndex.indexed_at.desc())
                .first()
            )
            results.append({
                "id": r.id,
                "name": r.name,
                "full_name": full_name,
                "owner": r.owner,
                "description": "",
                "default_branch": r.default_branch,
                "private": False,
                "language": "Other",
                "languages": [],
                "indexing_status": latest_idx.status if latest_idx else "NOT_INDEXED",
                "indexed_at": latest_idx.indexed_at.isoformat() if latest_idx else None,
                "total_nodes": latest_idx.total_nodes if latest_idx else 0,
                "total_edges": latest_idx.total_edges if latest_idx else 0,
            })

    # Dev-mode: inject sample-repository if present and not already in results
    if ALLOW_DEV_BYPASS and Path("sample-repository").exists():
        if not any(r["full_name"] == "org/shop-repo" for r in results):
            results.insert(0, {
                "id": 1,
                "name": "shop-repo",
                "full_name": "org/shop-repo",
                "owner": "org",
                "description": "Multi-tier sample e-commerce application (React + Express/FastAPI)",
                "default_branch": "main",
                "private": False,
                "language": "JavaScript",
                "languages": ["JavaScript", "Python"],
                "indexing_status": "NOT_INDEXED",
                "indexed_at": None,
                "total_nodes": 0,
                "total_edges": 0,
            })

    return results


@api_router.get("/repos/{owner}/{repo}")
def get_repository_details(
    owner: str,
    repo: str,
    db: Session = Depends(get_db)
):
    """Retrieve metadata and indexing summary for a specific repository."""
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        # Dev-mode: return stub for sample repository
        if ALLOW_DEV_BYPASS and (full_name == "org/shop-repo" or Path("sample-repository").exists()):
            return {
                "id": 1,
                "name": repo,
                "full_name": full_name,
                "owner": owner,
                "default_branch": "main",
                "private": False,
                "languages": ["JavaScript", "Python"],
                "indexing_status": "NOT_INDEXED",
                "total_nodes": 0,
                "total_edges": 0
            }
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not found")

    latest_idx = (
        db.query(CommitIndex)
        .filter(CommitIndex.repository_id == repository.id)
        .order_by(CommitIndex.indexed_at.desc())
        .first()
    )

    return {
        "id": repository.id,
        "name": repository.name,
        "full_name": repository.full_name,
        "owner": repository.owner,
        "default_branch": repository.default_branch,
        "private": False,
        "languages": ["JavaScript", "Python"],
        "indexing_status": latest_idx.status if latest_idx else "NOT_INDEXED",
        "indexed_at": latest_idx.indexed_at.isoformat() if latest_idx else None,
        "branch": latest_idx.branch if latest_idx else repository.default_branch,
        "commit_sha": latest_idx.commit_sha if latest_idx else "HEAD",
        "total_nodes": latest_idx.total_nodes if latest_idx else 0,
        "total_edges": latest_idx.total_edges if latest_idx else 0
    }


@api_router.delete("/repos/{owner}/{repo}")
def remove_repository(
    owner: str,
    repo: str,
    db: Session = Depends(get_db)
):
    """Remove repository from the local application database (does NOT delete GitHub repo)."""
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not found")

    db.delete(repository)
    db.commit()
    return {"status": "removed", "repository": full_name}


# ============================================================================
# 12. Code Knowledge Graph Explorer Endpoints (Increment 5)
# ============================================================================

@api_router.get("/repos/{owner}/{repo}/graph/summary")
def get_graph_summary(
    owner: str,
    repo: str,
    db: Session = Depends(get_db)
):
    """Return high-level Code Knowledge Graph summary and node type counts."""
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not registered")

    ckg, commit_index = RepositoryStore.load_graph(db, repository.id)
    if not ckg:
        raise HTTPException(status_code=400, detail="Repository graph not indexed yet")

    # Group node types
    type_counts = {}
    modules = set()
    for n, data in ckg.graph.nodes(data=True):
        ntype = data.get("type", "Symbol")
        type_counts[ntype] = type_counts.get(ntype, 0) + 1
        path = data.get("path", n.split("::")[0])
        if "/" in path:
            modules.add(path.split("/")[0])

    return {
        "repository": full_name,
        "total_nodes": ckg.graph.number_of_nodes(),
        "total_edges": ckg.graph.number_of_edges(),
        "node_type_counts": type_counts,
        "top_modules": sorted(list(modules))
    }


@api_router.get("/repos/{owner}/{repo}/graph/nodes")
def search_graph_nodes(
    owner: str,
    repo: str,
    q: Optional[str] = Query(None, description="Search query string"),
    node_type: Optional[str] = Query(None, description="Filter by NodeType (Function, Component, ApiRoute, etc.)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Search nodes in the repository's Code Knowledge Graph."""
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not registered")

    ckg, _ = RepositoryStore.load_graph(db, repository.id)
    if not ckg:
        raise HTTPException(status_code=400, detail="Repository graph not indexed")

    matched = []
    q_lower = q.lower() if q else None

    for node_id, data in ckg.graph.nodes(data=True):
        ntype = data.get("type", "Symbol")
        if node_type and ntype.lower() != node_type.lower():
            continue

        if q_lower:
            name = data.get("name") or node_id
            path = data.get("path") or ""
            if q_lower not in node_id.lower() and q_lower not in name.lower() and q_lower not in path.lower():
                continue

        matched.append({
            "id": node_id,
            "type": ntype,
            "name": data.get("name") or node_id.split("::")[-1],
            "path": data.get("path") or node_id.split("::")[0],
            "language": data.get("language", "javascript"),
            "metadata": data.get("metadata", {})
        })
        if len(matched) >= limit:
            break

    return {"count": len(matched), "nodes": matched}


@api_router.get("/repos/{owner}/{repo}/graph/node")
def get_graph_node_details(
    owner: str,
    repo: str,
    node_id: str = Query(..., description="Target node ID, e.g. 'src/services/paymentService.js::processPayment'"),
    db: Session = Depends(get_db)
):
    """Retrieve full details, incoming callers, outgoing dependencies, and tests for a specific node."""
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not registered")

    ckg, _ = RepositoryStore.load_graph(db, repository.id)
    if not ckg or node_id not in ckg.graph:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in repository graph")

    data = ckg.graph.nodes[node_id]

    # Incoming predecessors (Callers, Renders, Handlers)
    incoming = []
    for pred in ckg.graph.predecessors(node_id):
        edata = ckg.graph[pred][node_id]
        incoming.append({
            "source": pred,
            "relation_type": edata.get("type", "calls"),
            "statement": edata.get("statement"),
            "line": edata.get("line"),
            "confidence": edata.get("confidence", 1.0)
        })

    # Outgoing successors (Dependencies, Callees)
    outgoing = []
    for succ in ckg.graph.successors(node_id):
        edata = ckg.graph[node_id][succ]
        outgoing.append({
            "target": succ,
            "relation_type": edata.get("type", "calls"),
            "statement": edata.get("statement"),
            "line": edata.get("line"),
            "confidence": edata.get("confidence", 1.0)
        })

    return {
        "id": node_id,
        "type": data.get("type", "Symbol"),
        "name": data.get("name") or node_id.split("::")[-1],
        "path": data.get("path") or node_id.split("::")[0],
        "language": data.get("language", "javascript"),
        "metadata": data.get("metadata", {}),
        "incoming_callers": incoming,
        "outgoing_dependencies": outgoing
    }


@api_router.get("/repos/{owner}/{repo}/graph/neighbors")
def get_graph_neighbors_for_react_flow(
    owner: str,
    repo: str,
    node_id: Optional[str] = Query(None, description="Center node ID for on-demand lazy expansion"),
    max_nodes: int = Query(25, ge=5, le=100),
    db: Session = Depends(get_db)
):
    """
    Format subgraphs directly into React Flow elements (nodes & edges)
    with positions, styles, and labels for lazy exploration.
    """
    full_name = f"{owner}/{repo}"
    repository = db.query(Repository).filter(Repository.full_name == full_name).first()
    if not repository:
        raise HTTPException(status_code=404, detail=f"Repository '{full_name}' not registered")

    ckg, _ = RepositoryStore.load_graph(db, repository.id)
    if not ckg:
        raise HTTPException(status_code=400, detail="Repository graph not indexed")

    flow_nodes = []
    flow_edges = []
    visited_node_ids = set()

    # Determine center node or top central symbol
    target_id = node_id
    if not target_id:
        # Default to a prominent function, component, or route
        candidates = [n for n, d in ckg.graph.nodes(data=True) if d.get("type") in ("Function", "Component", "ApiRoute")]
        target_id = candidates[0] if candidates else list(ckg.graph.nodes())[0]

    if target_id not in ckg.graph:
        raise HTTPException(status_code=404, detail=f"Node '{target_id}' not found")

    # Add center node
    c_data = ckg.graph.nodes[target_id]
    visited_node_ids.add(target_id)
    flow_nodes.append({
        "id": target_id,
        "type": "custom",
        "data": {
            "label": c_data.get("name") or target_id.split("::")[-1],
            "nodeType": c_data.get("type", "Symbol"),
            "path": c_data.get("path", target_id.split("::")[0]),
            "isCenter": True
        },
        "position": {"x": 300, "y": 200}
    })

    # Add direct predecessors (Callers/Upstream)
    preds = list(ckg.graph.predecessors(target_id))[:max_nodes // 2]
    for idx, pred in enumerate(preds):
        if pred not in visited_node_ids:
            visited_node_ids.add(pred)
            p_data = ckg.graph.nodes.get(pred, {})
            flow_nodes.append({
                "id": pred,
                "type": "custom",
                "data": {
                    "label": p_data.get("name") or pred.split("::")[-1],
                    "nodeType": p_data.get("type", "Symbol"),
                    "path": p_data.get("path", pred.split("::")[0]),
                    "direction": "caller"
                },
                "position": {"x": 50, "y": 80 + (idx * 90)}
            })
        edata = ckg.graph[pred][target_id]
        flow_edges.append({
            "id": f"edge_{pred}_{target_id}",
            "source": pred,
            "target": target_id,
            "label": edata.get("type", "calls"),
            "animated": True,
            "style": {"stroke": "#6366f1"}
        })

    # Add direct successors (Dependencies/Callees)
    succs = list(ckg.graph.successors(target_id))[:max_nodes // 2]
    for idx, succ in enumerate(succs):
        if succ not in visited_node_ids:
            visited_node_ids.add(succ)
            s_data = ckg.graph.nodes.get(succ, {})
            flow_nodes.append({
                "id": succ,
                "type": "custom",
                "data": {
                    "label": s_data.get("name") or succ.split("::")[-1],
                    "nodeType": s_data.get("type", "Symbol"),
                    "path": s_data.get("path", succ.split("::")[0]),
                    "direction": "dependency"
                },
                "position": {"x": 550, "y": 80 + (idx * 90)}
            })
        edata = ckg.graph[target_id][succ]
        flow_edges.append({
            "id": f"edge_{target_id}_{succ}",
            "source": target_id,
            "target": succ,
            "label": edata.get("type", "calls"),
            "style": {"stroke": "#10b981"}
        })

    return {
        "center_node_id": target_id,
        "nodes": flow_nodes,
        "edges": flow_edges
    }
