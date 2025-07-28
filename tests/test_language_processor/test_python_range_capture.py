#!/usr/bin/env python3
"""
测试Python处理器的范围捕获行为。
这些测试定义了我们期望的正确行为，而不是当前实现的行为。
"""

import pytest
from pathlib import Path
from code_index.language_processor.impl_python import PythonProcessor
from code_index.language_processor.base import QueryContext
from code_index.models import Function, Method, Definition, Reference
from tree_sitter import Parser


class TestPythonRangeCapture:
    """测试Python处理器的范围捕获"""

    def setup_method(self):
        self.processor = PythonProcessor()
        self.parser = self.processor.parser

    def _parse_and_get_nodes(self, code: str, query_type: str):
        """解析代码并获取相应的节点"""
        source_bytes = code.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("test.py"), source_bytes=source_bytes)

        if query_type == "definition":
            nodes = list(self.processor.get_definition_nodes(tree.root_node))
        else:  # reference
            nodes = list(self.processor.get_reference_nodes(tree.root_node))

        return nodes, ctx, source_bytes

    def test_function_definition_without_decorator(self):
        """测试没有装饰器的函数定义捕获"""
        code = '''def simple_function():
    """A simple function"""
    return 42'''

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "simple_function"

        # 应该从"def"开始到函数体结束
        expected_content = '''def simple_function():
    """A simple function"""
    return 42'''
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_definition_with_single_decorator(self):
        """测试带单个装饰器的函数定义捕获"""
        code = '''@property
def decorated_function():
    return "decorated"'''

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "decorated_function"

        # 应该从装饰器开始到函数体结束
        expected_content = '''@property
def decorated_function():
    return "decorated"'''
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_definition_with_multiple_decorators(self):
        """测试带多个装饰器的函数定义捕获"""
        code = '''@decorator1
@decorator2(arg="value")
@decorator3
def multi_decorated_function(param):
    """Multiple decorators"""
    return param * 2'''

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        assert len(nodes) == 1

        result = self.processor.handle_definition(nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Function)
        assert symbol.name == "multi_decorated_function"

        # 应该从第一个装饰器开始到函数体结束
        expected_content = '''@decorator1
@decorator2(arg="value")
@decorator3
def multi_decorated_function(param):
    """Multiple decorators"""
    return param * 2'''
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_definition_without_decorator(self):
        """测试没有装饰器的方法定义捕获"""
        code = '''class MyClass:
    def method_name(self):
        return "method"'''

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        # 应该有一个方法定义
        method_nodes = [n for n in nodes if self.processor._is_method_definition(n)]
        assert len(method_nodes) == 1

        result = self.processor.handle_definition(method_nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Method)
        assert symbol.name == "method_name"
        assert symbol.class_name == "MyClass"

        # 应该从"def"开始到方法体结束（不包括class定义）
        expected_content = '''def method_name(self):
        return "method"'''
        actual_content = source_bytes[
            definition.location.start_byte : definition.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_definition_with_decorators(self):
        """测试带装饰器的方法定义捕获"""
        code = """class MyClass:
    @property
    @validate_input
    def decorated_method(self):
        return self._value"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "definition")
        method_nodes = [n for n in nodes if self.processor._is_method_definition(n)]
        assert len(method_nodes) == 1

        result = self.processor.handle_definition(method_nodes[0], ctx)
        assert result is not None

        symbol, definition = result
        assert isinstance(symbol, Method)
        assert symbol.name == "decorated_method"
        assert symbol.class_name == "MyClass"

        # 应该从第一个装饰器开始到方法体结束
        expected_content = """@property
    @validate_input
    def decorated_method(self):
        return self._value"""
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
        code = """func(arg1, arg2, arg3=expression)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Function)
        assert symbol.name == "func"

        # 应该捕获完整的函数调用：函数名 + 括号 + 参数
        expected_content = "func(arg1, arg2, arg3=expression)"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_function_call_complex_args(self):
        """测试复杂参数的函数调用捕获"""
        code = """func(
    param1,
    param2="string with spaces",
    param3=calculate_something(),
    *args,
    **kwargs
)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) >= 1  # 可能还有calculate_something()

        # 找到func调用
        func_call = None
        for node in nodes:
            result = self.processor.handle_reference(node, ctx)
            if result and result[0].name == "func":
                func_call = result
                break

        assert func_call is not None
        symbol, reference = func_call

        # 应该捕获完整的多行函数调用
        expected_content = """func(
    param1,
    param2="string with spaces",
    param3=calculate_something(),
    *args,
    **kwargs
)"""
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_call_simple(self):
        """测试简单方法调用的捕获"""
        code = """obj.method()"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Method)
        assert symbol.name == "method"
        assert symbol.class_name is None  # 调用时不知道类名

        # 应该捕获完整的方法调用：对象 + 点 + 方法名 + 括号
        expected_content = "obj.method()"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_call_with_args(self):
        """测试带参数的方法调用捕获"""
        code = """obj.method(arg1, arg2, kwarg=value)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Method)
        assert symbol.name == "method"

        # 应该捕获完整的方法调用：对象 + 点 + 方法名 + 括号 + 参数
        expected_content = "obj.method(arg1, arg2, kwarg=value)"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_call_class_method(self):
        """测试类方法调用的捕获"""
        code = """ClassFoo.method()"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Method)
        assert symbol.name == "method"

        # 应该捕获完整的类方法调用
        expected_content = "ClassFoo.method()"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_call_module_method(self):
        """测试模块方法调用的捕获"""
        code = """Module.method()"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Method)
        assert symbol.name == "method"

        # 应该捕获完整的模块方法调用
        expected_content = "Module.method()"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_call_chained(self):
        """测试链式方法调用的捕获"""
        code = """foo.bar().method()"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) >= 1

        # 应该能识别出两个方法调用：bar() 和 method()
        method_calls = []
        for node in nodes:
            result = self.processor.handle_reference(node, ctx)
            if result and isinstance(result[0], Method):
                method_calls.append(result)

        # 找到method()调用
        method_call = None
        for symbol, reference in method_calls:
            if symbol.name == "method":
                method_call = (symbol, reference)
                break

        assert method_call is not None
        symbol, reference = method_call

        # 应该捕获从foo开始的完整链式调用
        expected_content = "foo.bar().method()"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_call_complex_expression(self):
        """测试复杂表达式的方法调用捕获"""
        code = """(obj1 + obj2).method(arg)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")
        assert len(nodes) == 1

        result = self.processor.handle_reference(nodes[0], ctx)
        assert result is not None

        symbol, reference = result
        assert isinstance(symbol, Method)
        assert symbol.name == "method"

        # 应该捕获包括复杂表达式在内的完整方法调用
        expected_content = "(obj1 + obj2).method(arg)"
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content

    def test_method_call_multiline_expression(self):
        """测试多行表达式的方法调用捕获"""
        code = """(
    very_long_expression_that_spans
    .multiple_lines()
    .and_has_chaining()
).final_method(
    param1,
    param2
)"""

        nodes, ctx, source_bytes = self._parse_and_get_nodes(code, "reference")

        # 找到final_method调用
        final_method_call = None
        for node in nodes:
            result = self.processor.handle_reference(node, ctx)
            if result and result[0].name == "final_method":
                final_method_call = result
                break

        assert final_method_call is not None
        symbol, reference = final_method_call

        # 应该捕获完整的多行表达式和方法调用
        expected_content = """(
    very_long_expression_that_spans
    .multiple_lines()
    .and_has_chaining()
).final_method(
    param1,
    param2
)"""
        actual_content = source_bytes[
            reference.location.start_byte : reference.location.end_byte
        ].decode("utf-8")
        assert actual_content == expected_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
