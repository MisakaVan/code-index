from tree_sitter import Node, Parser, Language, Query, Tree
from typing import Optional, Iterable, Dict, List

from ..models import FunctionDefinition, FunctionReference, CodeLocation
from .base import BaseLanguageProcessor, QueryContext


# C 和 C++ 通用的查询字符串
C_LIKE_DEF_QUERY = """
    (function_definition
        declarator: (function_declarator
            declarator: (identifier) @function.name
        )
    ) @function.definition
"""
C_LIKE_REF_QUERY = """
    (call_expression
        function: (identifier) @function.call
    )
"""


class CProcessor(BaseLanguageProcessor):
    """
    针对 C 语言的具体实现。
    """

    def __init__(self):
        super().__init__(
            name="c",
            extensions=[".c", ".h"],
            def_query_str=C_LIKE_DEF_QUERY,
            ref_query_str=C_LIKE_REF_QUERY,
        )


class CppProcessor(BaseLanguageProcessor):
    """
    针对 C++ 语言的具体实现。
    """

    def __init__(self):
        super().__init__(
            name="cpp",
            extensions=[".cpp", ".hpp", ".cc", ".h"],
            def_query_str=C_LIKE_DEF_QUERY,
            ref_query_str=C_LIKE_REF_QUERY,
        )
