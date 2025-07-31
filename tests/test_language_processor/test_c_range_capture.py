#!/usr/bin/env python3
"""
测试C语言处理器的范围捕获行为。
这些测试定义了我们期望的正确行为，而不是当前实现的行为。
"""

from pathlib import Path

import pytest
from tree_sitter import Parser

from code_index.language_processor.base import QueryContext
from code_index.language_processor.impl_c import CProcessor
from code_index.models import Function


class TestCRangeCapture:
    """测试C处理器的范围捕获"""

    def setup_method(self):
        self.processor = CProcessor()
        self.parser = Parser()
        self.parser.language = self.processor.language

    def _parse_and_get_nodes(self, code: str, query_type: str):
        """解析代码并获取相应的节点"""
        source_bytes = code.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("test.c"), source_bytes=source_bytes)

        if query_type == "definition":
            nodes = list(self.processor.get_definition_nodes(tree.root_node))
        else:  # reference
            nodes = list(self.processor.get_reference_nodes(tree.root_node))

        return nodes, ctx, source_bytes

    def test_simple_function_definition(self):
        """测试简单函数定义的捕获"""
        code = """int simple_function() {
    return 42;
}"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "simple_function"

        # 应该从返回类型开始到函数体结束
        expected_content = """int simple_function() {
    return 42;
}"""
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_definition_with_return_type(self):
        """测试带复杂返回类型的函数定义捕获"""
        code = """static int* get_pointer(int param) {
    static int value = 42;
    return &value;
}"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "get_pointer"

        # 应该从static开始到函数体结束
        expected_content = """static int* get_pointer(int param) {
    static int value = 42;
    return &value;
}"""
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_definition_with_void_return(self):
        """测试void返回类型的函数定义捕获"""
        code = """void helper_function(int x) {
    printf("Value: %d\\n", x);
}"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "helper_function"

        # 应该从void开始到函数体结束
        expected_content = """void helper_function(int x) {
    printf("Value: %d\\n", x);
}"""
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_definition_with_modifiers(self):
        """测试带修饰符的函数定义捕获"""
        code = """static inline int calculate(int a, int b) {
    return a * b + 1;
}"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "calculate"

        # 应该从static开始到函数体结束
        expected_content = """static inline int calculate(int a, int b) {
    return a * b + 1;
}"""
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_definition_complex_parameters(self):
        """测试复杂参数的函数定义捕获"""
        code = """int process_array(const int* arr, size_t len, void (*callback)(int)) {
    for (size_t i = 0; i < len; i++) {
        callback(arr[i]);
    }
    return 0;
}"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "process_array"

        # 应该从返回类型开始到函数体结束
        expected_content = """int process_array(const int* arr, size_t len, void (*callback)(int)) {
    for (size_t i = 0; i < len; i++) {
        callback(arr[i]);
    }
    return 0;
}"""
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_definition_multiline(self):
        """测试多行函数定义的捕获"""
        code = """long long
complex_function(
    int first_param,
    const char* second_param,
    double third_param
) {
    // Function body
    return 0LL;
}"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "complex_function"

        # 应该从返回类型开始到函数体结束
        expected_content = """long long
complex_function(
    int first_param,
    const char* second_param,
    double third_param
) {
    // Function body
    return 0LL;
}"""
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_simple(self):
        """测试简单函数调用的捕获"""
        code = """func()"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Function)
        assert symbol.name == "func"

        # 应该捕获完整的函数调用：函数名 + 括号
        expected_content = "func()"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_with_args(self):
        """测试带参数的函数调用捕获"""
        code = """func(arg1, arg2, arg3)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Function)
        assert symbol.name == "func"

        # 应该捕获完整的函数调用：函数名 + 括号 + 参数
        expected_content = "func(arg1, arg2, arg3)"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_complex_args(self):
        """测试复杂参数的函数调用捕获"""
        code = """printf("Result: %d, %s\\n", calculate(x, y), get_name())"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) >= 1  # 可能还有嵌套的函数调用

        # 找到printf调用
        printf_call = None
        for node in nodes:
            result = self.processor.handle_reference(node, ctx)
            if result and result[0].name == "printf":
                printf_call = result
                break

        assert printf_call is not None
        symbol, reference = printf_call

        # 应该捕获完整的printf调用包括所有参数
        expected_content = 'printf("Result: %d, %s\\n", calculate(x, y), get_name())'
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_multiline(self):
        """测试多行函数调用的捕获"""
        code = """func(
    param1,
    param2 + param3,
    "string literal",
    &variable
)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Function)
        assert symbol.name == "func"

        # 应该捕获完整的多行函数调用
        expected_content = """func(
    param1,
    param2 + param3,
    "string literal",
    &variable
)"""
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_with_casts(self):
        """测试带类型转换的函数调用捕获"""
        code = """func((int)value, (char*)buffer, (size_t)length)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Function)
        assert symbol.name == "func"

        # 应该捕获包括类型转换在内的完整函数调用
        expected_content = "func((int)value, (char*)buffer, (size_t)length)"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_nested(self):
        """测试嵌套函数调用的捕获"""
        code = """outer(inner1(x), inner2(y, z))"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) >= 1

        # 找到outer调用
        outer_call = None
        for node in nodes:
            result = self.processor.handle_reference(node, ctx)
            if result and result[0].name == "outer":
                outer_call = result
                break

        assert outer_call is not None
        symbol, reference = outer_call

        # 应该捕获完整的外层函数调用
        expected_content = "outer(inner1(x), inner2(y, z))"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_with_pointer_dereference(self):
        """测试带指针解引用的函数调用捕获"""
        code = """(*func_ptr)(arg1, arg2)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        # 注意：这种情况下函数名是通过指针调用的，可能不会被识别为普通函数调用
        # 但如果被识别，应该捕获完整的调用表达式
        if nodes:
            result = self.processor.handle_reference(nodes[0], ctx)
            if result:
                symbol, reference = result
                expected_content = "(*func_ptr)(arg1, arg2)"
                actual_content = source_bytes[
                    reference.location.start_byte : reference.location.end_byte
                ].decode("utf-8")
                assert actual_content == expected_content

    def test_function_call_in_expression(self):
        """测试表达式中的函数调用捕获"""
        code = """int result = func(a, b) + other_func(c);"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 2  # 应该找到两个函数调用

        # 验证每个函数调用都被正确捕获
        func_calls = []
        for node in nodes:
            result = self.processor.handle_reference(node, ctx)
            if result:
                func_calls.append(result)

        assert len(func_calls) == 2

        # 检查func调用
        func_call = None
        other_func_call = None
        for symbol, reference in func_calls:
            if symbol.name == "func":
                func_call = (symbol, reference)
            elif symbol.name == "other_func":
                other_func_call = (symbol, reference)

        assert func_call is not None
        symbol, reference = func_call
        expected_content = "func(a, b)"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

        if other_func_call:  # 如果找到other_func调用
            symbol, reference = other_func_call
            expected_content = "other_func(c)"
            actual_content = source_bytes[
                reference.location.start_byte : reference.location.end_byte
            ].decode("utf-8")
            assert actual_content == expected_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
