import pathlib
from typing import Protocol, List, Optional, Iterable
from itertools import chain
from dataclasses import dataclass
from tree_sitter import Language, Query, Parser, Node, Tree, QueryCursor
from tree_sitter_language_pack import get_language

from ..models import FunctionDefinition, FunctionReference, CodeLocation


@dataclass
class QueryContext:
    """
    用于存储查询时需要查询的信息，包括文件地址、文件bytes等。
    """

    file_path: pathlib.Path
    source_bytes: bytes


class LanguageProcessor(Protocol):
    """
    定义了处理一种特定编程语言所需的所有配置和资源的接口。
    这是一个协议类，用于静态类型检查，确保所有实现都符合规范。
    """

    @property
    def name(self) -> str:
        """语言的名称，例如 'python'。"""
        ...

    @property
    def extensions(self) -> List[str]:
        """该语言处理器支持的文件扩展名列表，例如 ['.py']。"""
        ...

    @property
    def language(self) -> Language:
        """tree-sitter 的 Language 对象。"""
        ...

    @property
    def parser(self) -> Parser:
        """tree-sitter 的 Parser 对象。"""
        ...

    def get_definition_query(self) -> Query:
        """获取用于查找函数/方法定义的查询。"""
        ...

    def get_reference_query(self) -> Query:
        """获取用于查找函数/方法引用的查询。"""
        ...

    def get_definition_nodes(self, tree: Tree) -> Iterable[Node]:
        """从语法树中获取所有定义（函数/方法）的节点。"""
        ...

    def get_reference_nodes(self, tree: Tree) -> Iterable[Node]:
        """从语法树中获取所有引用（函数/方法调用）的节点。"""
        ...

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> Optional[FunctionDefinition]:
        """
        处理函数/方法定义节点，返回一个 FunctionDefinition 对象。
        如果节点不符合预期格式，返回 None。
        """
        ...

    def handle_reference(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> Optional[FunctionReference]:
        """
        处理函数/方法引用节点，返回一个 FunctionReference 对象。
        如果节点不符合预期格式，返回 None。
        """
        ...


class BaseLanguageProcessor(LanguageProcessor):
    """
    一个具体的基类，封装了所有语言处理器共享的通用逻辑。
    它实现了 LanguageProcessor 协议。
    """

    def __init__(self, name: str, extensions: List[str], def_query_str: str, ref_query_str: str):
        self._name = name
        self._extensions = extensions
        self._language = get_language(name)
        self._parser = Parser(self._language)
        self._def_query = Query(self._language, def_query_str)
        self._ref_query = Query(self._language, ref_query_str)

    @property
    def name(self) -> str:
        return self._name

    @property
    def extensions(self) -> List[str]:
        return self._extensions

    @property
    def language(self) -> Language:
        return self._language

    @property
    def parser(self) -> Parser:
        return self._parser

    def get_definition_query(self) -> Query:
        return self._def_query

    def get_reference_query(self) -> Query:
        return self._ref_query

    def get_definition_nodes(self, tree: Tree) -> Iterable[Node]:
        captures = QueryCursor(self.get_definition_query()).captures(tree.root_node)
        func_defs = captures.get("function.definition", [])
        return chain(func_defs)

    def get_reference_nodes(self, tree: Tree) -> Iterable[Node]:
        captures = QueryCursor(self.get_reference_query()).captures(tree.root_node)
        func_calls = captures.get("function.call", [])
        return chain(func_calls)

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> Optional[FunctionDefinition]:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement handle_definition method."
        )

    def handle_reference(
        self,
        node,
        ctx: QueryContext,
    ) -> Optional[FunctionReference]:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement handle_reference method."
        )


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
    ) -> Optional[FunctionDefinition]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return FunctionDefinition(
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
    ) -> Optional[FunctionReference]:
        # 从 call 节点中找到名为 'function' 的子节点
        name_node = node.child_by_field_name("function")
        if not name_node:
            print(f"Warning: Expected 'function' node to exist")
            return None
        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return FunctionReference(
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


def language_processor_factory(name: str) -> Optional[LanguageProcessor]:
    """
    一个简单的工厂函数，根据语言名称返回对应的处理器实例。
    """
    processors = {
        "python": PythonProcessor,
        "c": CProcessor,
        "cpp": CppProcessor,
    }
    processor_class = processors.get(name)
    if processor_class:
        return processor_class()

    print(f"Warning: No language processor found for '{name}'")
    return None
