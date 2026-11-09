from enum import Enum
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    FILE = "File"
    FUNCTION = "Function"
    CLASS = "Class"
    COMPONENT = "Component"
    API_ROUTE = "ApiRoute"
    TEST = "Test"


class RelationType(str, Enum):
    IMPORTS = "imports"
    DEFINES = "defines"
    CALLS = "calls"
    RENDERS = "renders"
    EXPOSES = "exposes"
    HANDLED_BY = "handled_by"
    FETCHES = "fetches"
    TESTS = "tests"


class Node(BaseModel):
    """
    Normalized Code Knowledge Graph node.
    Represents files, functions, classes, components, API routes, or tests.
    """
    id: str  # Unique repo-relative identifier, e.g. "src/services/paymentService.js::processPayment"
    type: NodeType = NodeType.FILE
    path: str  # Relative file path from repository root
    name: Optional[str] = None  # Symbol name (e.g. "processPayment", "PaymentService", "POST /api/payment")
    language: str = "javascript"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create_file(cls, path: str, language: str = "javascript", metadata: Optional[Dict[str, Any]] = None) -> "Node":
        return cls(id=path, type=NodeType.FILE, path=path, name=path, language=language, metadata=metadata or {})

    @classmethod
    def create_function(cls, file_path: str, function_name: str, language: str = "javascript", metadata: Optional[Dict[str, Any]] = None) -> "Node":
        node_id = f"{file_path}::{function_name}"
        return cls(id=node_id, type=NodeType.FUNCTION, path=file_path, name=function_name, language=language, metadata=metadata or {})

    @classmethod
    def create_class(cls, file_path: str, class_name: str, language: str = "javascript", metadata: Optional[Dict[str, Any]] = None) -> "Node":
        node_id = f"{file_path}::{class_name}"
        return cls(id=node_id, type=NodeType.CLASS, path=file_path, name=class_name, language=language, metadata=metadata or {})

    @classmethod
    def create_component(cls, file_path: str, component_name: str, language: str = "javascript", metadata: Optional[Dict[str, Any]] = None) -> "Node":
        node_id = f"{file_path}::{component_name}"
        return cls(id=node_id, type=NodeType.COMPONENT, path=file_path, name=component_name, language=language, metadata=metadata or {})

    @classmethod
    def create_api_route(cls, method: str, route_path: str, source_file: str, language: str = "javascript", metadata: Optional[Dict[str, Any]] = None) -> "Node":
        clean_method = method.upper()
        clean_path = route_path if route_path.startswith("/") else f"/{route_path}"
        node_id = f"{clean_method} {clean_path}"
        return cls(id=node_id, type=NodeType.API_ROUTE, path=source_file, name=node_id, language=language, metadata=metadata or {})

    @classmethod
    def create_test(cls, file_path: str, test_name: str, language: str = "javascript", metadata: Optional[Dict[str, Any]] = None) -> "Node":
        node_id = f"{file_path}::{test_name}"
        return cls(id=node_id, type=NodeType.TEST, path=file_path, name=test_name, language=language, metadata=metadata or {})


class DependencyEdge(BaseModel):
    """
    Normalized Code Knowledge Graph directed edge.
    Canonical direction: Caller / Dependent (source) ➔ Dependency (target).
    Examples:
        - caller_function ──[calls]──> callee_function
        - file ──[defines]──> function_or_class
        - component ──[renders]──> child_component
        - api_route ──[handled_by]──> controller_function
        - frontend_function ──[fetches]──> api_route
        - test_function ──[tests]──> target_function
    """
    source: str  # Dependent node ID (the caller, parent, or importing entity)
    target: str  # Dependency node ID (the callee, child, or imported entity)
    type: RelationType = RelationType.IMPORTS
    file: str  # Originating source file path
    line: int  # 1-based line number where relationship is declared
    statement: Optional[str] = None  # Verbatim source code snippet
    confidence: float = 1.0
    extractor: str = "tree_sitter"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedImport(BaseModel):
    """Raw import extraction record prior to graph ingestion."""
    source_file: str  # Repo-relative path of the importing file
    raw_specifier: str  # Exact string in the import statement
    resolved_path: Optional[str] = None  # Repo-relative path if resolved internal file
    line_number: int  # 1-based line number
    statement: str  # Full import statement text
    is_external: bool = False  # True for third-party packages (e.g. 'axios', 'express')
    is_resolved: bool = False  # True if internal file was matched on disk
    imported_symbols: List[str] = Field(default_factory=list)  # Named imports, e.g. ['processPayment', 'validatePayment']
    default_import: Optional[str] = None  # Default imported identifier, e.g. 'db'
    is_namespace: bool = False  # True if import * as db from '...'
    namespace_alias: Optional[str] = None


class ExtractedSymbol(BaseModel):
    """Normalized symbol definition discovered by language extractors."""
    name: str
    symbol_type: NodeType
    file_path: str
    start_line: int
    end_line: int
    is_exported: bool = False
    scope: Optional[str] = None  # Containing class or parent function if applicable
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def node_id(self) -> str:
        if self.scope:
            return f"{self.file_path}::{self.scope}.{self.name}"
        return f"{self.file_path}::{self.name}"


class ExtractedCall(BaseModel):
    """Raw function/method call record."""
    caller_file: str
    caller_symbol: Optional[str] = None  # Containing function or class method
    callee_name: str  # Verbatim call expression (e.g. 'validatePayment', 'this.verify', 'db.query')
    line_number: int
    statement: str
    resolved_target_id: Optional[str] = None  # Canonical node ID if resolved statically
    is_resolved: bool = False
