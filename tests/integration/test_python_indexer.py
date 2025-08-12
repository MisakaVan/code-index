from pathlib import Path

import pytest

from code_index.indexer import CodeIndexer
from code_index.language_processor import PythonProcessor
from code_index.models import Function, Method

# --- Fixtures ---


@pytest.fixture
def python_processor() -> PythonProcessor:
    return PythonProcessor()


@pytest.fixture
def indexer(python_processor: PythonProcessor) -> CodeIndexer:
    return CodeIndexer(processor=python_processor)


class TestPythonIndexer:
    def test_standalone_functions(self, indexer: CodeIndexer, tmp_path: Path):
        """测试独立函数的定义和引用索引。"""
        python_code = """
def calculate_sum(a, b):
    return a + b

def main():
    result = calculate_sum(10, 20)  # 函数引用
    print(result)

main()  # 函数引用
calculate_sum(5, 3)  # 函数引用
"""
        test_file = tmp_path / "standalone_functions.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 使用 indexer.index 的方法查找函数
        calculate_sum_func = Function(name="calculate_sum")
        sum_definitions = list(indexer.index.get_definitions(calculate_sum_func))
        assert len(sum_definitions) == 1
        assert sum_definitions[0].location.start_lineno == 2
        assert sum_definitions[0].location.file_path == Path("standalone_functions.py")

        sum_references = list(indexer.index.get_references(calculate_sum_func))
        assert len(sum_references) == 2  # 两次调用
        ref_lines = [ref.location.start_lineno for ref in sum_references]
        assert 6 in ref_lines and 10 in ref_lines

        # 验证 main 函数
        main_func = Function(name="main")
        main_definitions = list(indexer.index.get_definitions(main_func))
        assert len(main_definitions) == 1
        assert main_definitions[0].location.start_lineno == 5

        main_references = list(indexer.index.get_references(main_func))
        assert len(main_references) == 1
        assert main_references[0].location.start_lineno == 9

    def test_class_methods(self, indexer: CodeIndexer, tmp_path: Path):
        """测试类方法的定义和引用索引。"""
        python_code = """
class Calculator:
    def __init__(self, name):
        self.name = name

    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b

    def calculate(self, x, y):
        sum_result = self.add(x, y)  # 方法引用
        product = self.multiply(x, y)  # 方法引用
        return sum_result + product

calc = Calculator("MyCalc")
result1 = calc.add(5, 3)  # 方法引用
result2 = calc.multiply(4, 6)  # 方法引用
final = calc.calculate(2, 3)  # 方法引用
"""
        test_file = tmp_path / "class_methods.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        print(indexer.index)

        # 验证 add 方法定义 - 使用 Method 对象查找，带类名
        add_method_with_class = Method(name="add", class_name="Calculator")
        add_definitions = list(indexer.index.get_definitions(add_method_with_class))
        assert len(add_definitions) == 1
        assert add_definitions[0].location.start_lineno == 6

        # 验证 add 方法引用 - 方法调用时类名不可见，所以使用 class_name=None
        add_method_without_class = Method(name="add", class_name=None)
        add_references = list(indexer.index.get_references(add_method_without_class))
        assert len(add_references) == 2  # 2 次调用

        # 验证 multiply 方法定义
        multiply_method_with_class = Method(name="multiply", class_name="Calculator")
        multiply_definitions = list(indexer.index.get_definitions(multiply_method_with_class))
        assert len(multiply_definitions) == 1
        assert multiply_definitions[0].location.start_lineno == 9

        # 验证 multiply 方法引用
        multiply_method_without_class = Method(name="multiply", class_name=None)
        multiply_references = list(indexer.index.get_references(multiply_method_without_class))
        assert len(multiply_references) == 2

        # 验证 calculate 方法定义
        calculate_method_with_class = Method(name="calculate", class_name="Calculator")
        calculate_definitions = list(indexer.index.get_definitions(calculate_method_with_class))
        assert len(calculate_definitions) == 1
        assert calculate_definitions[0].location.start_lineno == 12

        # 验证 calculate 方法引用
        calculate_method_without_class = Method(name="calculate", class_name=None)
        calculate_references = list(indexer.index.get_references(calculate_method_without_class))
        assert len(calculate_references) == 1

    def test_nested_functions(self, indexer: CodeIndexer, tmp_path: Path):
        """测试嵌套函数的定义和引用索引。"""
        python_code = """
def outer_function(x):
    def inner_function(y):
        return y * 2

    def another_inner(z):
        return inner_function(z) + 1  # 内部函数引用

    result = inner_function(x)  # 内部函数引用
    return another_inner(result)  # 内部函数引用

value = outer_function(5)  # 外部函数引用
"""
        test_file = tmp_path / "nested_functions.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 验证外部函数
        outer_func = Function(name="outer_function")
        outer_definitions = list(indexer.index.get_definitions(outer_func))
        assert len(outer_definitions) == 1
        assert outer_definitions[0].location.start_lineno == 2

        outer_references = list(indexer.index.get_references(outer_func))
        assert len(outer_references) == 1
        assert outer_references[0].location.start_lineno == 12

        # 验证内部函数
        inner_func = Function(name="inner_function")
        inner_definitions = list(indexer.index.get_definitions(inner_func))
        assert len(inner_definitions) == 1
        assert inner_definitions[0].location.start_lineno == 3

        inner_references = list(indexer.index.get_references(inner_func))
        assert len(inner_references) == 2  # 两次调用

        # 验证另一个内部函数
        another_func = Function(name="another_inner")
        another_definitions = list(indexer.index.get_definitions(another_func))
        assert len(another_definitions) == 1
        assert another_definitions[0].location.start_lineno == 6

        another_references = list(indexer.index.get_references(another_func))
        assert len(another_references) == 1

    def test_mixed_functions_and_methods(self, indexer: CodeIndexer, tmp_path: Path):
        """测试混合的函数和方法定义与引用。"""
        python_code = """
def utility_function(data):
    return len(data)

class DataProcessor:
    def __init__(self, items):
        self.items = items

    def process(self):
        count = utility_function(self.items)  # 函数引用
        return self.transform(count)  # 方法引用

    def transform(self, value):
        return value * 2

def main():
    processor = DataProcessor([1, 2, 3, 4])
    result = processor.process()  # 方法引用
    final_count = utility_function([5, 6, 7])  # 函数引用
    return result + final_count

main()  # 函数引用
"""
        test_file = tmp_path / "mixed_code.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 验证独立函数
        utility_func = Function(name="utility_function")
        utility_definitions = list(indexer.index.get_definitions(utility_func))
        assert len(utility_definitions) == 1
        assert utility_definitions[0].location.start_lineno == 2

        utility_references = list(indexer.index.get_references(utility_func))
        assert len(utility_references) == 2

        # 验证方法定义 - 使用带类名的Method对象
        process_method_with_class = Method(name="process", class_name="DataProcessor")
        process_definitions = list(indexer.index.get_definitions(process_method_with_class))
        assert len(process_definitions) == 1
        assert process_definitions[0].location.start_lineno == 9

        # 验证方法引用 - 使用不带类名的Method对象
        process_method_without_class = Method(name="process", class_name=None)
        process_references = list(indexer.index.get_references(process_method_without_class))
        assert len(process_references) == 1

        transform_method_with_class = Method(name="transform", class_name="DataProcessor")
        transform_definitions = list(indexer.index.get_definitions(transform_method_with_class))
        assert len(transform_definitions) == 1
        assert transform_definitions[0].location.start_lineno == 13

        transform_method_without_class = Method(name="transform", class_name=None)
        transform_references = list(indexer.index.get_references(transform_method_without_class))
        assert len(transform_references) == 1

    def test_get_all_functions(self, indexer: CodeIndexer, tmp_path: Path):
        """测试获取所有函数和方法的功能。"""
        python_code = """
def global_func():
    pass

class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass

def another_global():
    pass
"""
        test_file = tmp_path / "all_functions.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        all_functions = list(indexer.index)
        function_names = [func.name for func in all_functions]

        assert "global_func" in function_names
        assert "method_one" in function_names
        assert "method_two" in function_names
        assert "another_global" in function_names
        assert len(all_functions) == 4

    def test_get_function_info(self, indexer: CodeIndexer, tmp_path: Path):
        """测试获取函数完整信息的功能。"""
        python_code = """
def target_function(param):
    return param * 2

target_function(5)  # 引用1
target_function(10)  # 引用2
result = target_function(15)  # 引用3
"""
        test_file = tmp_path / "function_info.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        func = Function(name="target_function")
        func_info = indexer.index.get_info(func)

        assert func_info is not None
        assert len(func_info.definitions) == 1
        assert len(func_info.references) == 3
        assert func_info.definitions[0].location.start_lineno == 2

    def test_clear_index(self, indexer: CodeIndexer, tmp_path: Path):
        """测试清空索引的功能。"""
        python_code = """
def test_func():
    pass

test_func()
"""
        test_file = tmp_path / "clear_test.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 验证索引中有数据
        all_functions_before = list(indexer.index)
        assert len(all_functions_before) > 0

        # 清空索引
        indexer.clear_index()

        # 验证索引已清空
        all_functions_after = list(indexer.index)
        assert len(all_functions_after) == 0

        test_func = Function(name="test_func")
        definitions = list(indexer.index.get_definitions(test_func))
        assert len(definitions) == 0

    def test_multiple_files_indexing(self, indexer: CodeIndexer, tmp_path: Path):
        """测试多文件索引功能。"""
        # 第一个文件
        file1_code = """
def shared_function():
    return "from file1"

def file1_specific():
    shared_function()  # 引用
"""
        file1 = tmp_path / "file1.py"
        file1.write_text(file1_code)

        # 第二个文件
        file2_code = """
def shared_function():
    return "from file2"

def file2_specific():
    shared_function()  # 引用
"""
        file2 = tmp_path / "file2.py"
        file2.write_text(file2_code)

        # 索引两个文件
        indexer.index_file(file1, project_path=tmp_path)
        indexer.index_file(file2, project_path=tmp_path)

        # 验证有两个同名函数的定义
        shared_func = Function(name="shared_function")
        shared_definitions = list(indexer.index.get_definitions(shared_func))
        assert len(shared_definitions) == 2

        # 验证有两个引用
        shared_references = list(indexer.index.get_references(shared_func))
        assert len(shared_references) == 2

        # 验证每个文件特有的函数
        file1_func = Function(name="file1_specific")
        file1_definitions = list(indexer.index.get_definitions(file1_func))
        assert len(file1_definitions) == 1

        file2_func = Function(name="file2_specific")
        file2_definitions = list(indexer.index.get_definitions(file2_func))
        assert len(file2_definitions) == 1

    def test_method_with_class_name(self, indexer: CodeIndexer, tmp_path: Path):
        """测试带类名的方法索引。"""
        python_code = """
class FirstClass:
    def common_method(self):
        return "first"

class SecondClass:
    def common_method(self):
        return "second"

    def call_method(self):
        return self.common_method()  # 方法引用

obj1 = FirstClass()
obj1.common_method()  # 方法引用

obj2 = SecondClass()
obj2.common_method()  # 方法引用
obj2.call_method()  # 方法引用
"""
        test_file = tmp_path / "method_classes.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 验证 FirstClass 的 common_method 定义
        first_method_with_class = Method(name="common_method", class_name="FirstClass")
        first_definitions = list(indexer.index.get_definitions(first_method_with_class))
        assert len(first_definitions) == 1

        # 验证 SecondClass 的 common_method 定义
        second_method_with_class = Method(name="common_method", class_name="SecondClass")
        second_definitions = list(indexer.index.get_definitions(second_method_with_class))
        assert len(second_definitions) == 1

        # 验证 call_method 定义
        call_method_with_class = Method(name="call_method", class_name="SecondClass")
        call_definitions = list(indexer.index.get_definitions(call_method_with_class))
        assert len(call_definitions) == 1

        # 验证方法引用 - 所有方法调用都使用 class_name=None
        common_method_without_class = Method(name="common_method", class_name=None)
        common_method_references = list(indexer.index.get_references(common_method_without_class))
        assert len(common_method_references) == 3  # 应该有多个 common_method 的调用

        call_method_without_class = Method(name="call_method", class_name=None)
        call_method_references = list(indexer.index.get_references(call_method_without_class))
        assert len(call_method_references) == 1

    def test_index_contains_and_items(self, indexer: CodeIndexer, tmp_path: Path):
        """测试索引的 contains 和 items 方法。"""
        python_code = """
def test_function():
    return "test"

class TestClass:
    def test_method(self):
        return "method"

test_function()
obj = TestClass()
obj.test_method()
"""
        test_file = tmp_path / "contains_test.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 测试 contains
        test_func = Function(name="test_function")
        assert test_func in indexer.index

        test_method = Method(name="test_method", class_name="TestClass")
        assert test_method in indexer.index

        nonexistent_func = Function(name="nonexistent")
        assert nonexistent_func not in indexer.index

        # 测试 items - 索引器可能会索引额外的项目（如构造函数调用等）
        items = list(indexer.index.items())
        # 验证至少包含我们期望的函数和方法
        indexed_items = {func_like.name: func_like for func_like, _ in items}

        assert "test_function" in indexed_items
        assert "test_method" in indexed_items

        # 验证每个项目都是 (FunctionLike, FunctionLikeInfo) 对
        for func_like, func_info in items:
            assert hasattr(func_like, "name")
            assert hasattr(func_info, "definitions")
            assert hasattr(func_info, "references")

    def test_index_getitem_and_setitem(self, indexer: CodeIndexer, tmp_path: Path):
        """测试索引的 getitem 和 setitem 方法。"""
        python_code = """
def sample_function():
    pass

sample_function()
"""
        test_file = tmp_path / "getitem_test.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 测试 getitem
        sample_func = Function(name="sample_function")
        func_info = indexer.index[sample_func]

        assert func_info is not None
        assert len(func_info.definitions) == 1
        assert len(func_info.references) == 1

        # 测试修改后重新设置（setitem）
        original_definitions = func_info.definitions[:]
        original_references = func_info.references[:]

        # 这里只是验证 setitem 接口存在并可以调用
        indexer.index[sample_func] = func_info

        # 验证设置后数据仍然正确
        retrieved_info = indexer.index[sample_func]
        assert len(retrieved_info.definitions) == len(original_definitions)
        assert len(retrieved_info.references) == len(original_references)

    def test_python_docstring_extraction_integration(self, indexer: CodeIndexer, tmp_path: Path):
        """测试Python文档字符串提取的集成功能。"""
        python_code = '''
def calculate_area(length, width):
    """
    Calculate the area of a rectangle.

    Args:
        length (float): The length of the rectangle
        width (float): The width of the rectangle

    Returns:
        float: The area of the rectangle
    """
    return length * width

def process_data(data_list):
    """Process a list of data items."""
    results = []
    for item in data_list:
        area = calculate_area(item[0], item[1])  # 函数引用
        results.append(area)
    return results

class Calculator:
    """A simple calculator class."""

    def __init__(self, initial_value=0):
        """
        Initialize the calculator.

        Args:
            initial_value (int): Starting value
        """
        self.value = initial_value

    def add(self, number):
        """Add a number to the current value."""
        self.value += number
        result = calculate_area(self.value, number)  # 函数引用
        return result

def function_without_docs():
    return "No documentation"

def main():
    calc = Calculator(10)
    result = calc.add(5)  # 方法引用
    data = process_data([(2, 3), (4, 5)])  # 函数引用
    return result
'''
        test_file = tmp_path / "documented_code.py"
        test_file.write_text(python_code)

        indexer.index_file(test_file, project_path=tmp_path)

        # 测试带有完整文档字符串的函数
        calculate_area_func = Function(name="calculate_area")
        area_definitions = list(indexer.index.get_definitions(calculate_area_func))
        assert len(area_definitions) == 1
        area_def = area_definitions[0]
        assert area_def.doc is not None
        assert "Calculate the area of a rectangle" in area_def.doc
        assert "Args:" in area_def.doc
        assert "Returns:" in area_def.doc
        assert "length (float)" in area_def.doc
        assert "width (float)" in area_def.doc

        # 测试带有简单文档字符串的函数
        process_data_func = Function(name="process_data")
        process_definitions = list(indexer.index.get_definitions(process_data_func))
        assert len(process_definitions) == 1
        process_def = process_definitions[0]
        assert process_def.doc is not None
        assert "Process a list of data items" in process_def.doc

        # 测试类方法的文档字符串
        init_method = Method(name="__init__", class_name="Calculator")
        init_definitions = list(indexer.index.get_definitions(init_method))
        assert len(init_definitions) == 1
        init_def = init_definitions[0]
        assert init_def.doc is not None
        assert "Initialize the calculator" in init_def.doc
        assert "Args:" in init_def.doc

        add_method = Method(name="add", class_name="Calculator")
        add_definitions = list(indexer.index.get_definitions(add_method))
        assert len(add_definitions) == 1
        add_def = add_definitions[0]
        assert add_def.doc is not None
        assert "Add a number to the current value" in add_def.doc

        # 测试没有文档字符串的函数
        no_docs_func = Function(name="function_without_docs")
        no_docs_definitions = list(indexer.index.get_definitions(no_docs_func))
        assert len(no_docs_definitions) == 1
        assert no_docs_definitions[0].doc is None

        # 验证函数调用仍然正常工作
        area_references = list(indexer.index.get_references(calculate_area_func))
        assert len(area_references) == 2  # 在process_data和Calculator.add中被调用

        # 验证文档字符串不影响交叉引用功能
        process_references = list(indexer.index.get_references(process_data_func))
        assert len(process_references) == 1  # 在main中被调用
