from dataclasses import dataclass, field
from pathlib import Path

from .utils.custom_json import register_json_type


@register_json_type
@dataclass(frozen=True)
class CodeLocation:
    """
    Represents a location in the codebase.
    """

    file_path: Path
    start_lineno: int
    start_col: int
    end_lineno: int
    end_col: int


@register_json_type
@dataclass(frozen=True)
class Function:
    """
    Represents a function in the codebase.
    """

    name: str  # The name of the function


@register_json_type
@dataclass(frozen=True)
class Method:
    """
    Represents a method in the codebase.
    """

    name: str

    # The name of the class the method belongs to. May not be accessible on calls.
    class_name: str | None


FunctionLike = Function | Method


@register_json_type
@dataclass
class Definition:
    """
    Represents a function definition in the codebase.
    """

    location: CodeLocation


@register_json_type
@dataclass
class Reference:
    """
    Represents a reference to a function in the codebase.
    """

    location: CodeLocation


@register_json_type
@dataclass
class FunctionLikeInfo:
    """
    Represents information about a function, including its definition(s) and references.
    """

    definitions: list[Definition] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
