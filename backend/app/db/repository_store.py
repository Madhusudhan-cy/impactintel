from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session

from app.db.models import (
    Repository,
    CommitIndex,
    GraphNodeRecord,
    GraphEdgeRecord,
    PullRequestAnalysisRecord,
    ImpactReportRecord
)
from app.graph.schema import Node, NodeType, DependencyEdge, RelationType
from app.graph.builder import CodeKnowledgeGraph
from app.impact.models import ImpactAnalysisReport


class RepositoryStore:
    """
    Persistence adapter for storing and reconstructing Code Knowledge Graphs,
    repository metadata, and Pull Request impact analysis records in PostgreSQL.
    """

    @staticmethod
    def get_or_create_repository(
        db: Session,
        full_name: str,
        default_branch: str = "main",
        installation_id: Optional[int] = None
    ) -> Repository:
        repo = db.query(Repository).filter(Repository.full_name == full_name).first()
        if not repo:
            parts = full_name.split("/")
            owner = parts[0] if len(parts) > 1 else "default"
            name = parts[1] if len(parts) > 1 else full_name
            repo = Repository(
                name=name,
                full_name=full_name,
                owner=owner,
                default_branch=default_branch,
                installation_id=installation_id
            )
            db.add(repo)
            db.commit()
            db.refresh(repo)
        else:
            updated = False
            if installation_id is not None and repo.installation_id != installation_id:
                repo.installation_id = installation_id
                updated = True
            if default_branch and repo.default_branch != default_branch:
                repo.default_branch = default_branch
                updated = True
            if updated:
                db.commit()
                db.refresh(repo)
        return repo

    @staticmethod
    def save_graph(
        db: Session,
        repository_id: int,
        branch: str,
        commit_sha: str,
        ckg: CodeKnowledgeGraph,
        status: str = "INDEXED"
    ) -> CommitIndex:
        """
        Persist a Code Knowledge Graph into the database under a specific commit SHA.
        """
        # Find or create CommitIndex record
        commit_index = (
            db.query(CommitIndex)
            .filter(CommitIndex.repository_id == repository_id, CommitIndex.commit_sha == commit_sha)
            .first()
        )
        if not commit_index:
            commit_index = CommitIndex(
                repository_id=repository_id,
                branch=branch,
                commit_sha=commit_sha,
                status=status,
                total_nodes=ckg.node_count,
                total_edges=ckg.edge_count,
                indexed_at=datetime.now(timezone.utc)
            )
            db.add(commit_index)
            db.commit()
            db.refresh(commit_index)
        else:
            # Clear previous nodes and edges for re-indexing
            db.query(GraphNodeRecord).filter(GraphNodeRecord.commit_index_id == commit_index.id).delete()
            db.query(GraphEdgeRecord).filter(GraphEdgeRecord.commit_index_id == commit_index.id).delete()
            commit_index.status = status
            commit_index.total_nodes = ckg.node_count
            commit_index.total_edges = ckg.edge_count
            commit_index.indexed_at = datetime.now(timezone.utc)
            db.commit()

        # Persist nodes
        for node_id, data in ckg.graph.nodes(data=True):
            node_record = GraphNodeRecord(
                commit_index_id=commit_index.id,
                node_id=node_id,
                node_type=data.get("type", "File"),
                language=data.get("language", "javascript"),
                meta_data={k: v for k, v in data.items() if k not in ("type", "language", "path")}
            )
            db.add(node_record)

        # Persist edges
        for u, v, data in ckg.graph.edges(data=True):
            evidence = data.get("evidence", [])
            first_line = evidence[0]["line"] if evidence and "line" in evidence[0] else None
            first_stmt = evidence[0]["statement"] if evidence and "statement" in evidence[0] else None
            first_conf = evidence[0]["confidence"] if evidence and "confidence" in evidence[0] else 1.0
            first_ext = evidence[0]["extractor"] if evidence and "extractor" in evidence[0] else "tree_sitter"

            edge_record = GraphEdgeRecord(
                commit_index_id=commit_index.id,
                source=u,
                target=v,
                edge_type=data.get("type", "imports"),
                file=data.get("file", u),
                line=first_line,
                statement=first_stmt,
                confidence=first_conf,
                extractor=first_ext,
                evidence=evidence
            )
            db.add(edge_record)

        db.commit()
        db.refresh(commit_index)
        return commit_index

    @staticmethod
    def load_graph(
        db: Session,
        repository_id: int,
        commit_sha: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Tuple[Optional[CodeKnowledgeGraph], Optional[CommitIndex]]:
        """
        Reconstruct a CodeKnowledgeGraph instance from database records.
        """
        query = db.query(CommitIndex).filter(CommitIndex.repository_id == repository_id)
        if commit_sha:
            query = query.filter(CommitIndex.commit_sha == commit_sha)
        elif branch:
            query = query.filter(CommitIndex.branch == branch).order_by(CommitIndex.indexed_at.desc())
        else:
            query = query.order_by(CommitIndex.indexed_at.desc())

        commit_index = query.first()
        if not commit_index:
            return None, None

        # Reconstruct nodes
        node_records = db.query(GraphNodeRecord).filter(GraphNodeRecord.commit_index_id == commit_index.id).all()
        nodes = [
            Node(
                id=nr.node_id,
                type=NodeType(nr.node_type) if nr.node_type in [e.value for e in NodeType] else NodeType.FILE,
                path=nr.node_id,
                language=nr.language,
                metadata=nr.meta_data or {}
            )
            for nr in node_records
        ]

        # Reconstruct edges
        edge_records = db.query(GraphEdgeRecord).filter(GraphEdgeRecord.commit_index_id == commit_index.id).all()
        edges = []
        for er in edge_records:
            # Recreate each edge with its evidence
            rel_type = RelationType(er.edge_type) if er.edge_type in [e.value for e in RelationType] else RelationType.IMPORTS
            if er.evidence and len(er.evidence) > 0:
                for ev in er.evidence:
                    edges.append(
                        DependencyEdge(
                            source=er.source,
                            target=er.target,
                            type=rel_type,
                            file=er.file,
                            line=ev.get("line", er.line or 1),
                            statement=ev.get("statement", er.statement),
                            confidence=ev.get("confidence", er.confidence),
                            extractor=ev.get("extractor", er.extractor)
                        )
                    )
            else:
                edges.append(
                    DependencyEdge(
                        source=er.source,
                        target=er.target,
                        type=rel_type,
                        file=er.file,
                        line=er.line or 1,
                        statement=er.statement,
                        confidence=er.confidence,
                        extractor=er.extractor
                    )
                )

        ckg = CodeKnowledgeGraph.from_nodes_and_edges(nodes, edges)
        return ckg, commit_index

    @staticmethod
    def save_pr_analysis(
        db: Session,
        repository_id: int,
        pr_number: int,
        pr_title: str,
        base_branch: str,
        base_commit_sha: str,
        head_commit_sha: str,
        report: ImpactAnalysisReport,
        unmapped_files: Optional[List[str]] = None
    ) -> PullRequestAnalysisRecord:
        """
        Persist a Pull Request impact analysis run and its structured report.
        """
        unmapped = unmapped_files or []
        pr_record = (
            db.query(PullRequestAnalysisRecord)
            .filter(
                PullRequestAnalysisRecord.repository_id == repository_id,
                PullRequestAnalysisRecord.pr_number == pr_number
            )
            .first()
        )

        if not pr_record:
            pr_record = PullRequestAnalysisRecord(
                repository_id=repository_id,
                pr_number=pr_number,
                pr_title=pr_title,
                base_branch=base_branch,
                base_commit_sha=base_commit_sha,
                head_commit_sha=head_commit_sha,
                status="COMPLETED",
                total_affected=report.total_affected
            )
            db.add(pr_record)
            db.commit()
            db.refresh(pr_record)
        else:
            pr_record.pr_title = pr_title
            pr_record.base_branch = base_branch
            pr_record.base_commit_sha = base_commit_sha
            pr_record.head_commit_sha = head_commit_sha
            pr_record.status = "COMPLETED"
            pr_record.total_affected = report.total_affected
            # Remove previous impact report if any
            db.query(ImpactReportRecord).filter(ImpactReportRecord.pr_analysis_id == pr_record.id).delete()
            db.commit()

        # Serialize affected components to JSON
        affected_json = [c.model_dump() for c in report.affected_components]

        impact_report = ImpactReportRecord(
            pr_analysis_id=pr_record.id,
            changed_files=report.changed_files,
            affected_components=affected_json,
            unaffected_files=report.unaffected_files,
            unmapped_files=unmapped,
            total_affected=report.total_affected
        )
        db.add(impact_report)
        db.commit()
        db.refresh(pr_record)
        return pr_record

    @staticmethod
    def get_pr_analysis(
        db: Session,
        repository_id: int,
        pr_number: int
    ) -> Optional[PullRequestAnalysisRecord]:
        return (
            db.query(PullRequestAnalysisRecord)
            .filter(
                PullRequestAnalysisRecord.repository_id == repository_id,
                PullRequestAnalysisRecord.pr_number == pr_number
            )
            .first()
        )

    @staticmethod
    def list_pr_analyses(
        db: Session,
        repository_id: int
    ) -> List[PullRequestAnalysisRecord]:
        return (
            db.query(PullRequestAnalysisRecord)
            .filter(PullRequestAnalysisRecord.repository_id == repository_id)
            .order_by(PullRequestAnalysisRecord.created_at.desc())
            .all()
        )
