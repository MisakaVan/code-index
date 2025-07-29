# code_index/index/code_query.py
# query the index in more ways

from dataclasses import dataclass, field
from enum import Enum
import re

from ..models import FunctionLike, FunctionLikeInfo


@dataclass(frozen=True)
class QueryByKey:
    """
    Represents a query by key in the index.
    This is an accurate query that returns the exact match in the index.

    e.g.:
    - query the `my_function` function:
        `QueryByKey(func_like=Function(name="my_function"))`
    - query the `my_method` method with class name `MyClass`:
        `QueryByKey(func_like=Method(name="my_method", class_name="MyClass"))`
    - query the `my_method` method without class name:
        `QueryByKey(func_like=Method(name="my_method", class_name=None))`
        Note: This will NOT match `my_method` methods with a class name.
        Rather, it matches those symbols that are called in the format `<some_expression>.my_method()`
    """

    func_like: FunctionLike


class FilterOption(Enum):
    """
    Filter for the symbol type.
    """

    FUNCTION = "function"
    METHOD = "method"
    ALL = "all"


@dataclass(frozen=True)
class QueryByName:
    """
    Represents a query by name in the index.
    Results can be associated with all those keys with the same name.
    The type_filter option allows filtering results by symbol type.

    e.g.:
    - query the `my_function` function:
        QueryByName(name="my_function", type_filter=FilterOption.FUNCTION)
    - query the `my_method` method:
        QueryByName(name="my_method", type_filter=FilterOption.METHOD)
        Note: This will match all symbols defined as methods with the name `my_method`,
        and those that are called in the format `<some_expression>.my_method()`
    - query all FunctionLike symbols with the name `my_symbol`:
        QueryByName(name="my_symbol", type_filter=FilterOption.ALL)
    """

    name: str
    type_filter: FilterOption = field(default=FilterOption.ALL)


@dataclass(frozen=True)
class QueryByNameRegex:
    """
    Represents a query by name using regex pattern in the index.
    Results can be associated with all those keys whose names match the regex pattern.
    The type_filter option allows filtering results by symbol type.

    e.g.:
    - query functions starting with "test_":
        QueryByNameRegex(name_regex=r"^test_.*", type_filter=FilterOption.FUNCTION)
    - query methods ending with "_handler":
        QueryByNameRegex(name_regex=r".*_handler$", type_filter=FilterOption.METHOD)
    - query all symbols containing "debug":
        QueryByNameRegex(name_regex=r".*debug.*", type_filter=FilterOption.ALL)
    """

    name_regex: str
    type_filter: FilterOption = field(default=FilterOption.ALL)


CodeQuery = QueryByKey | QueryByName | QueryByNameRegex


@dataclass(frozen=True)
class CodeQuerySingleResponse:
    """
    Represents a response to a code query.
    Contains the function-like information and its associated definitions.
    """

    func_like: FunctionLike
    info: FunctionLikeInfo
