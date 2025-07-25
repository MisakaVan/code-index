# code_index/language_processor/impl_c_cpp.py

from tree_sitter import Node, Parser, Language, Query, Tree
from typing import Optional, Iterable, Dict, List

from ..models import Definition, Reference, CodeLocation, FunctionLike, Function
from .base import BaseLanguageProcessor, QueryContext


class CProcessor(BaseLanguageProcessor):
    """
    针对 C 语言的具体实现。
    """

    def __init__(self):
        super().__init__(
            name="c",
            extensions=[".c", ".h"],
            def_query_str="""
                (function_definition) @function.definition
            """,
            ref_query_str="""
                (call_expression) @function.call
            """,
        )

    def handle_definition(
        self,
        node: Node,  # 这是一个 function_definition 节点
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        """处理一个 C-style 的函数定义节点。"""
        # C 语法的结构是：function_definition -> declarator -> function_declarator -> declarator -> identifier
        declarator_node = node.child_by_field_name("declarator")
        if not declarator_node or declarator_node.type != "function_declarator":
            return None

        name_node = declarator_node.child_by_field_name("declarator")
        if not name_node:
            return None

        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return (
            Function(name=func_name),  # 返回一个 Function 对象
            Definition(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=node.start_point[0] + 1,
                    start_col=node.start_point[1],
                    end_lineno=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                ),
            ),
        )

    def handle_reference(
        self,
        node: Node,  # 这是一个 call_expression 节点
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """处理一个 C-style 的函数调用节点。"""
        name_node = node.child_by_field_name("function")
        if not name_node or name_node.type != "identifier":
            return None

        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return (
            Function(name=func_name),
            Reference(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=name_node.start_point[0] + 1,
                    start_col=name_node.start_point[1],
                    end_lineno=name_node.end_point[0] + 1,
                    end_col=name_node.end_point[1],
                ),
            ),
        )


class CppProcessor(BaseLanguageProcessor):
    """
    针对 C++ 语言的具体实现。
    """

    def __init__(self):
        super().__init__(
            name="cpp",
            extensions=[".cpp", ".hpp", ".cc", ".h", ".cxx", ".hxx"],
            def_query_str="""
                [
                    (function_definition) @function.definition
                ]
            """,
            ref_query_str="""
                (call_expression) @function.call
            """,
        )

    def _handle_function_definition(
        self,
        node: Node,  # 这是一个 function_definition 节点
        ctx: QueryContext,
    ) -> tuple[Function, Definition] | None:
        """处理 C++ 的函数定义节点。"""
        assert node.type == "function_definition", f"Expected function_definition, got {node.type}"

        declarator_node = node.child_by_field_name("declarator")
        if not declarator_node or declarator_node.type != "function_declarator":
            return None

        name_node = declarator_node.child_by_field_name("declarator")
        if not name_node or name_node.type != "identifier":
            return None

        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return (
            Function(name=func_name),
            Definition(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=node.start_point[0] + 1,
                    start_col=node.start_point[1],
                    end_lineno=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                ),
            ),
        )

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        if node.type == "function_definition":
            return self._handle_function_definition(node, ctx)

        return None

    def _handle_function_call(
        self,
        node: Node,  # 这是一个 call_expression 节点
        ctx: QueryContext,
    ) -> tuple[Function, Reference] | None:
        """处理 C++ 的函数或方法调用节点。"""
        assert node.type == "call_expression", f"Expected call_expression, got {node.type}"

        name_node = node.child_by_field_name("function")
        if not name_node or name_node.type != "identifier":
            return None

        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return (
            Function(name=func_name),
            Reference(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=name_node.start_point[0] + 1,
                    start_col=name_node.start_point[1],
                    end_lineno=name_node.end_point[0] + 1,
                    end_col=name_node.end_point[1],
                ),
            ),
        )

    def handle_reference(
        self,
        node: Node,  # 这是一个 call_expression 节点
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """处理 C++ 的函数或方法调用。"""
        name_node = node.child_by_field_name("function")
        if not name_node:
            return None

        if name_node.type == "identifier":
            func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")
            return (
                Function(name=func_name),  # 返回一个 Function 对象
                Reference(
                    location=CodeLocation(
                        file_path=ctx.file_path,
                        start_lineno=name_node.start_point[0] + 1,
                        start_col=name_node.start_point[1],
                        end_lineno=name_node.end_point[0] + 1,
                        end_col=name_node.end_point[1],
                    ),
                ),
            )

        return None
