"""Dataclasses for representing code elements and their relationships.

This module defines the core data structures used to model functions, methods,
references, definitions, and their relationships in a codebase.
"""

from dataclasses import dataclass, field
from pathlib import Path

from .utils.custom_json import register_json_type

__all__ = [
    "CodeLocation",
    "Function",
    "Method",
    "FunctionLike",
    "FunctionLikeRef",
    "Reference",
    "Definition",
    "FunctionLikeInfo",
    "IndexDataEntry",
    "IndexData",
]


@register_json_type
@dataclass(frozen=True)
class CodeLocation:
    """Represents a specific location in source code.

    Contains precise position information including line numbers, column positions,
    and byte offsets for a code element within a source file.
    """

    file_path: Path
    """Path to the source file containing this location."""
    start_lineno: int
    """Starting line number (1-based)."""
    start_col: int
    """Starting column number (0-based)."""
    end_lineno: int
    """Ending line number (1-based)."""
    end_col: int
    """Ending column number (0-based)."""
    start_byte: int
    """Byte offset in the file where the location starts (including)."""
    end_byte: int
    """Byte offset in the file where the location ends (not including)."""


@register_json_type
@dataclass(frozen=True)
class Function:
    """Represents a standalone function in the codebase.

    A function is a callable code block that is not bound to any class.
    This includes module-level functions, nested functions, and lambda functions.
    """

    name: str
    """The name of the function."""


@register_json_type
@dataclass(frozen=True)
class Method:
    """Represents a method bound to a class in the codebase.

    A method is a function that belongs to a class. The class_name may be None
    for method calls where the class context cannot be determined statically.
    """

    name: str
    """The name of the method."""
    class_name: str | None
    """The name of the class the method belongs to. May be None for calls where the class context is not accessible or determinable."""


FunctionLike = Function | Method
"""Represents a function or method in the codebase."""


@register_json_type
@dataclass
class Reference:
    """Represents a reference to a function or method in the codebase.

    A reference occurs when a function or method is called, passed as an argument,
    or otherwise used in the code (but not where it's defined).
    """

    location: CodeLocation
    """The code location where the reference occurs."""


@register_json_type
@dataclass
class FunctionLikeRef:
    """Represents a reference to a function-like entity with context.

    This combines a function or method symbol with the specific reference location,
    providing full context about where and what is being referenced.
    """

    symbol: FunctionLike
    """The function or method being referenced."""
    reference: Reference
    """The reference information including location."""


@register_json_type
@dataclass
class Definition:
    """Represents a function or method definition in the codebase.

    A definition is where a function or method is declared/implemented.
    It includes the location of the definition and tracks any function calls
    made within the definition body.
    """

    location: CodeLocation
    """The code location where the definition occurs."""
    calls: list[FunctionLikeRef] = field(default_factory=list)
    """List of function/method calls made within this definition."""


@register_json_type
@dataclass
class FunctionLikeInfo:
    """Contains comprehensive information about a function or method.

    Aggregates all known information about a function or method, including
    all its definitions (in case of overloads or multiple declarations)
    and all references to it throughout the codebase.
    """

    definitions: list[Definition] = field(default_factory=list)
    """List of all definition locations for this symbol."""
    references: list[Reference] = field(default_factory=list)
    """List of all reference locations for this symbol."""


@register_json_type
@dataclass
class IndexDataEntry:
    """Represents a single entry in the serialized index data.

    Each entry associates a function or method symbol with its complete
    information including definitions and references.
    """

    symbol: FunctionLike
    """The function or method symbol."""
    info: FunctionLikeInfo
    """Complete information about the symbol."""


@register_json_type
@dataclass
class IndexData:
    """Represents the complete index data in a serializable format.

    This is the top-level container for all indexed information about
    functions and methods in a codebase. Used for persistence and
    data exchange between different index implementations.
    """

    type: str
    """String identifier indicating the index type (e.g., "simple_index")."""
    data: list[IndexDataEntry] = field(default_factory=list)
    """List of all indexed symbol entries."""
