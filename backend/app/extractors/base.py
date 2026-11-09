from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple
from app.graph.schema import Node, DependencyEdge, ExtractedImport


class BaseExtractor(ABC):
    """Abstract base class for all language-specific repository extractors."""

    @abstractmethod
    def extract_file(self, file_path: Path, repo_root: Path) -> List[ExtractedImport]:
        """Extract import relationships from a single source file."""
        pass

    @abstractmethod
    def extract_repository(self, repo_root: Path) -> Tuple[List[Node], List[DependencyEdge], List[ExtractedImport]]:
        """
        Scan and extract all nodes, resolved dependency edges, and raw import records
        from a repository.
        """
        pass
