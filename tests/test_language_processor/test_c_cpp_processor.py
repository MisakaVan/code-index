from pathlib import Path

import pytest

from code_index.language_processor.base import QueryContext
from code_index.language_processor.impl_c import CProcessor
from code_index.language_processor.impl_cpp import CppProcessor
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

    def test_c_function_calls_tracking(self, c_processor):
        """测试C函数定义中的函数调用追踪功能"""
        code_with_calls = """#include <stdio.h>

void helper_func(int x) {
    printf("Helper: %d\\n", x);
}

void utility_func() {
    printf("Utility called\\n");
}

int main() {
    helper_func(5);
    helper_func(10);
    utility_func();
    printf("Main function\\n");
    return 0;
}

void another_func() {
    main();
    helper_func(100);
}
"""
        source_bytes = code_with_calls.encode("utf-8")
        tree = c_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("test_calls.c"), source_bytes=source_bytes)

        # 获取main函数的定义节点
        definition_nodes = list(c_processor.get_definition_nodes(tree.root_node))
        main_func_result = None
        another_func_result = None

        for def_node in definition_nodes:
            result = c_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "main":
                main_func_result = result
            elif result and result[0].name == "another_func":
                another_func_result = result

        # 验证main函数被找到并包含调用信息
        assert main_func_result is not None
        symbol, definition = main_func_result
        assert symbol.name == "main"
        assert (
            len(definition.calls) == 4
        )  # helper_func(5), helper_func(10), utility_func(), printf()

        # 验证调用的函数名
        called_functions = [call.symbol.name for call in definition.calls]
        assert called_functions.count("helper_func") == 2
        assert called_functions.count("utility_func") == 1
        assert called_functions.count("printf") == 1

        # 验证another_func的调用
        assert another_func_result is not None
        another_symbol, another_definition = another_func_result
        assert another_symbol.name == "another_func"
        assert len(another_definition.calls) == 2  # main(), helper_func(100)

        another_called_functions = [call.symbol.name for call in another_definition.calls]
        assert "main" in another_called_functions
        assert "helper_func" in another_called_functions

    def test_c_function_calls_location_accuracy(self, c_processor):
        """测试C函数调用位置信息的准确性"""
        location_test_code = """void target_func() {
    return;
}

void caller_func() {
    target_func();  // Line 6
    // comment
    target_func();  // Line 8
}
"""
        source_bytes = location_test_code.encode("utf-8")
        tree = c_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("location_test.c"), source_bytes=source_bytes)

        definition_nodes = list(c_processor.get_definition_nodes(tree.root_node))
        caller_func_result = None

        for def_node in definition_nodes:
            result = c_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "caller_func":
                caller_func_result = result
                break

        assert caller_func_result is not None
        symbol, definition = caller_func_result

        # 找到target_func的调用
        target_calls = [call for call in definition.calls if call.symbol.name == "target_func"]
        assert len(target_calls) == 2

        # 验证调用位置
        call_lines = {call.reference.location.start_lineno for call in target_calls}
        assert 6 in call_lines
        assert 8 in call_lines

    def test_c_function_calls_empty_function(self, c_processor):
        """测试C空函数的调用追踪"""
        empty_func_code = """void empty_func() {}

void func_with_comment() {
    /* This function only has comments */
}

void func_calling_empty() {
    empty_func();
    func_with_comment();
}
"""
        source_bytes = empty_func_code.encode("utf-8")
        tree = c_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("empty_test.c"), source_bytes=source_bytes)

        definition_nodes = list(c_processor.get_definition_nodes(tree.root_node))

        # 查找各个函数的定义
        results = {}
        for def_node in definition_nodes:
            result = c_processor.handle_definition(def_node, ctx)
            if result:
                results[result[0].name] = result

        # 验证空函数没有调用
        assert "empty_func" in results
        assert len(results["empty_func"][1].calls) == 0

        assert "func_with_comment" in results
        assert len(results["func_with_comment"][1].calls) == 0

        # 验证调用空函数的函数
        assert "func_calling_empty" in results
        calling_func_calls = [call.symbol.name for call in results["func_calling_empty"][1].calls]
        assert "empty_func" in calling_func_calls
        assert "func_with_comment" in calling_func_calls


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

    def test_cpp_function_calls_tracking(self, cpp_processor):
        """测试C++函数定义中的函数调用追踪功能"""
        code_with_calls = """#include <iostream>
using namespace std;

void helper_func(int x) {
    cout << "Helper: " << x << endl;
}

void utility_func() {
    cout << "Utility called" << endl;
}

int main() {
    helper_func(5);
    helper_func(10);
    utility_func();
    cout << "Main function" << endl;
    return 0;
}

void another_func() {
    main();
    helper_func(100);
}
"""
        source_bytes = code_with_calls.encode("utf-8")
        tree = cpp_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("test_calls.cpp"), source_bytes=source_bytes)

        # 获取main函数的定义节点
        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))
        main_func_result = None
        another_func_result = None

        for def_node in definition_nodes:
            result = cpp_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "main":
                main_func_result = result
            elif result and result[0].name == "another_func":
                another_func_result = result

        # 验证main函数被找到并包含调用信息
        assert main_func_result is not None
        symbol, definition = main_func_result
        assert symbol.name == "main"
        # C++可能有更多的函数调用(包括operator<<等)，所以使用>=
        assert len(definition.calls) >= 3  # 至少helper_func(5), helper_func(10), utility_func()

        # 验证调用的函数名
        called_functions = [call.symbol.name for call in definition.calls]
        assert called_functions.count("helper_func") == 2
        assert called_functions.count("utility_func") == 1

        # 验证another_func的调用
        assert another_func_result is not None
        another_symbol, another_definition = another_func_result
        assert another_symbol.name == "another_func"
        assert len(another_definition.calls) >= 2  # 至少main(), helper_func(100)

        another_called_functions = [call.symbol.name for call in another_definition.calls]
        assert "main" in another_called_functions
        assert "helper_func" in another_called_functions

    def test_cpp_function_calls_with_method_calls(self, cpp_processor):
        """测试C++函数调用追踪中的方法调用"""
        method_calls_code = """class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }
    
    int multiply(int a, int b) {
        return a * b;
    }
};

void helper_func() {
    return;
}

int compute() {
    Calculator calc;
    helper_func();
    return calc.add(5, 3);
}
"""
        source_bytes = method_calls_code.encode("utf-8")
        tree = cpp_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("method_calls.cpp"), source_bytes=source_bytes)

        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))

        # 查找compute函数的定义
        compute_result = None
        for def_node in definition_nodes:
            result = cpp_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "compute":
                compute_result = result
                break

        assert compute_result is not None
        symbol, definition = compute_result

        # 验证compute函数调用了helper_func
        called_functions = [call.symbol.name for call in definition.calls]
        assert "helper_func" in called_functions

    def test_cpp_function_calls_location_accuracy(self, cpp_processor):
        """测试C++函数调用位置信息的准确性"""
        location_test_code = """void target_func() {
    return;
}

void caller_func() {
    target_func();  // Line 6
    /* comment */
    target_func();  // Line 8
}
"""
        source_bytes = location_test_code.encode("utf-8")
        tree = cpp_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("location_test.cpp"), source_bytes=source_bytes)

        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))
        caller_func_result = None

        for def_node in definition_nodes:
            result = cpp_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "caller_func":
                caller_func_result = result
                break

        assert caller_func_result is not None
        symbol, definition = caller_func_result

        # 找到target_func的调用
        target_calls = [call for call in definition.calls if call.symbol.name == "target_func"]
        assert len(target_calls) == 2

        # 验证调用位置
        call_lines = {call.reference.location.start_lineno for call in target_calls}
        assert 6 in call_lines
        assert 8 in call_lines

    def test_cpp_function_calls_empty_function(self, cpp_processor):
        """测试C++空函数的调用追踪"""
        empty_func_code = """void empty_func() {}

void func_with_comment() {
    // This function only has comments
}

void func_calling_empty() {
    empty_func();
    func_with_comment();
}
"""
        source_bytes = empty_func_code.encode("utf-8")
        tree = cpp_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("empty_test.cpp"), source_bytes=source_bytes)

        definition_nodes = list(cpp_processor.get_definition_nodes(tree.root_node))

        # 查找各个函数的定义
        results = {}
        for def_node in definition_nodes:
            result = cpp_processor.handle_definition(def_node, ctx)
            if result:
                results[result[0].name] = result

        # 验证空函数没有调用
        assert "empty_func" in results
        assert len(results["empty_func"][1].calls) == 0

        assert "func_with_comment" in results
        assert len(results["func_with_comment"][1].calls) == 0

        # 验证调用空函数的函数
        assert "func_calling_empty" in results
        calling_func_calls = [call.symbol.name for call in results["func_calling_empty"][1].calls]
        assert "empty_func" in calling_func_calls
        assert "func_with_comment" in calling_func_calls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
