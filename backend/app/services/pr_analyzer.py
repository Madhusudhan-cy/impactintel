from typing import List, Dict, Any, Optional, Tuple
import logging
from sqlalchemy.orm import Session

from app.db.models import Repository, PullRequestAnalysisRecord
from app.db.repository_store import RepositoryStore
from app.graph.builder import CodeKnowledgeGraph
from app.impact.engine import find_affected_components
from app.impact.models import ImpactAnalysisReport
from app.services.github_app import GitHubAppService

logger = logging.getLogger(__name__)


class PullRequestImpactService:
    """
    Core service that coordinates Pull Request change mapping,
    reverse dependency traversal on the stored base graph, and report persistence.
    Reused by both Webhook handlers and manual analysis endpoints.
    """

    def __init__(self, github_service: Optional[GitHubAppService] = None):
        self.github_service = github_service

    def analyze_pull_request(
        self,
        db: Session,
        full_name: str,
        pr_number: int,
        pr_title: str,
        base_branch: str,
        base_commit_sha: str,
        head_commit_sha: str,
        changed_files_info: List[Dict[str, Any]],
        post_github_comment: bool = False
    ) -> Tuple[PullRequestAnalysisRecord, ImpactAnalysisReport, List[str]]:
        """
        Analyze a Pull Request against the repository's indexed base graph.

        Args:
            changed_files_info: List of file objects with 'filename', 'status', and optional 'previous_filename'.
        """
        # 1. Fetch repository record
        repo = RepositoryStore.get_or_create_repository(db, full_name, default_branch=base_branch)

        # 2. Retrieve base branch's stored Code Knowledge Graph
        ckg, commit_index = RepositoryStore.load_graph(
            db=db,
            repository_id=repo.id,
            commit_sha=base_commit_sha if base_commit_sha != "HEAD" else None,
            branch=base_branch
        )

        if not ckg or not commit_index:
            raise ValueError(
                f"No indexed graph found for repository '{full_name}' on branch '{base_branch}'. "
                "Please index the repository before analyzing Pull Requests."
            )

        # 3. Map changed files to existing graph nodes
        mapped_changed_files: List[str] = []
        unmapped_files: List[str] = []

        for file_info in changed_files_info:
            filename = file_info.get("filename", "").strip()
            status = file_info.get("status", "modified")
            prev_filename = file_info.get("previous_filename")

            # Handle renamed or removed files
            target_path = prev_filename if status == "renamed" and prev_filename else filename

            if target_path in ckg.graph:
                mapped_changed_files.append(target_path)
            else:
                unmapped_files.append(f"{filename} ({status}: not present in base branch graph)")

        # 4. Perform reverse dependency impact analysis on the stored graph
        report = find_affected_components(
            graph_or_ckg=ckg,
            changed_files=mapped_changed_files,
            max_depth=3
        )

        # 5. Persist PR analysis and structured report
        analysis_record = RepositoryStore.save_pr_analysis(
            db=db,
            repository_id=repo.id,
            pr_number=pr_number,
            pr_title=pr_title,
            base_branch=base_branch,
            base_commit_sha=commit_index.commit_sha,
            head_commit_sha=head_commit_sha,
            report=report,
            unmapped_files=unmapped_files
        )

        # 6. Optional: Post GitHub PR Comment if requested
        if post_github_comment and self.github_service and repo.installation_id:
            try:
                comment_body = self.format_markdown_comment(
                    pr_number=pr_number,
                    pr_title=pr_title,
                    base_branch=base_branch,
                    commit_sha=commit_index.commit_sha,
                    report=report,
                    unmapped_files=unmapped_files
                )
                self.post_pr_comment(
                    full_name=full_name,
                    pr_number=pr_number,
                    comment_body=comment_body,
                    installation_id=repo.installation_id
                )
            except Exception as e:
                logger.warning(f"Failed to post GitHub PR comment: {e}")

        return analysis_record, report, unmapped_files

    @staticmethod
    def format_markdown_comment(
        pr_number: int,
        pr_title: str,
        base_branch: str,
        commit_sha: str,
        report: ImpactAnalysisReport,
        unmapped_files: List[str]
    ) -> str:
        """Construct a GitHub markdown summary comment."""
        lines = [
            f"### 🔍 AI-Powered Repository Impact Report for PR #{pr_number}",
            f"**PR Title**: {pr_title}",
            f"**Base Branch**: `{base_branch}` (`{commit_sha[:7]}`)",
            f"**Total Affected Components**: **{report.total_affected}**",
            "",
            "#### 📊 Potentially Affected Components"
        ]

        if not report.affected_components:
            lines.append("_No internal dependents identified within 3 traversal levels._")
        else:
            lines.append("| Component | Impact Level | Dependency Path |")
            lines.append("| :--- | :--- | :--- |")
            for comp in report.affected_components:
                path_str = " ➔ ".join(comp.dependency_path)
                lines.append(f"| `{comp.file_path}` | {comp.impact_level} | `{path_str}` |")

        # Identify tests
        tests = [c.file_path for c in report.affected_components if "test" in c.file_path.lower()]
        if tests:
            lines.append("")
            lines.append("#### 🧪 Related Tests to Inspect")
            for t in tests:
                lines.append(f"- `{t}`")

        if unmapped_files:
            lines.append("")
            lines.append("#### ℹ️ Unmapped Changes")
            for u in unmapped_files:
                lines.append(f"- {u}")

        lines.append("")
        lines.append("> _Note: Impact derived structurally via static reverse dependency traversal (max depth 3). No runtime tests were automatically executed._")
        return "\n".join(lines)

    def post_pr_comment(
        self,
        full_name: str,
        pr_number: int,
        comment_body: str,
        installation_id: int
    ) -> None:
        """Post a comment to the GitHub PR issue endpoint."""
        if not self.github_service:
            return

        token = self.github_service.get_installation_access_token(installation_id)
        parts = full_name.split("/")
        owner, repo = parts[0], parts[1]
        url = f"{self.github_service.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"

        import httpx
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=headers, json={"body": comment_body})
            response.raise_for_status()
