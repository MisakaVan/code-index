"""Query interfaces for searching code symbols in the index.

This module defines various query types to search for functions and methods
in the code index. It includes exact key matches, name-based searches, and
regex-based searches.
"""

from dataclasses import dataclass, field
from enum import Enum

from code_index.models import FunctionLike, FunctionLikeInfo


@dataclass(frozen=True)
class QueryByKey:
    """Query for exact function or method matches by key.

    This query type returns exact matches in the index using the complete
    function or method signature as the key.

    Examples:
        Query a function: QueryByKey(func_like=Function(name="my_function"))
        Query a method: QueryByKey(func_like=Method(name="my_method", class_name="MyClass"))
        Query unbound method: QueryByKey(func_like=Method(name="my_method", class_name=None))

    """

    func_like: FunctionLike
    """The function or method to search for exactly."""


class FilterOption(Enum):
    """Filter options for symbol types in queries."""

    FUNCTION = "function"
    """Filter for standalone functions only."""
    METHOD = "method"
    """Filter for class methods only."""
    ALL = "all"
    """Include both functions and methods in results."""


@dataclass(frozen=True)
class QueryByName:
    """Query for functions and methods by name with optional type filtering.

    Finds all symbols with the specified name, optionally filtered by type.
    This is useful for finding all occurrences of symbols with the same name.

    Examples:
        Query functions: QueryByName(name="my_function", type_filter=FilterOption.FUNCTION)
        Query methods: QueryByName(name="my_method", type_filter=FilterOption.METHOD)
        Query all symbols: QueryByName(name="my_symbol", type_filter=FilterOption.ALL)
    """

    name: str
    """The exact name of the function or method to search for."""
    type_filter: FilterOption = field(default=FilterOption.ALL)
    """The type of symbols to include in results. Defaults to ALL."""


@dataclass(frozen=True)
class QueryByNameRegex:
    """Query for functions and methods by regex name pattern with optional type filtering.

    Finds all symbols whose names match the specified regex pattern, optionally
    filtered by type. This is useful for pattern-based searches.

    Examples:
        Query test functions: QueryByNameRegex(name_regex=r"^test_.*", type_filter=FilterOption.FUNCTION)
        Query handler methods: QueryByNameRegex(name_regex=r".*_handler$", type_filter=FilterOption.METHOD)
        Query debug symbols: QueryByNameRegex(name_regex=r".*debug.*", type_filter=FilterOption.ALL)
    """

    name_regex: str
    """The regex pattern to match function or method names."""
    type_filter: FilterOption = field(default=FilterOption.ALL)
    """The type of symbols to include in results. Defaults to ALL."""


CodeQuery = QueryByKey | QueryByName | QueryByNameRegex
"""Represents a query for code symbols in the index."""


@dataclass(frozen=True)
class CodeQuerySingleResponse:
    """Represents a single response from a code query.

    Contains the function or method information along with its associated
    definitions and references from the index.
    """

    func_like: FunctionLike
    """The function or method that matched the query."""
    info: FunctionLikeInfo
    """The complete information about the function or method, including definitions and references."""
