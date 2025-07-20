from dataclasses import dataclass, field
from pathlib import Path

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
class FunctionDefinition:
    """
    Represents a function definition in the codebase.
    """
    name: str # The name of the function
    location: CodeLocation

@dataclass
class FunctionReference:
    """
    Represents a reference to a function in the codebase.
    """
    name: str # The name of the function
    location: CodeLocation
