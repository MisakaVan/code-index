import pytest
from pathlib import Path
from code_index.language_processor.impl_c_cpp import CProcessor, CppProcessor
from code_index.language_processor.base import QueryContext
from code_index.models import Function, Definition, Reference


class TestCProcessor:
    """测试C语言处理器"""

    @pytest.fixture
    def c_processor(self):
        return CProcessor()

    @pytest.fixture
    def sample_c_code(self):
        return """#include <stdio.h>

void helper_func(int x) {
    printf("Helper: %d\\n", x);
}

int main() {
    helper_func(42);
    helper_func(100);
    return 0;
}
"""

    def test_c_processor_initialization(self, c_processor):
        """测试C处理器的初始化"""
        assert c_processor.name == "c"
        assert ".c" in c_processor.extensions
        assert ".h" in c_processor.extensions
        assert c_processor.parser is not None
        assert c_processor.language is not None

    def test_c_function_definition_parsing(self, c_processor, sample_c_code):
        """测试C函数定义的解析"""
        source_bytes = sample_c_code.encode("utf-8")
        tree = c_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("test.c"), source_bytes=source_bytes)

        # 获取定义节点
        definition_nodes = list(c_processor.get_definition_nodes(tree.root_node))
        assert len(definition_nodes) == 2  # helper_func 和 main

        # 测试处理第一个定义（helper_func）
        helper_def_node = definition_nodes[0]
        result = c_processor.handle_definition(helper_def_node, ctx)

        assert result is not None
        func, definition = result
        assert isinstance(func, Function)
        assert func.name == "helper_func"
        assert isinstance(definition, Definition)
        assert definition.location.start_lineno == 3  # helper_func在第3行定义
        assert definition.location.file_path == Path("test.c")

        # 测试处理第二个定义（main）
        main_def_node = definition_nodes[1]
        result = c_processor.handle_definition(main_def_node, ctx)

        assert result is not None
        func, definition = result
        assert isinstance(func, Function)
        assert func.name == "main"
        assert definition.location.start_lineno == 7  # main在第7行定义

    def test_c_function_reference_parsing(self, c_processor, sample_c_code):
        """测试C函数引用的解析"""
        source_bytes = sample_c_code.encode("utf-8")
        tree = c_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("test.c"), source_bytes=source_bytes)

        # 获取引用节点
        reference_nodes = list(c_processor.get_reference_nodes(tree.root_node))
        assert len(reference_nodes) >= 2  # 至少有两次对 helper_func 的调用

        # 测试处理第一个引用
        first_ref_node = reference_nodes[0]
        result = c_processor.handle_reference(first_ref_node, ctx)

        assert result is not None
        func, reference = result
        assert isinstance(func, Function)
        assert func.name in ["helper_func", "printf"]  # 可能是helper_func或printf调用
        assert isinstance(reference, Reference)

        # 找到helper_func的引用
        helper_refs = []
        for ref_node in reference_nodes:
            result = c_processor.handle_reference(ref_node, ctx)
            if result and result[0].name == "helper_func":
                helper_refs.append(result)

        assert len(helper_refs) == 2  # 应该有两个helper_func的调用

    def test_c_processor_with_header_file(self, c_processor):
        """测试C处理器处理头文件"""
        header_code = """#ifndef MYHEADER_H
#define MYHEADER_H

void public_func(void);
int calculate(int a, int b);

#endif
"""
        source_bytes = header_code.encode("utf-8")
        tree = c_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("myheader.h"), source_bytes=source_bytes)

        # 头文件中的函数声明不会被当作定义处理
        definition_nodes = list(c_processor.get_definition_nodes(tree.root_node))
        assert len(definition_nodes) == 0  # 头文件中只有声明，没有定义

    def test_c_processor_malformed_code(self, c_processor):
        """测试C处理器处理格式错误的代码"""
        malformed_c = b"void func( { // missing parameter and closing brace"
        tree = c_processor.parser.parse(malformed_c)

        ctx = QueryContext(file_path=Path("malformed.c"), source_bytes=malformed_c)

        # 即使代码格式错误，处理器也不应该崩溃
        definition_nodes = list(c_processor.get_definition_nodes(tree.root_node))
        reference_nodes = list(c_processor.get_reference_nodes(tree.root_node))

        # 处理器应该优雅地处理错误，不会崩溃
        assert isinstance(definition_nodes, list)
        assert isinstance(reference_nodes, list)

    def test_c_processor_empty_file(self, c_processor):
        """测试C处理器处理空文件"""
        source_bytes = b""
        tree = c_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("empty.c"), source_bytes=source_bytes)

        # 空文件不应该有任何定义或引用
        definition_nodes = list(c_processor.get_definition_nodes(tree.root_node))
        reference_nodes = list(c_processor.get_reference_nodes(tree.root_node))

        assert len(definition_nodes) == 0
        assert len(reference_nodes) == 0


class TestCppProcessor:
    """测试C++语言处理器"""

    @pytest.fixture
    def cpp_processor(self):
        return CppProcessor()

    @pytest.fixture
    def sample_cpp_code(self):
        return """#include <iostream>
using namespace std;

void helper_func(int x) {
    cout << "Helper: " << x << endl;
}

class MyClass {
public:
    void method_func() {
        helper_func(10);
    }
};

int main() {
    helper_func(42);
    MyClass obj;
    obj.method_func();
    return 0;
}
"""

    def test_cpp_processor_initialization(self, cpp_processor):
        """测试C++处理器的初始化"""
        assert cpp_processor.name == "cpp"
        assert ".cpp" in cpp_processor.extensions
        assert ".hpp" in cpp_processor.extensions
        assert ".cc" in cpp_processor.extensions
        assert ".h" in cpp_processor.extensions
        assert cpp_processor.parser is not None
        assert cpp_processor.language is not None

    def test_cpp_function_definition_parsing(self, cpp_processor, sample_cpp_code):
        """测试C++函数定义的解析"""
        source_bytes = sample_cpp_code.encode("utf-8")
        tree = cpp_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("test.cpp"), source_bytes=source_bytes)

        # 获取定义节点
        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))
        # 应该包括 helper_func, method_func, main
        assert len(definition_nodes) >= 3

        # 找到helper_func定义
        helper_def = None
        for def_node in definition_nodes:
            result = cpp_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "helper_func":
                helper_def = result
                break

        assert helper_def is not None
        func, definition = helper_def
        assert isinstance(func, Function)
        assert func.name == "helper_func"
        assert isinstance(definition, Definition)
        assert definition.location.start_lineno == 4  # helper_func在第4行定义

    def test_cpp_function_reference_parsing(self, cpp_processor, sample_cpp_code):
        """测试C++函数引用的解析"""
        source_bytes = sample_cpp_code.encode("utf-8")
        tree = cpp_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("test.cpp"), source_bytes=source_bytes)

        # 获取引用节点
        reference_nodes = list(cpp_processor.get_reference_nodes(tree.root_node))
        assert len(reference_nodes) >= 2  # 至少有helper_func的调用

        # 找到helper_func的引用
        helper_refs = []
        for ref_node in reference_nodes:
            result = cpp_processor.handle_reference(ref_node, ctx)
            if result and result[0].name == "helper_func":
                helper_refs.append(result)

        assert len(helper_refs) >= 2  # 应该有至少两个helper_func的调用

    def test_cpp_processor_with_templates(self, cpp_processor):
        """测试C++处理器处理模板函数"""
        template_code = """template<typename T>
void template_func(T value) {
    // template implementation
}

void regular_func() {
    template_func<int>(42);
    template_func<double>(3.14);
}
"""
        source_bytes = template_code.encode("utf-8")
        tree = cpp_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("template.cpp"), source_bytes=source_bytes)

        # 获取定义节点
        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))
        assert len(definition_nodes) >= 2  # template_func 和 regular_func

    def test_cpp_processor_malformed_code(self, cpp_processor):
        """测试C++处理器处理格式错误的代码"""
        malformed_cpp = b"void func( { // missing parameter and closing brace"
        tree = cpp_processor.parser.parse(malformed_cpp)

        ctx = QueryContext(file_path=Path("malformed.cpp"), source_bytes=malformed_cpp)

        # 即使代码格式错误，处理器也不应该崩溃
        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))
        for node in definition_nodes:
            result = cpp_processor.handle_definition(node, ctx)
            # 结果可能为None，但不应该抛出异常

    def test_cpp_processor_empty_file(self, cpp_processor):
        """测试C++处理器处理空文件"""
        source_bytes = b""
        tree = cpp_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("empty.cpp"), source_bytes=source_bytes)

        # 空文件不应该有任何定义或引用
        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))
        reference_nodes = list(cpp_processor.get_reference_nodes(tree.root_node))

        assert len(definition_nodes) == 0
        assert len(reference_nodes) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
