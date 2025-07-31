# code_index/language_processor/impl_c.py

from tree_sitter import Node
from tree_sitter_language_pack import get_language

from .base import BaseLanguageProcessor, QueryContext
from ..models import Definition, Reference, CodeLocation, FunctionLike, Function, FunctionLikeRef


class CProcessor(BaseLanguageProcessor):
    """
    针对 C 语言的具体实现。
    """

    def __init__(self):
        super().__init__(
            name="c",
            language=get_language("c"),
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
        # 从AST分析可知，function_definition的结构可能是：
        # 1. 简单情况: primitive_type -> function_declarator -> compound_statement
        # 2. 带修饰符: storage_class_specifier -> primitive_type -> function_declarator -> compound_statement
        # 3. 指针返回: storage_class_specifier -> primitive_type -> pointer_declarator -> compound_statement

        # 查找function_declarator或pointer_declarator中的函数名
        func_name = self._extract_function_name(node, ctx)
        if not func_name:
            return None

        # 查找函数体内的所有函数调用
        calls = []

        # 获取函数体节点 (compound_statement)
        body_node = node.child_by_field_name("body")
        if body_node:
            # 在函数体内查找所有函数调用
            for call_node in self.get_reference_nodes(body_node):
                call_result = self.handle_reference(call_node, ctx)
                if call_result:
                    symbol, reference = call_result
                    calls.append(FunctionLikeRef(symbol=symbol, reference=reference))

        return (
            Function(name=func_name),  # 返回一个 Function 对象
            Definition(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=node.start_point[0] + 1,
                    start_col=node.start_point[1],
                    end_lineno=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                ),
                calls=calls,
            ),
        )

    def _extract_function_name(self, function_def_node: Node, ctx: QueryContext) -> str | None:
        """从function_definition节点中提取函数名"""
        # 查找declarator字段，可能是function_declarator或pointer_declarator
        declarator_node = function_def_node.child_by_field_name("declarator")
        if not declarator_node:
            return None

        # 如果是pointer_declarator，需要进一步查找function_declarator
        if declarator_node.type == "pointer_declarator":
            # 在pointer_declarator的子节点中查找function_declarator
            for child in declarator_node.children:
                if child.type == "function_declarator":
                    declarator_node = child
                    break
            else:
                return None

        # 现在declarator_node应该是function_declarator
        if declarator_node.type != "function_declarator":
            return None

        # 从function_declarator中获取函数名
        name_node = declarator_node.child_by_field_name("declarator")
        if not name_node or name_node.type != "identifier":
            return None

        return ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

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

        # 使用整个call_expression节点的范围，包括函数名、括号和参数
        return (
            Function(name=func_name),
            Reference(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=node.start_point[0] + 1,
                    start_col=node.start_point[1],
                    end_lineno=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                ),
            ),
        )
