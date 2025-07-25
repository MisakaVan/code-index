# code_index/language_processor/impl_python.py

from tree_sitter import Node, Parser, Language, Query, Tree
from typing import Optional, Iterable, Dict, List

from ..models import Definition, Reference, CodeLocation
from .base import BaseLanguageProcessor, QueryContext


class PythonProcessor(BaseLanguageProcessor):
    """
    针对 Python 语言的具体实现。
    它只负责提供 Python 特有的配置。
    """

    def __init__(self):
        super().__init__(
            name="python",
            extensions=[".py"],
            def_query_str="""
                (
                    (function_definition) @function.definition
                    (#not-has-ancestor? @function.definition class_definition)
                )
            """,
            ref_query_str="""
                (call
                    function: (identifier)) @function.call
            """,
        )

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> Optional[Definition]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return Definition(
            name=func_name,
            # location 信息直接来自整个 function_definition 节点
            location=CodeLocation(
                file_path=ctx.file_path,
                start_lineno=node.start_point[0] + 1,
                start_col=node.start_point[1],
                end_lineno=node.end_point[0] + 1,
                end_col=node.end_point[1],
            ),
        )

    def handle_reference(
        self,
        node,
        ctx: QueryContext,
    ) -> Optional[Reference]:
        # 从 call 节点中找到名为 'function' 的子节点
        name_node = node.child_by_field_name("function")
        if not name_node:
            print(f"Warning: Expected 'function' node to exist")
            return None
        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return Reference(
            name=func_name,
            # location 信息来自调用的名称节点本身
            location=CodeLocation(
                file_path=ctx.file_path,
                start_lineno=name_node.start_point[0] + 1,
                start_col=name_node.start_point[1],
                end_lineno=name_node.end_point[0] + 1,
                end_col=name_node.end_point[1],
            ),
        )
