from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DependencyHop(BaseModel):
    """Represents a single step in a reverse dependency chain."""
    dependent: str  # The file or symbol that imports/calls/renders
    dependency: str  # The file or symbol being imported/called/rendered
    relation_type: str = "imports"  # imports, defines, calls, renders, handled_by, fetches, tests
    line: Optional[int] = None
    statement: Optional[str] = None


class AffectedComponent(BaseModel):
    """Normalized record of a potentially affected entity (function, class, component, file)."""
    file_path: str  # Node ID or file path
    entity_type: str = "File"  # File, Function, Class, Component, ApiRoute, Test
    depth: int  # 1 for Direct, 2 or 3 for Indirect
    impact_level: str  # "Direct (Depth 1)" or "Indirect (Depth N)"
    dependency_path: List[str]  # e.g., ["src/services/paymentService.js::processPayment", "src/routes/paymentRoutes.js::handlePaymentRequest"]
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


class ImpactAnalysisReport(BaseModel):
    """Comprehensive impact analysis result contract."""
    changed_files: List[str]  # Changed files or symbols
    analysis_level: str = "file-level"  # "symbol-level" or "file-level"
    max_depth: int = 3
    total_affected: int
    affected_components: List[AffectedComponent]
    related_tests: List[str] = Field(default_factory=list)
    unaffected_files: List[str] = Field(default_factory=list)
