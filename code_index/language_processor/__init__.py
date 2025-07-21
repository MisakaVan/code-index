from typing import Protocol, List, Optional
from tree_sitter import Language, Query, Parser
from tree_sitter_language_pack import get_language


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


class PythonProcessor(BaseLanguageProcessor):
    """
    针对 Python 语言的具体实现。
    它只负责提供 Python 特有的配置。
    """

    def __init__(self):
        super().__init__(
            name="python",
            extensions=['.py'],
            def_query_str="""
                (function_definition
                    name: (identifier) @function.name) @function.definition
            """,
            ref_query_str="""
                (call
                    function: [(identifier) @function.call
                               (attribute attribute: (identifier) @method.call)])
            """
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
            extensions=['.c', '.h'],
            def_query_str=C_LIKE_DEF_QUERY,
            ref_query_str=C_LIKE_REF_QUERY
        )


class CppProcessor(BaseLanguageProcessor):
    """
    针对 C++ 语言的具体实现。
    """

    def __init__(self):
        super().__init__(
            name="cpp",
            extensions=['.cpp', '.hpp', '.cc', '.h'],
            def_query_str=C_LIKE_DEF_QUERY,
            ref_query_str=C_LIKE_REF_QUERY
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
