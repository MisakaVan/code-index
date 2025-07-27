import pytest
from pathlib import Path
from code_index.language_processor.impl_c_cpp import CProcessor, CppProcessor
from code_index.language_processor.impl_python import PythonProcessor
from code_index.language_processor import language_processor_factory
from code_index.language_processor.base import QueryContext


class TestLanguageProcessorFactory:
    """测试语言处理器工厂函数"""

    def test_factory_creates_correct_processors(self):
        """测试工厂函数创建正确的处理器"""
        # 测试创建Python处理器
        python_proc = language_processor_factory("python")
        assert python_proc is not None
        assert isinstance(python_proc, PythonProcessor)
        assert python_proc.name == "python"

        # 测试创建C处理器
        c_proc = language_processor_factory("c")
        assert c_proc is not None
        assert isinstance(c_proc, CProcessor)
        assert c_proc.name == "c"

        # 测试创建C++处理器
        cpp_proc = language_processor_factory("cpp")
        assert cpp_proc is not None
        assert isinstance(cpp_proc, CppProcessor)
        assert cpp_proc.name == "cpp"

    def test_factory_returns_none_for_unknown_language(self):
        """测试工厂函数对未知语言返回None"""
        unknown_proc = language_processor_factory("unknown_language")
        assert unknown_proc is None

    def test_factory_returns_none_for_empty_string(self):
        """测试工厂函数对空字符串返回None"""
        empty_proc = language_processor_factory("")
        assert empty_proc is None


class TestLanguageProcessorCommonBehavior:
    """测试所有语言处理器的通用行为"""

    @pytest.fixture
    def all_processors(self):
        """返回所有可用的语言处理器"""
        return [CProcessor(), CppProcessor(), PythonProcessor()]

    def test_all_processors_have_required_attributes(self, all_processors):
        """测试所有处理器都具有必需的属性"""
        for processor in all_processors:
            # 检查基本属性
            assert hasattr(processor, "name")
            assert hasattr(processor, "extensions")
            assert hasattr(processor, "language")
            assert hasattr(processor, "parser")

            # 检查属性类型
            assert isinstance(processor.name, str)
            assert isinstance(processor.extensions, list)
            assert len(processor.extensions) > 0
            assert processor.language is not None
            assert processor.parser is not None

    def test_all_processors_have_required_methods(self, all_processors):
        """测试所有处理器都具有必需的方法"""
        for processor in all_processors:
            # 检查查询方法
            assert hasattr(processor, "get_definition_query")
            assert hasattr(processor, "get_reference_query")
            assert hasattr(processor, "get_definition_nodes")
            assert hasattr(processor, "get_reference_nodes")

            # 检查处理方法
            assert hasattr(processor, "handle_definition")
            assert hasattr(processor, "handle_reference")

            # 验证方法可以被调用
            assert callable(processor.get_definition_query)
            assert callable(processor.get_reference_query)
            assert callable(processor.get_definition_nodes)
            assert callable(processor.get_reference_nodes)
            assert callable(processor.handle_definition)
            assert callable(processor.handle_reference)

    def test_all_processors_handle_empty_files(self, all_processors):
        """测试所有处理器都能正确处理空文件"""
        for processor in all_processors:
            source_bytes = b""
            tree = processor.parser.parse(source_bytes)

            # 获取适当的文件扩展名
            file_ext = processor.extensions[0]
            ctx = QueryContext(file_path=Path(f"empty{file_ext}"), source_bytes=source_bytes)

            # 空文件不应该有任何定义或引用
            definition_nodes = list(processor.get_definition_nodes(tree.root_node))
            reference_nodes = list(processor.get_reference_nodes(tree.root_node))

            assert len(definition_nodes) == 0
            assert len(reference_nodes) == 0

    def test_all_processors_handle_malformed_code_gracefully(self, all_processors):
        """测试所有处理器都能优雅地处理格式错误的代码"""
        malformed_codes = {
            "c": b"void func( { // missing parameter and closing brace",
            "cpp": b"void func( { // missing parameter and closing brace",
            "python": b"def func( # missing colon and closing parenthesis",
        }

        for processor in all_processors:
            malformed_code = malformed_codes.get(processor.name, b"invalid code")
            tree = processor.parser.parse(malformed_code)

            file_ext = processor.extensions[0]
            ctx = QueryContext(file_path=Path(f"malformed{file_ext}"), source_bytes=malformed_code)

            # 即使代码格式错误，处理器也不应该崩溃
            try:
                definition_nodes = list(processor.get_definition_nodes(tree.root_node))
                for node in definition_nodes:
                    result = processor.handle_definition(node, ctx)
                    # 结果可能为None，但不应该抛出异常

                reference_nodes = list(processor.get_reference_nodes(tree.root_node))
                for node in reference_nodes:
                    result = processor.handle_reference(node, ctx)
                    # 结果可能为None，但不应该抛出异常

            except Exception as e:
                pytest.fail(f"{processor.name} processor crashed on malformed code: {e}")

    def test_processor_extensions_are_valid(self, all_processors):
        """测试处理器的文件扩展名格式正确"""
        for processor in all_processors:
            for ext in processor.extensions:
                assert ext.startswith(
                    "."
                ), f"Extension {ext} for {processor.name} should start with '.'"
                assert (
                    len(ext) > 1
                ), f"Extension {ext} for {processor.name} should have content after '.'"
                assert (
                    ext.islower() or ext == ".h"
                ), f"Extension {ext} for {processor.name} should be lowercase (except .h)"

    def test_processor_names_are_consistent(self, all_processors):
        """测试处理器名称与其类型一致"""
        expected_names = {CProcessor: "c", CppProcessor: "cpp", PythonProcessor: "python"}

        for processor in all_processors:
            expected_name = expected_names.get(type(processor))
            assert (
                processor.name == expected_name
            ), f"Expected {expected_name}, got {processor.name}"


class TestQueryContextBehavior:
    """测试QueryContext的行为"""

    def test_query_context_creation(self):
        """测试QueryContext的创建"""
        file_path = Path("test.py")
        source_bytes = b"def test(): pass"

        ctx = QueryContext(file_path=file_path, source_bytes=source_bytes)

        assert ctx.file_path == file_path
        assert ctx.source_bytes == source_bytes

    def test_query_context_with_different_encodings(self):
        """测试QueryContext处理不同编码的源代码"""
        file_path = Path("test.py")

        # UTF-8编码
        utf8_code = "def 测试函数(): pass".encode("utf-8")
        ctx_utf8 = QueryContext(file_path=file_path, source_bytes=utf8_code)
        assert ctx_utf8.source_bytes == utf8_code

        # ASCII编码
        ascii_code = b"def test_func(): pass"
        ctx_ascii = QueryContext(file_path=file_path, source_bytes=ascii_code)
        assert ctx_ascii.source_bytes == ascii_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
