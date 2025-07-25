from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


@dataclass
class CodeLocation:
    """
    Represents a location in the codebase.
    """

    file_path: Path
    start_lineno: int
    start_col: int
    end_lineno: int
    end_col: int


@dataclass
class Function:
    """
    Represents a function in the codebase.
    """

    name: str  # The name of the function


@dataclass
class Method:
    """
    Represents a method in the codebase.
    """

    name: str
    class_name: str


FunctionLike = Function | Method


@dataclass
class Definition:
    """
    Represents a function definition in the codebase.
    """

    name: str  # The name of the function
    location: CodeLocation


@dataclass
class Reference:
    """
    Represents a reference to a function in the codebase.
    """

    name: str  # The name of the function
    location: CodeLocation


@dataclass
class FunctionLikeInfo:
    """
    Represents information about a function, including its definition(s) and references.
    """

    definition: list[Definition] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
