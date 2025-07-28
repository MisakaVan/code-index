from pprint import pprint

import pytest
from pathlib import Path

# 导入我们需要测试的类和我们将要用到的辅助类
from code_index.indexer import CodeIndexer
from code_index.language_processor.impl_c import CProcessor
from code_index.language_processor.impl_cpp import CppProcessor

# --- Fixtures: 为 C 和 C++ 测试提供可重用的处理器 ---


@pytest.fixture
def c_processor() -> CProcessor:
    """提供一个 C 语言处理器实例。"""
    return CProcessor()


@pytest.fixture
def cpp_processor() -> CppProcessor:
    """提供一个 C++ 语言处理器实例。"""
    return CppProcessor()


# --- C 语言的测试 ---


def test_c_function_indexing(c_processor: CProcessor, tmp_path: Path):
    """
    测试 CProcessor 是否能正确索引函数的定义和引用。
    """
    # 1. 准备硬编码的 C 代码片段
    c_code = """#include <stdio.h>

void print_message(const char* msg) { // 定义
    printf("%s", msg);
}

int main() {
    print_message("Hello from C"); // 引用
    return 0;
}
"""
    test_file = tmp_path / "main.c"
    test_file.write_text(c_code)

    # 2. 初始化索引器并处理文件
    indexer = CodeIndexer(processor=c_processor)
    indexer.index_file(test_file, project_path=tmp_path)

    # 3. 断言和验证
    # 验证函数定义
    definitions = indexer.find_definitions("print_message")
    assert len(definitions) == 1
    assert definitions[0].location.start_lineno == 3

    # 验证函数引用
    references = indexer.find_references("print_message")
    assert len(references) == 1
    assert references[0].location.start_lineno == 8


# --- C++ 语言的测试 ---


def test_cpp_function_indexing(cpp_processor: CppProcessor, tmp_path: Path):
    """
    测试 CppProcessor 是否能正确索引全局函数的定义和引用。
    （当前不测试成员函数）
    """
    # 1. 准备硬编码的 C++ 代码片段
    cpp_code = """#include <iostream>

void log_value(int value) { // 定义
    std::cout << value << std::endl;
}

int main() {
    log_value(123); // 引用
    return 0;
}
"""
    test_file = tmp_path / "app.cpp"
    test_file.write_text(cpp_code)

    # 2. 初始化索引器并处理文件
    indexer = CodeIndexer(processor=cpp_processor)
    indexer.index_file(test_file, project_path=tmp_path)

    pprint(indexer.index.as_data())

    # 3. 断言和验证
    # 验证函数定义
    definitions = indexer.find_definitions("log_value")
    assert len(definitions) == 1
    assert definitions[0].location.start_lineno == 3

    # 验证函数引用
    references = indexer.find_references("log_value")
    assert len(references) == 1
    assert references[0].location.start_lineno == 8
