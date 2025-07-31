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

    Attributes:
        file_path: Path to the source file containing this location.
        start_lineno: Starting line number (1-based).
        start_col: Starting column number (0-based).
        end_lineno: Ending line number (1-based).
        end_col: Ending column number (0-based).
        start_byte: Byte offset where the location starts (inclusive).
        end_byte: Byte offset where the location ends (exclusive).
    """

    file_path: Path
    start_lineno: int
    start_col: int
    end_lineno: int
    end_col: int
    start_byte: int  # Byte offset in the file where the location starts (including)
    end_byte: int  # Byte offset in the file where the location ends (not including)


@register_json_type
@dataclass(frozen=True)
class Function:
    """Represents a standalone function in the codebase.

    A function is a callable code block that is not bound to any class.
    This includes module-level functions, nested functions, and lambda functions.

    Attributes:
        name: The name of the function.
    """

    name: str  # The name of the function


@register_json_type
@dataclass(frozen=True)
class Method:
    """Represents a method bound to a class in the codebase.

    A method is a function that belongs to a class. The class_name may be None
    for method calls where the class context cannot be determined statically.

    Attributes:
        name: The name of the method.
        class_name: The name of the class the method belongs to. May be None
            for calls where the class context is not accessible or determinable.
    """

    name: str

    # The name of the class the method belongs to. May not be accessible on calls.
    class_name: str | None


FunctionLike = Function | Method


@register_json_type
@dataclass
class Reference:
    """Represents a reference to a function or method in the codebase.

    A reference occurs when a function or method is called, passed as an argument,
    or otherwise used in the code (but not where it's defined).

    Attributes:
        location: The code location where the reference occurs.
    """

    location: CodeLocation


@register_json_type
@dataclass
class FunctionLikeRef:
    """Represents a reference to a function-like entity with context.

    This combines a function or method symbol with the specific reference location,
    providing full context about where and what is being referenced.

    Attributes:
        symbol: The function or method being referenced.
        reference: The reference information including location.
    """

    symbol: FunctionLike
    reference: Reference


@register_json_type
@dataclass
class Definition:
    """Represents a function or method definition in the codebase.

    A definition is where a function or method is declared/implemented.
    It includes the location of the definition and tracks any function calls
    made within the definition body.

    Attributes:
        location: The code location where the definition occurs.
        calls: List of function/method calls made within this definition.
    """

    location: CodeLocation
    calls: list[FunctionLikeRef] = field(default_factory=list)


@register_json_type
@dataclass
class FunctionLikeInfo:
    """Contains comprehensive information about a function or method.

    Aggregates all known information about a function or method, including
    all its definitions (in case of overloads or multiple declarations)
    and all references to it throughout the codebase.

    Attributes:
        definitions: List of all definition locations for this symbol.
        references: List of all reference locations for this symbol.
    """

    definitions: list[Definition] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)


@register_json_type
@dataclass
class IndexDataEntry:
    """Represents a single entry in the serialized index data.

    Each entry associates a function or method symbol with its complete
    information including definitions and references.

    Attributes:
        symbol: The function or method symbol.
        info: Complete information about the symbol.
    """

    symbol: FunctionLike
    info: FunctionLikeInfo


@register_json_type
@dataclass
class IndexData:
    """Represents the complete index data in a serializable format.

    This is the top-level container for all indexed information about
    functions and methods in a codebase. Used for persistence and
    data exchange between different index implementations.

    Attributes:
        type: String identifier indicating the index type (e.g., "simple_index").
        data: List of all indexed symbol entries.
    """

    type: str
    data: list[IndexDataEntry] = field(default_factory=list)
