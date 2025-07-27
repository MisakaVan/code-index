import pytest
from pathlib import Path
from code_index.language_processor.impl_python import PythonProcessor
from code_index.language_processor.base import QueryContext
from code_index.models import Function, Definition, Reference, FunctionLikeRef, Method


class TestPythonProcessor:
    """测试Python语言处理器"""

    @pytest.fixture
    def python_processor(self):
        return PythonProcessor()

    @pytest.fixture
    def sample_python_code(self):
        return """def helper_func(x):
    print(f"Helper: {x}")

class MyClass:
    def method_func(self):
        helper_func(10)
        return "done"

def main():
    helper_func(42)
    helper_func(100)
    obj = MyClass()
    obj.method_func()

if __name__ == "__main__":
    main()
"""

    def test_python_processor_initialization(self, python_processor):
        """测试Python处理器的初始化"""
        assert python_processor.name == "python"
        assert ".py" in python_processor.extensions
        assert python_processor.parser is not None
        assert python_processor.language is not None

    def test_python_function_definition_parsing(self, python_processor, sample_python_code):
        """测试Python函数定义的解析"""
        source_bytes = sample_python_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("test.py"), source_bytes=source_bytes)

        # 获取定义节点
        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        # 应该包括 helper_func, method_func, main
        assert len(definition_nodes) >= 3

        # 处理所有定义节点，看看实际找到了什么
        found_functions = []
        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result:
                found_functions.append((result[0].name, result[1].location.start_lineno))

        # 验证找到了预期的函数
        function_names = [func[0] for func in found_functions]
        assert function_names.count("helper_func") == 1
        assert function_names.count("main") == 1

        # 根据Python查询的实际行为，可能包含类方法，所以我们检查至少包含这两个函数
        assert len(found_functions) >= 2

        # 验证helper_func在第1行定义
        helper_func_line = next(
            (line for name, line in found_functions if name == "helper_func"), None
        )
        assert helper_func_line == 1

        # 验证main在第9行定义
        main_func_line = next((line for name, line in found_functions if name == "main"), None)
        assert main_func_line == 9

    def test_python_function_reference_parsing(self, python_processor, sample_python_code):
        """测试Python函数引用的解析"""
        source_bytes = sample_python_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("test.py"), source_bytes=source_bytes)

        # 获取引用节点
        reference_nodes = list(python_processor.get_reference_nodes(tree.root_node))
        assert len(reference_nodes) >= 2  # 至少有helper_func的调用

        # 找到helper_func的引用
        helper_refs = []
        for ref_node in reference_nodes:
            result = python_processor.handle_reference(ref_node, ctx)
            if result and result[0].name == "helper_func":
                helper_refs.append(result)

        assert len(helper_refs) >= 2  # 应该有至少两个helper_func的调用

        # 验证引用位置信息
        ref_lines = {ref[1].location.start_lineno for ref in helper_refs}
        assert 6 in ref_lines or 10 in ref_lines  # helper_func的调用位置

    def test_python_processor_with_nested_functions(self, python_processor):
        """测试Python处理器处理嵌套函数"""
        nested_code = """def outer_func():
    def inner_func():
        print("inner")

    inner_func()
    return "outer"

def another_func():
    outer_func()
"""
        source_bytes = nested_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("nested.py"), source_bytes=source_bytes)

        # 获取定义节点
        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        assert len(definition_nodes) >= 3  # outer_func, inner_func, another_func

        # 验证所有函数都被正确识别
        func_names = []
        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result:
                func_names.append(result[0].name)

        assert "outer_func" in func_names
        assert "inner_func" in func_names
        assert "another_func" in func_names

    def test_python_processor_with_decorators(self, python_processor):
        """测试Python处理器处理装饰器函数"""
        decorator_code = """def my_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@my_decorator
def decorated_func():
    return "decorated"

def normal_func():
    decorated_func()
"""
        source_bytes = decorator_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("decorator.py"), source_bytes=source_bytes)

        # 获取定义节点
        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        assert len(definition_nodes) >= 4  # my_decorator, wrapper, decorated_func, normal_func

        # 验证装饰器函数被正确识别
        func_names = []
        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result:
                func_names.append(result[0].name)

        assert "my_decorator" in func_names
        assert "decorated_func" in func_names
        assert "normal_func" in func_names

    def test_python_processor_malformed_code(self, python_processor):
        """测试Python处理器处理格式错误的代码"""
        malformed_python = b"def func( # missing colon and closing parenthesis"
        tree = python_processor.parser.parse(malformed_python)

        ctx = QueryContext(file_path=Path("malformed.py"), source_bytes=malformed_python)

        # 即使代码格式错误，处理器也不应该崩溃
        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        reference_nodes = list(python_processor.get_reference_nodes(tree.root_node))

        # 处理器应该优雅地处理错误，不会崩溃
        assert isinstance(definition_nodes, list)
        assert isinstance(reference_nodes, list)

    def test_python_processor_empty_file(self, python_processor):
        """测试Python处理器处理空文件"""
        source_bytes = b""
        tree = python_processor.parser.parse(source_bytes)

        ctx = QueryContext(file_path=Path("empty.py"), source_bytes=source_bytes)

        # 空文件不应该有任何定义或引用
        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        reference_nodes = list(python_processor.get_reference_nodes(tree.root_node))

        assert len(definition_nodes) == 0
        assert len(reference_nodes) == 0

    def test_python_function_calls_tracking(self, python_processor):
        """测试Python函数定义中的函数调用追踪功能"""
        code_with_calls = """def helper_func(x):
    print(f"Helper: {x}")
    return x * 2

def utility_func():
    return "utility"

def main_func():
    result1 = helper_func(5)
    result2 = helper_func(10)
    util = utility_func()
    print(result1, result2, util)
    return result1 + result2

def another_func():
    main_func()
    helper_func(100)
"""
        source_bytes = code_with_calls.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("test_calls.py"), source_bytes=source_bytes)

        # 获取main_func的定义节点
        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        main_func_result = None
        another_func_result = None

        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "main_func":
                main_func_result = result
            elif result and result[0].name == "another_func":
                another_func_result = result

        # 验证main_func被找到并包含调用信息
        assert main_func_result is not None
        symbol, definition = main_func_result
        assert (
            len(definition.calls) == 4
        )  # helper_func(5), helper_func(10), utility_func(), print()

        # 验证调用的函数名
        called_functions = [call.symbol.name for call in definition.calls]
        assert called_functions.count("helper_func") == 2
        assert called_functions.count("utility_func") == 1
        assert called_functions.count("print") == 1

        # 验证another_func的调用
        assert another_func_result is not None
        another_symbol, another_definition = another_func_result
        assert another_symbol.name == "another_func"
        assert len(another_definition.calls) == 2  # main_func(), helper_func(100)

        another_called_functions = [call.symbol.name for call in another_definition.calls]
        assert "main_func" in another_called_functions
        assert "helper_func" in another_called_functions

    def test_python_function_calls_with_nested_calls(self, python_processor):
        """测试嵌套函数调用的追踪"""
        nested_calls_code = """def inner_helper():
    return "inner"

def outer_func():
    def nested_func():
        inner_helper()
        return "nested"
    
    result = nested_func()
    return result

def top_level():
    outer_func()
    inner_helper()
"""
        source_bytes = nested_calls_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("nested_calls.py"), source_bytes=source_bytes)

        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))

        # 查找outer_func和nested_func的定义
        outer_func_result = None
        nested_func_result = None
        top_level_result = None

        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result:
                if result[0].name == "outer_func":
                    outer_func_result = result
                elif result[0].name == "nested_func":
                    nested_func_result = result
                elif result[0].name == "top_level":
                    top_level_result = result

        # 验证outer_func调用了nested_func
        assert outer_func_result is not None
        outer_calls = [call.symbol.name for call in outer_func_result[1].calls]
        assert "nested_func" in outer_calls

        # 验证nested_func调用了inner_helper
        assert nested_func_result is not None
        nested_calls = [call.symbol.name for call in nested_func_result[1].calls]
        assert "inner_helper" in nested_calls

        # 验证top_level调用了outer_func和inner_helper
        assert top_level_result is not None
        top_calls = [call.symbol.name for call in top_level_result[1].calls]
        assert "outer_func" in top_calls
        assert "inner_helper" in top_calls

    def test_python_function_calls_location_accuracy(self, python_processor):
        """测试函数调用位置信息的准确性"""
        location_test_code = """def target_func():
    return "target"

def caller_func():
    result1 = target_func()  # Line 5
    print("middle")
    result2 = target_func()  # Line 7
    return result1 + result2
"""
        source_bytes = location_test_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("location_test.py"), source_bytes=source_bytes)

        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        caller_func_result = None

        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
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
        assert 5 in call_lines
        assert 7 in call_lines

    def test_python_function_calls_empty_function(self, python_processor):
        """测试空函数的调用追踪"""
        empty_func_code = """def empty_func():
    pass

def func_with_docstring():
    '''This function has only a docstring'''
    pass

def func_calling_empty():
    empty_func()
    func_with_docstring()
"""
        source_bytes = empty_func_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("empty_test.py"), source_bytes=source_bytes)

        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))

        # 查找各个函数的定义
        results = {}
        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result:
                results[result[0].name] = result

        # 验证空函数没有调用
        assert "empty_func" in results
        assert len(results["empty_func"][1].calls) == 0

        assert "func_with_docstring" in results
        assert len(results["func_with_docstring"][1].calls) == 0

        # 验证调用空函数的函数
        assert "func_calling_empty" in results
        calling_func_calls = [call.symbol.name for call in results["func_calling_empty"][1].calls]
        # 使用更严格的检查：确保每个函数只被调用一次
        assert calling_func_calls.count("empty_func") == 1
        assert calling_func_calls.count("func_with_docstring") == 1
        assert len(calling_func_calls) == 2  # 总共应该只有2个调用

    def test_python_method_calls_tracking(self, python_processor):
        """测试Python方法调用追踪功能"""
        code_with_method_calls = """def test_function():
    obj = MyClass()
    result1 = obj.method1()
    result2 = obj.method2(arg1, arg2)
    
    # 链式调用
    chained = obj.method1().method2()
    
    # 静态方法风格调用
    static_result = MyClass.static_method()
    
    # 普通函数调用
    func_result = regular_function()
    
    return result1

def another_function():
    obj = SomeClass()
    obj.do_something()
    print("done")
"""
        source_bytes = code_with_method_calls.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("method_calls.py"), source_bytes=source_bytes)

        # 获取test_function的定义节点
        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        test_func_result = None
        another_func_result = None

        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "test_function":
                test_func_result = result
            elif result and result[0].name == "another_function":
                another_func_result = result

        # 验证test_function被找到并包含调用信息
        assert test_func_result is not None
        symbol, definition = test_func_result
        assert symbol.name == "test_function"

        # 验证调用的函数和方法
        called_functions = []
        called_methods = []

        for call in definition.calls:
            if isinstance(call.symbol, Function):
                called_functions.append(call.symbol.name)
            elif isinstance(call.symbol, Method):
                called_methods.append(call.symbol.name)

        # 验证方法调用
        assert "method1" in called_methods
        assert "method2" in called_methods
        assert "static_method" in called_methods
        assert (
            called_methods.count("method1") == 2
        )  # obj.method1() 和 obj.method1().method2()中的第一个
        assert called_methods.count("method2") == 2  # obj.method2(arg1, arg2) 和链式调用中的第二个

        # 验证函数调用
        assert "regular_function" in called_functions

        # 验证another_function的调用
        assert another_func_result is not None
        another_symbol, another_definition = another_func_result
        assert another_symbol.name == "another_function"

        another_called_methods = [
            call.symbol.name for call in another_definition.calls if isinstance(call.symbol, Method)
        ]
        another_called_functions = [
            call.symbol.name
            for call in another_definition.calls
            if isinstance(call.symbol, Function)
        ]

        assert "do_something" in another_called_methods
        assert "print" in another_called_functions

    def test_python_method_calls_class_name_none(self, python_processor):
        """测试方法调用的class_name字段为None"""
        method_call_code = """def test_func():
    obj.method()
    MyClass.static_method()
    some_var.another_method()
"""
        source_bytes = method_call_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("class_name_test.py"), source_bytes=source_bytes)

        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        test_func_result = None

        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "test_func":
                test_func_result = result
                break

        assert test_func_result is not None
        symbol, definition = test_func_result

        # 验证所有方法调用的class_name都为None
        for call in definition.calls:
            if isinstance(call.symbol, Method):
                assert call.symbol.class_name is None

    def test_python_mixed_calls_location_accuracy(self, python_processor):
        """测试混合调用（函数和方法）位置信息的准确性"""
        location_test_code = """def caller_func():
    func_call()        # Line 2 - 函数调用
    obj.method_call()  # Line 3 - 方法调用
    another_func()     # Line 4 - 函数调用
    obj.another_method()  # Line 5 - 方法调用
"""
        source_bytes = location_test_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("location_test.py"), source_bytes=source_bytes)

        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        caller_func_result = None

        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "caller_func":
                caller_func_result = result
                break

        assert caller_func_result is not None
        symbol, definition = caller_func_result

        # 验证调用位置
        function_calls = [call for call in definition.calls if isinstance(call.symbol, Function)]
        method_calls = [call for call in definition.calls if isinstance(call.symbol, Method)]

        # 验证函数调用位置
        func_call_lines = {call.reference.location.start_lineno for call in function_calls}
        assert 2 in func_call_lines  # func_call()
        assert 4 in func_call_lines  # another_func()

        # 验证方法调用位置
        method_call_lines = {call.reference.location.start_lineno for call in method_calls}
        assert 3 in method_call_lines  # obj.method_call()
        assert 5 in method_call_lines  # obj.another_method()

    def test_python_chained_method_calls(self, python_processor):
        """测试链式方法调用"""
        chained_calls_code = """def test_chained():
    # 简单链式调用
    result1 = obj.method1().method2()
    
    # 复杂链式调用
    result2 = obj.first().second().third()
    
    # 混合链式调用
    result3 = get_obj().process().finalize()
"""
        source_bytes = chained_calls_code.encode("utf-8")
        tree = python_processor.parser.parse(source_bytes)
        ctx = QueryContext(file_path=Path("chained_calls.py"), source_bytes=source_bytes)

        definition_nodes = list(python_processor.get_definition_nodes(tree.root_node))
        test_result = None

        for def_node in definition_nodes:
            result = python_processor.handle_definition(def_node, ctx)
            if result and result[0].name == "test_chained":
                test_result = result
                break

        assert test_result is not None
        symbol, definition = test_result

        # 统计方法调用
        method_names = [
            call.symbol.name for call in definition.calls if isinstance(call.symbol, Method)
        ]
        function_names = [
            call.symbol.name for call in definition.calls if isinstance(call.symbol, Function)
        ]

        # 验证方法调用
        assert "method1" in method_names
        assert "method2" in method_names
        assert "first" in method_names
        assert "second" in method_names
        assert "third" in method_names
        assert "process" in method_names
        assert "finalize" in method_names

        # 验证函数调用
        assert "get_obj" in function_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
