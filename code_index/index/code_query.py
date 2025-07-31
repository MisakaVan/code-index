# code_index/index/code_query.py
# Query interfaces for the code index

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

    Attributes:
        func_like: The function or method to search for exactly.
    """

    func_like: FunctionLike


class FilterOption(Enum):
    """Filter options for symbol types in queries.

    Attributes:
        FUNCTION: Filter for standalone functions only.
        METHOD: Filter for class methods only.
        ALL: Include both functions and methods.
    """

    FUNCTION = "function"
    METHOD = "method"
    ALL = "all"


@dataclass(frozen=True)
class QueryByName:
    """Query for functions and methods by name with optional type filtering.

    Finds all symbols with the specified name, optionally filtered by type.
    This is useful for finding all occurrences of symbols with the same name.

    Examples:
        Query functions: QueryByName(name="my_function", type_filter=FilterOption.FUNCTION)
        Query methods: QueryByName(name="my_method", type_filter=FilterOption.METHOD)
        Query all symbols: QueryByName(name="my_symbol", type_filter=FilterOption.ALL)

    Attributes:
        name: The exact name to search for.
        type_filter: The type of symbols to include in results.
    """

    name: str
    type_filter: FilterOption = field(default=FilterOption.ALL)


@dataclass(frozen=True)
class QueryByNameRegex:
    """Query for functions and methods by regex name pattern with optional type filtering.

    Finds all symbols whose names match the specified regex pattern, optionally
    filtered by type. This is useful for pattern-based searches.

    Examples:
        Query test functions: QueryByNameRegex(name_regex=r"^test_.*", type_filter=FilterOption.FUNCTION)
        Query handler methods: QueryByNameRegex(name_regex=r".*_handler$", type_filter=FilterOption.METHOD)
        Query debug symbols: QueryByNameRegex(name_regex=r".*debug.*", type_filter=FilterOption.ALL)

    Attributes:
        name_regex: The regex pattern to match against symbol names.
        type_filter: The type of symbols to include in results.
    """

    name_regex: str
    type_filter: FilterOption = field(default=FilterOption.ALL)


CodeQuery = QueryByKey | QueryByName | QueryByNameRegex


@dataclass(frozen=True)
class CodeQuerySingleResponse:
    """Represents a single response from a code query.

    Contains the function or method information along with its associated
    definitions and references from the index.

    Attributes:
        func_like: The function or method that matched the query.
        info: The complete information including definitions and references.
    """

    func_like: FunctionLike
    info: FunctionLikeInfo
