# code_index/language_processor/impl_python.py

from tree_sitter import Node, Parser, Language, Query, Tree, QueryCursor
from typing import Optional, Iterable, Dict, List

from ..models import (
    Definition,
    Reference,
    CodeLocation,
    FunctionLike,
    Function,
    FunctionLikeRef,
    Method,
)
from .base import BaseLanguageProcessor, QueryContext
from ..utils.logger import logger


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
                [
                  ; 捕获类中的方法
                  (class_definition
                    body: (block
                      (function_definition) @method.definition
                    )
                  )
                  ; 捕获独立的函数
                  (
                    (function_definition) @function.definition
                    (#not-has-ancestor? @function.definition class_definition)
                  )
                ]
            """,
            ref_query_str="""
                (call) @function.call
            """,
        )

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        # 判断是否是方法定义（在class内部）
        is_method = self._is_method_definition(node)

        # 查找函数体内的所有函数调用
        calls = []

        # 获取函数体节点
        body_node = node.child_by_field_name("body")
        if body_node:
            # 在函数体内查找所有函数调用
            for call_node in self.get_reference_nodes(body_node):
                call_result = self.handle_reference(call_node, ctx)
                if call_result:
                    symbol, reference = call_result
                    calls.append(FunctionLikeRef(symbol=symbol, reference=reference))

        # 根据是否是方法定义返回不同的符号类型
        if is_method:
            # 尝试获取类名
            class_name = self._get_class_name_for_method(node, ctx)
            symbol = Method(name=func_name, class_name=class_name)
        else:
            symbol = Function(name=func_name)

        return (
            symbol,
            Definition(
                # location 信息直接来自整个 function_definition 节点
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=node.start_point[0] + 1,
                    start_col=node.start_point[1],
                    end_lineno=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                ),
                calls=calls,
            ),
        )

    def _is_method_definition(self, node: Node) -> bool:
        """检查函数定义是否在类内部（即是否为方法）"""
        current = node.parent
        while current:
            if current.type == "class_definition":
                return True
            current = current.parent
        return False

    def _get_class_name_for_method(self, node: Node, ctx: QueryContext) -> str | None:
        """获取方法所属的类名"""
        current = node.parent
        while current:
            if current.type == "class_definition":
                name_node = current.child_by_field_name("name")
                if name_node:
                    return ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode(
                        "utf8"
                    )
            current = current.parent
        return None

    def handle_reference(
        self,
        node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        # 从 call 节点中找到名为 'function' 的子节点
        function_node = node.child_by_field_name("function")
        if not function_node:
            logger.warning(
                f"Expected 'function' node to exist in call expression at {ctx.file_path}"
            )
            return None

        # 处理函数调用 (function: identifier)
        if function_node.type == "identifier":
            func_name = ctx.source_bytes[function_node.start_byte : function_node.end_byte].decode(
                "utf8"
            )
            return (
                Function(name=func_name),
                Reference(
                    location=CodeLocation(
                        file_path=ctx.file_path,
                        start_lineno=function_node.start_point[0] + 1,
                        start_col=function_node.start_point[1],
                        end_lineno=function_node.end_point[0] + 1,
                        end_col=function_node.end_point[1],
                    ),
                ),
            )

        # 处理方法调用 (function: attribute)
        elif function_node.type == "attribute":
            # attribute节点的结构：object.method
            # 对于链式调用，可能是嵌套的结构，我们需要找到最后的method名

            # 直接查找attribute节点的最后一个identifier子节点
            method_name_node = None

            # 倒序遍历子节点，找到最后一个identifier
            for child in reversed(function_node.children):
                if child.type == "identifier":
                    method_name_node = child
                    break

            if not method_name_node:
                logger.warning(f"Could not find method name in attribute node at {ctx.file_path}")
                return None

            method_name = ctx.source_bytes[
                method_name_node.start_byte : method_name_node.end_byte
            ].decode("utf8")

            return (
                Method(name=method_name, class_name=None),  # 按要求设置class_name为None
                Reference(
                    location=CodeLocation(
                        file_path=ctx.file_path,
                        start_lineno=method_name_node.start_point[0] + 1,
                        start_col=method_name_node.start_point[1],
                        end_lineno=method_name_node.end_point[0] + 1,
                        end_col=method_name_node.end_point[1],
                    ),
                ),
            )

        else:
            logger.warning(
                f"Unexpected function node type '{function_node.type}' at {ctx.file_path}"
            )
            return None
