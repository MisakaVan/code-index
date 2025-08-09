"""Pydantic models for representing code elements and their relationships.

This module defines the core data structures used to model functions, methods,
references, definitions, and their relationships in a codebase.
"""

from pathlib import Path
from typing import List, Literal, Annotated, Any

from pydantic import BaseModel, Field, Discriminator

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


class CodeLocation(BaseModel):
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

    model_config = {"frozen": True}


class Function(BaseModel):
    """Represents a standalone function in the codebase.

    A function is a callable code block that is not bound to any class.
    This includes module-level functions, nested functions, and lambda functions.
    """

    type: Literal["function"] = "function"
    """Type discriminator for function."""
    name: str
    """The name of the function."""

    model_config = {"frozen": True}


class Method(BaseModel):
    """Represents a method bound to a class in the codebase.

    A method is a function that belongs to a class. The class_name may be None
    for method calls where the class context cannot be determined statically.
    """

    type: Literal["method"] = "method"
    """Type discriminator for method."""
    name: str
    """The name of the method."""
    class_name: str | None
    """The name of the class the method belongs to. May be None for calls where the class context is not accessible or determinable."""

    model_config = {"frozen": True}


FunctionLike = Annotated[
    Function | Method,
    Field(discriminator="type", description="Discriminated union for function-like entities."),
]
"""Represents a function or method in the codebase. A discriminated union type that can be either a Function or a Method.

The discriminator field 'type' is used to determine which variant to deserialize to.
Pydantic automatically handles serialization and deserialization based on this field.

Example usage:

.. code-block:: python

    from pydantic import TypeAdapter

    # For standalone validation of FunctionLike objects
    funclike_adapter = TypeAdapter(FunctionLike)
    
    # Validate from dict
    func_data = {"type": "function", "name": "my_func"}
    function_obj = funclike_adapter.validate_python(func_data)
    
    # Validate from JSON
    method_json = '{"type": "method", "name": "my_method", "class_name": "MyClass"}'
    method_obj = funclike_adapter.validate_json(method_json)
"""


class Reference(BaseModel):
    """Represents a reference to a function or method in the codebase.

    A reference occurs when a function or method is called, passed as an argument,
    or otherwise used in the code (but not where it's defined).
    """

    location: CodeLocation
    """The code location where the reference occurs."""


class FunctionLikeRef(BaseModel):
    """Represents a reference to a function-like entity with context.

    This combines a function or method symbol with the specific reference location,
    providing full context about where and what is being referenced.
    """

    symbol: FunctionLike
    """The function or method being referenced."""
    reference: Reference
    """The reference information including location."""


class Definition(BaseModel):
    """Represents a function or method definition in the codebase.

    A definition is where a function or method is declared/implemented.
    It includes the location of the definition and tracks any function calls
    made within the definition body.
    """

    location: CodeLocation
    """The code location where the definition occurs."""
    calls: List[FunctionLikeRef] = Field(default_factory=list)
    """List of function/method calls made within this definition."""


class FunctionLikeDef(BaseModel):
    """Represents a definition of a function-like entity with context.

    This combines a function or method symbol with the specific definition information,
    providing full context about where and what is being defined.
    """

    symbol: FunctionLike
    """The function or method being defined."""
    definition: Definition
    """The definition information including location and calls."""


class FunctionLikeInfo(BaseModel):
    """Contains comprehensive information about a function or method.

    Aggregates all known information about a function or method, including
    all its definitions (in case of overloads or multiple declarations)
    and all references to it throughout the codebase.
    """

    definitions: List[Definition] = Field(default_factory=list)
    """List of all definition locations for this symbol."""
    references: List[Reference] = Field(default_factory=list)
    """List of all reference locations for this symbol."""


class IndexDataEntry(BaseModel):
    """Represents a single entry in the serialized index data.

    Each entry associates a function or method symbol with its complete
    information including definitions and references.
    """

    symbol: FunctionLike
    """The function or method symbol."""
    info: FunctionLikeInfo
    """Complete information about the symbol."""


class IndexData(BaseModel):
    """Represents the complete index data in a serializable format.

    This is the top-level container for all indexed information about
    functions and methods in a codebase. Used for persistence and
    data exchange between different index implementations.
    """

    type: str
    """String identifier indicating the index type (e.g., "simple_index")."""
    data: List[IndexDataEntry] = Field(default_factory=list)
    """List of all indexed symbol entries."""
    metadata: dict[Any, Any] | None = None
    """Optional metadata about the index, such as the indexer version, creation timestamp, etc."""
