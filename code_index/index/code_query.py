"""Query interfaces for searching code symbols in the index.

This module defines various query types to search for functions and methods
in the code index. It includes exact key matches, name-based searches, and
regex-based searches.
"""

from enum import Enum

from pydantic import BaseModel, Field

from code_index.models import FunctionLike, FunctionLikeInfo, PureDefinition


class QueryByKey(BaseModel):
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

    model_config = {"frozen": True}


class FilterOption(Enum):
    """Filter options for symbol types in queries."""

    FUNCTION = "function"
    """Filter for standalone functions only."""
    METHOD = "method"
    """Filter for class methods only."""
    ALL = "all"
    """Include both functions and methods in results."""


class QueryByName(BaseModel):
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
    type_filter: FilterOption = Field(default=FilterOption.ALL)
    """The type of symbols to include in results. Defaults to ALL."""

    model_config = {"frozen": True}


class QueryByNameRegex(BaseModel):
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
    type_filter: FilterOption = Field(default=FilterOption.ALL)
    """The type of symbols to include in results. Defaults to ALL."""

    model_config = {"frozen": True}


class QueryFullDefinition(BaseModel):
    """Given a symbol and a location, return the full definition of that symbol.

    This is useful for navigating to the complete definition of a symbol from
    a specific location in the codebase.

    The result of this query (the FunctionLikeInfo) will only contain the corresponding
    Definition that matches the provided PureDefinition. If there is no match, the result
    will be empty.
    """

    symbol: FunctionLike
    """The function or method symbol to look up."""
    pure_definition: PureDefinition
    """The specific location in the codebase to find the full definition from."""

    model_config = {"frozen": True}


CodeQuery = QueryByKey | QueryByName | QueryByNameRegex | QueryFullDefinition
"""Represents a query for code symbols in the index."""


class CodeQuerySingleResponse(BaseModel):
    """Represents a single response from a code query.

    Contains the function or method information along with its associated
    definitions and references from the index.
    """

    func_like: FunctionLike
    """The function or method that matched the query."""
    info: FunctionLikeInfo
    """The complete information about the function or method, including definitions and references."""


class CodeQueryResponse(BaseModel):
    """Represents the response for a code query.

    Contains a list of results matching the query criteria.
    """

    results: list[CodeQuerySingleResponse] = Field(default_factory=list)
    """List of matching function or method information."""
