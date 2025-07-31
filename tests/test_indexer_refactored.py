import pytest

from code_index.index.impl.simple_index import SimpleIndex
from code_index.index.persist.persist_json import SingleJsonFilePersistStrategy
from code_index.indexer import CodeIndexer
from code_index.language_processor.impl_c import CProcessor
from code_index.models import Function


@pytest.fixture
def c_processor():
    """提供一个 C 语言处理器实例。"""
    return CProcessor()


@pytest.fixture
def sample_c_code():
    """提供示例 C 代码。"""
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


class TestCodeIndexerRefactored:
    """测试重构后的 CodeIndexer 类。"""

    def test_indexer_with_custom_index_and_persist_strategy(
        self, c_processor, sample_c_code, tmp_path
    ):
        """测试使用自定义索引和持久化策略的索引器。"""
        # 创建测试文件
        test_file = tmp_path / "test.c"
        test_file.write_text(sample_c_code)

        # 使用自定义的索引和持久化策略创建索引器
        custom_index = SimpleIndex()
        custom_persist = SingleJsonFilePersistStrategy()
        indexer = CodeIndexer(processor=c_processor, index=custom_index)

        # 索引文件
        indexer.index_file(test_file, project_path=tmp_path)

        # 验证索引器使用了我们提供的索引实例
        assert indexer.index is custom_index

        # 验证索引功能
        definitions = indexer.find_definitions("helper_func")
        assert len(definitions) == 1
        assert definitions[0].location.start_lineno == 3

        references = indexer.find_references("helper_func")
        assert len(references) == 2

        # 不依赖列表顺序，检查所有期望的行号都存在
        reference_lines = {ref.location.start_lineno for ref in references}
        expected_lines = {8, 9}
        assert reference_lines == expected_lines

    def test_indexer_with_default_components(self, c_processor, sample_c_code, tmp_path):
        """测试使用默认组件的索引器。"""
        test_file = tmp_path / "test.c"
        test_file.write_text(sample_c_code)

        # 使用默认组件创建索引器
        indexer = CodeIndexer(processor=c_processor)

        # 验证默认组件被正确创建
        assert isinstance(indexer.index, SimpleIndex)

        # 索引文件
        indexer.index_file(test_file, project_path=tmp_path)

        # 验证功能正常
        all_functions = indexer.get_all_functions()
        function_names = [func.name for func in all_functions]
        assert "helper_func" in function_names
        assert "main" in function_names

    def test_index_persistence_and_loading(self, c_processor, sample_c_code, tmp_path):
        """测试索引的持久化和加载功能。"""
        # 创建测试文件
        test_file = tmp_path / "test.c"
        test_file.write_text(sample_c_code)
        index_file = tmp_path / "index.json"

        # 创建索引器并索引文件
        indexer1 = CodeIndexer(processor=c_processor)
        indexer1.index_file(test_file, project_path=tmp_path)

        # 持久化索引
        indexer1.dump_index(index_file, SingleJsonFilePersistStrategy())

        # 验证索引文件被创建
        assert index_file.exists()

        # 创建新的索引器并加载索引
        indexer2 = CodeIndexer(processor=c_processor)
        indexer2.load_index(index_file, SingleJsonFilePersistStrategy())

        # 验证加载的索引与原始索引相同
        original_funcs = set(func.name for func in indexer1.get_all_functions())
        loaded_funcs = set(func.name for func in indexer2.get_all_functions())
        assert original_funcs == loaded_funcs

        # 验证定义和引用数据
        original_defs = indexer1.find_definitions("helper_func")
        loaded_defs = indexer2.find_definitions("helper_func")
        assert len(original_defs) == len(loaded_defs)
        assert original_defs[0].location.start_lineno == loaded_defs[0].location.start_lineno

    def test_get_function_info(self, c_processor, sample_c_code, tmp_path):
        """测试获取函数信息的功能。"""
        test_file = tmp_path / "test.c"
        test_file.write_text(sample_c_code)

        indexer = CodeIndexer(processor=c_processor)
        indexer.index_file(test_file, project_path=tmp_path)

        # 测试获取存在的函数信息
        helper_func = Function(name="helper_func")
        func_info = indexer.get_function_info(helper_func)

        assert func_info is not None
        assert len(func_info.definitions) == 1
        assert len(func_info.references) == 2

        # 测试获取不存在的函数信息
        nonexistent_func = Function(name="nonexistent_func")
        func_info = indexer.get_function_info(nonexistent_func)
        assert func_info is None

    def test_clear_index(self, c_processor, sample_c_code, tmp_path):
        """测试清空索引功能。"""
        test_file = tmp_path / "test.c"
        test_file.write_text(sample_c_code)

        indexer = CodeIndexer(processor=c_processor)
        indexer.index_file(test_file, project_path=tmp_path)

        # 验证索引包含数据
        assert len(indexer.get_all_functions()) > 0

        # 清空索引
        indexer.clear_index()

        # 验证索引已清空
        assert len(indexer.get_all_functions()) == 0
        assert indexer.find_definitions("helper_func") == []
        assert indexer.find_references("helper_func") == []

    def test_indexer_backward_compatibility(self, c_processor, sample_c_code, tmp_path):
        """测试重构后的索引器保持向后兼容性。"""
        test_file = tmp_path / "test.c"
        test_file.write_text(sample_c_code)

        # 使用与原始 API 相同的方式创建索引器
        indexer = CodeIndexer(processor=c_processor, store_relative_paths=True)
        indexer.index_file(test_file, project_path=tmp_path)

        # 验证原有的 API 方法仍然工作
        definitions = indexer.find_definitions("helper_func")
        references = indexer.find_references("helper_func")

        assert len(definitions) == 1
        assert len(references) == 2

        # 验证 dump_index 方法仍然工作
        index_file = tmp_path / "backward_compat.json"
        indexer.dump_index(index_file, SingleJsonFilePersistStrategy())
        assert index_file.exists()

    def test_multiple_file_indexing(self, c_processor, tmp_path):
        """测试多文件索引功能。"""
        # 创建多个测试文件
        file1_content = """
void shared_func() {
    // implementation
}

void file1_func() {
    shared_func();
}
"""

        file2_content = """
void file2_func() {
    shared_func();  // 引用在 file1 中定义的函数
}
"""

        file1 = tmp_path / "file1.c"
        file2 = tmp_path / "file2.c"
        file1.write_text(file1_content)
        file2.write_text(file2_content)

        indexer = CodeIndexer(processor=c_processor)

        # 索引两个文件
        indexer.index_file(file1, project_path=tmp_path)
        indexer.index_file(file2, project_path=tmp_path)

        # 验证跨文件的定义和引用
        shared_defs = indexer.find_definitions("shared_func")
        shared_refs = indexer.find_references("shared_func")

        assert len(shared_defs) == 1  # 在 file1 中定义
        assert len(shared_refs) == 2  # 在两个文件中各有一个引用

        # 验证所有函数都被索引
        all_funcs = indexer.get_all_functions()
        func_names = [func.name for func in all_funcs]
        expected_funcs = ["shared_func", "file1_func", "file2_func"]

        for expected in expected_funcs:
            assert expected in func_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
