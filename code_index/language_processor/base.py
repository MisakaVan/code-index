import pathlib
from dataclasses import dataclass
from itertools import chain
from typing import Protocol, List, Iterable

from tree_sitter import Language, Query, Parser, Node, QueryCursor

from ..models import Definition, Reference, FunctionLike
from ..utils.logger import logger


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

    def get_definition_nodes(self, node: Node) -> Iterable[Node]:
        """从语法树节点中获取所有定义（函数/方法）的节点。"""
        ...

    def get_reference_nodes(self, node: Node) -> Iterable[Node]:
        """从语法树节点中获取所有引用（函数/方法调用）的节点。"""
        ...

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        """
        处理函数/方法定义节点，返回一个 Definition 对象。
        如果节点不符合预期格式，返回 None。
        """
        ...

    def handle_reference(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """
        处理函数/方法引用节点，返回一个 Reference 对象。
        如果节点不符合预期格式，返回 None。
        """
        ...


class BaseLanguageProcessor(LanguageProcessor):
    """
    一个具体的基类，封装了所有语言处理器共享的通用逻辑。
    它实现了 LanguageProcessor 协议。
    """

    def __init__(
        self,
        name: str,
        language: Language,
        extensions: List[str],
        def_query_str: str,
        ref_query_str: str,
    ):
        self._name = name  # language.name is problematic, so set manually
        self._extensions = extensions
        self._language = language
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

    def get_definition_nodes(self, node: Node) -> Iterable[Node]:
        captures = QueryCursor(self.get_definition_query()).captures(node)
        func_defs = captures.get("function.definition", [])
        method_defs = captures.get("method.definition", [])
        logger.debug(f"Got {len(func_defs)} function defs and {len(method_defs)} method defs.")
        return chain(func_defs, method_defs)

    def get_reference_nodes(self, node: Node) -> Iterable[Node]:
        captures = QueryCursor(self.get_reference_query()).captures(node)
        func_calls = captures.get("function.call", [])
        method_calls = captures.get("method.call", [])
        logger.debug(f"Got {len(func_calls)} function calls and {len(method_calls)} method calls.")
        return chain(func_calls, method_calls)

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement handle_definition method."
        )

    def handle_reference(
        self,
        node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement handle_reference method."
        )
