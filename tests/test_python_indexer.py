from pprint import pprint

import pytest
from pathlib import Path

# 导入我们需要测试的类和我们将要用到的辅助类
from code_index.indexer import CodeIndexer
from code_index.language_processor import PythonProcessor

# --- Fixture: 为 Python 测试提供可重用的处理器 ---


@pytest.fixture
def python_processor() -> PythonProcessor:
    """提供一个 Python 语言处理器实例。"""
    return PythonProcessor()


# --- Python 语言的测试 ---


def test_python_indexing_functions_and_methods(python_processor: PythonProcessor, tmp_path: Path):
    """
    测试对 Python 代码的索引功能，包括独立函数和类方法。
    """
    # 1. 准备硬编码的 Python 代码片段
    python_code = """
class MyCalculator:
    def add(self, a, b):
        return a + b

def standalone_func():
    calc = MyCalculator()
    calc.add(1, 2) # 方法引用

standalone_func() # 函数引用
"""
    test_file = tmp_path / "test_py.py"
    test_file.write_text(python_code)

    # 2. 初始化索引器并处理文件
    indexer = CodeIndexer(processor=python_processor)
    indexer.index_file(test_file, project_path=tmp_path)

    pprint(indexer.index.as_data())  # 打印索引内容以便调试

    # 3. 断言和验证
    # 验证独立函数
    def_func = indexer.find_definitions("standalone_func")
    assert len(def_func) == 1
    assert def_func[0].location.start_lineno == 6

    ref_func = indexer.find_references("standalone_func")
    assert len(ref_func) == 1
    assert ref_func[0].location.start_lineno == 10
