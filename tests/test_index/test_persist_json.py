import tempfile
from pathlib import Path

import pytest

from code_index.index.persist.persist_json import SingleJsonFilePersistStrategy
from code_index.models import (
    CodeLocation,
    Definition,
    Reference,
    FunctionLikeInfo,
    Function,
    Method,
)
from code_index.utils.custom_json import register_json_type, JSON_TYPE_REGISTRY


# 在每个测试前清理注册表，避免测试间相互影响
@pytest.fixture(autouse=True)
def clear_registry():
    original_registry = JSON_TYPE_REGISTRY.copy()
    JSON_TYPE_REGISTRY.clear()

    # 重新注册需要的模型类
    register_json_type(CodeLocation)
    register_json_type(Definition)
    register_json_type(Reference)
    register_json_type(FunctionLikeInfo)
    register_json_type(Function)
    register_json_type(Method)

    yield
    JSON_TYPE_REGISTRY.clear()
    JSON_TYPE_REGISTRY.update(original_registry)


@pytest.fixture
def sample_index_data():
    """创建示例索引数据用于测试"""
    # 创建示例位置
    location1 = CodeLocation(
        file_path=Path("/test/file1.py"),
        start_lineno=10,
        start_col=5,
        end_lineno=10,
        end_col=20,
        start_byte=100,
        end_byte=120,
    )
    location2 = CodeLocation(
        file_path=Path("/test/file2.py"),
        start_lineno=20,
        start_col=10,
        end_lineno=20,
        end_col=25,
        start_byte=150,
        end_byte=170,
    )

    # 创建示例函数
    function = Function(name="test_function")

    # 创建示例定义和引用
    definition = Definition(location=location1)
    reference = Reference(location=location2)

    # 创建函数信息
    func_info = FunctionLikeInfo(definitions=[definition], references=[reference])

    # 构建索引数据
    index_data = {
        "functions": {"test_function": func_info},
        "metadata": {"version": "1.0", "created_at": "2025-01-01T00:00:00"},
    }

    return index_data


class TestSingleJsonFilePersistStrategy:
    """测试 SingleJsonFilePersistStrategy 类"""

    def test_init(self):
        """测试初始化"""
        strategy = SingleJsonFilePersistStrategy()
        assert strategy is not None

    def test_save_and_load_simple_data(self):
        """测试保存和加载简单数据"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_index.json"

            # 简单测试数据
            test_data = {"simple": "data", "number": 42, "list": [1, 2, 3]}

            # 保存数据
            strategy.save(test_data, test_file)

            # 验证文件存在
            assert test_file.exists()

            # 加载数据
            loaded_data = strategy.load(test_file)

            # 验证数据完整性
            assert loaded_data == test_data

    def test_save_and_load_complex_index_data(self, sample_index_data):
        """测试保存和加载复杂索引数据"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "complex_index.json"

            # 保存复杂数据
            strategy.save(sample_index_data, test_file)

            # 验证文件存在
            assert test_file.exists()

            # 加载数据
            loaded_data = strategy.load(test_file)

            # 验证数据结构
            assert "functions" in loaded_data
            assert "metadata" in loaded_data

            # 验证函数信息数据
            func_info = loaded_data["functions"]["test_function"]
            assert isinstance(func_info, FunctionLikeInfo)

            # 验证定义数据
            assert len(func_info.definitions) == 1
            definition = func_info.definitions[0]
            assert isinstance(definition, Definition)
            assert isinstance(definition.location, CodeLocation)
            assert isinstance(definition.location.file_path, Path)
            assert definition.location.start_lineno == 10
            assert definition.location.start_col == 5

            # 验证引用数据
            assert len(func_info.references) == 1
            reference = func_info.references[0]
            assert isinstance(reference, Reference)
            assert isinstance(reference.location, CodeLocation)
            assert reference.location.start_lineno == 20

            # 验证元数据
            assert loaded_data["metadata"]["version"] == "1.0"

    def test_save_with_path_objects(self):
        """测试保存包含 Path 对象的数据"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "path_test.json"

            # 包含 Path 对象的数据
            data_with_paths = {
                "file_path": Path("/home/user/test.py"),
                "other_paths": [Path("/home/user/file1.py"), Path("/home/user/file2.py")],
                "nested": {"project_root": Path("/home/user/project")},
            }

            # 保存数据
            strategy.save(data_with_paths, test_file)

            # 加载数据
            loaded_data = strategy.load(test_file)

            # 验证 file_path 被正确转换回 Path 对象
            assert isinstance(loaded_data["file_path"], Path)
            assert str(loaded_data["file_path"]) == "/home/user/test.py"

            # 验证其他数据保持不变
            assert loaded_data["other_paths"] == ["/home/user/file1.py", "/home/user/file2.py"]
            assert loaded_data["nested"]["project_root"] == "/home/user/project"

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        strategy = SingleJsonFilePersistStrategy()

        nonexistent_file = Path("/nonexistent/path/file.json")

        with pytest.raises(FileNotFoundError, match="Index file does not exist"):
            strategy.load(nonexistent_file)

    def test_save_to_invalid_path(self):
        """测试保存到无效路径"""
        strategy = SingleJsonFilePersistStrategy()

        # 尝试保存到不存在的目录
        invalid_path = Path("/nonexistent/directory/file.json")
        test_data = {"test": "data"}

        with pytest.raises(FileNotFoundError, match="Parent directory does not exist"):
            strategy.save(test_data, invalid_path)

    def test_save_empty_data(self):
        """测试保存空数据"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "empty_data.json"

            # 保存空字典
            empty_data = {}
            strategy.save(empty_data, test_file)

            # 加载并验证
            loaded_data = strategy.load(test_file)
            assert loaded_data == empty_data

    def test_roundtrip_with_model_objects(self):
        """测试使用模型对象的完整往返序列化"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "model_objects.json"

            # 创建包含各种模型对象的数据
            location = CodeLocation(
                file_path=Path("/src/main.py"),
                start_lineno=100,
                start_col=15,
                end_lineno=100,
                end_col=30,
                start_byte=1000,
                end_byte=1020,
            )

            function = Function(name="main_function")
            method = Method(name="test_method", class_name="TestClass")
            definition = Definition(location=location)
            reference = Reference(location=location)

            func_info = FunctionLikeInfo(definitions=[definition], references=[reference])

            test_data = {
                "main_function": func_info,
                "locations": [location],
                "function_obj": function,
                "method_obj": method,
            }

            # 保存数据
            strategy.save(test_data, test_file)

            # 加载数据
            loaded_data = strategy.load(test_file)

            # 验证对象类型和数据完整性
            assert isinstance(loaded_data["main_function"], FunctionLikeInfo)
            assert len(loaded_data["main_function"].definitions) == 1
            assert isinstance(loaded_data["main_function"].definitions[0], Definition)
            assert isinstance(loaded_data["main_function"].definitions[0].location, CodeLocation)
            assert isinstance(loaded_data["main_function"].definitions[0].location.file_path, Path)

            assert len(loaded_data["locations"]) == 1
            assert isinstance(loaded_data["locations"][0], CodeLocation)

            assert isinstance(loaded_data["function_obj"], Function)
            assert loaded_data["function_obj"].name == "main_function"

            assert isinstance(loaded_data["method_obj"], Method)
            assert loaded_data["method_obj"].name == "test_method"
            assert loaded_data["method_obj"].class_name == "TestClass"

            # 验证原始数据和加载数据相等
            assert loaded_data["main_function"] == test_data["main_function"]
            assert loaded_data["locations"][0] == test_data["locations"][0]
            assert loaded_data["function_obj"] == test_data["function_obj"]
            assert loaded_data["method_obj"] == test_data["method_obj"]

    def test_save_and_load_with_mixed_function_types(self):
        """测试保存和加载包含不同函数类型的数据"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "mixed_functions.json"

            # 创建不同类型的函数对象
            location1 = CodeLocation(
                file_path=Path("/src/utils.py"),
                start_lineno=50,
                start_col=0,
                end_lineno=55,
                end_col=10,
                start_byte=500,
                end_byte=550,
            )

            location2 = CodeLocation(
                file_path=Path("/src/class.py"),
                start_lineno=100,
                start_col=4,
                end_lineno=105,
                end_col=15,
                start_byte=1000,
                end_byte=1050,
            )

            function = Function(name="utility_function")
            method = Method(name="class_method", class_name="MyClass")

            func_def = Definition(location=location1)
            method_def = Definition(location=location2)

            test_data = {
                "utility_function": FunctionLikeInfo(definitions=[func_def]),
                "class_method": FunctionLikeInfo(definitions=[method_def]),
                "function_objects": [function, method],
            }

            # 保存数据
            strategy.save(test_data, test_file)

            # 加载数据
            loaded_data = strategy.load(test_file)

            # 验证不同类型的函数对象都被正确处理
            utility_info = loaded_data["utility_function"]
            assert isinstance(utility_info, FunctionLikeInfo)
            assert len(utility_info.definitions) == 1

            class_info = loaded_data["class_method"]
            assert isinstance(class_info, FunctionLikeInfo)
            assert len(class_info.definitions) == 1

            # 验证函数对象列表
            func_objects = loaded_data["function_objects"]
            assert len(func_objects) == 2
            assert isinstance(func_objects[0], Function)
            assert isinstance(func_objects[1], Method)
            assert func_objects[0].name == "utility_function"
            assert func_objects[1].name == "class_method"
            assert func_objects[1].class_name == "MyClass"

    def test_save_to_directory_path(self):
        """测试保存到目录路径应该抛出异常"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 尝试保存到目录而不是文件
            directory_path = Path(temp_dir)
            test_data = {"test": "data"}

            with pytest.raises(ValueError, match="Specified path is a directory, not a file"):
                strategy.save(test_data, directory_path)

    def test_save_to_nonexistent_parent_directory(self):
        """测试保存到不存在的父目录应该抛出异常"""
        strategy = SingleJsonFilePersistStrategy()

        # 使用不存在的父目录
        nonexistent_path = Path("/nonexistent/directory/file.json")
        test_data = {"test": "data"}

        with pytest.raises(FileNotFoundError, match="Parent directory does not exist"):
            strategy.save(test_data, nonexistent_path)

    def test_save_parent_is_not_directory(self):
        """测试当父路径不是目录时应该抛出异常"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建一个文件
            parent_file = Path(temp_dir) / "parent_file.txt"
            parent_file.write_text("test content")

            # 尝试在文件下创建子文件
            invalid_path = parent_file / "subfile.json"
            test_data = {"test": "data"}

            with pytest.raises(ValueError, match="Parent path is not a directory"):
                strategy.save(test_data, invalid_path)

    def test_load_directory_path(self):
        """测试加载目录路径应该抛出异常"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = Path(temp_dir)

            with pytest.raises(ValueError, match="Specified path is a directory, not a file"):
                strategy.load(directory_path)

    def test_save_data_serialization_error(self):
        """测试保存不可序列化数据时的异常处理"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.json"

            # 创建包含不可序列化对象的数据
            class UnserializableClass:
                pass

            unserializable_data = {"normal": "data", "unserializable": UnserializableClass()}

            with pytest.raises(RuntimeError, match="Error saving index data to file.*"):
                strategy.save(unserializable_data, test_file)

    def test_save_with_existing_non_file(self):
        """测试当目标路径存在但不是普通文件时的处理"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建一个目录，然后尝试用同名保存文件
            special_path = Path(temp_dir) / "special"
            special_path.mkdir()
            test_data = {"test": "data"}

            with pytest.raises(ValueError, match="Specified path is a directory, not a file"):
                strategy.save(test_data, special_path)

    def test_comprehensive_path_validation(self):
        """测试完整的路径验证流程"""
        strategy = SingleJsonFilePersistStrategy()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 测试正常的保存和加载流程
            valid_file = Path(temp_dir) / "valid.json"
            test_data = {"valid": "data", "number": 42}

            # 保存应该成功
            strategy.save(test_data, valid_file)
            assert valid_file.exists()
            assert valid_file.is_file()

            # 加载应该成功
            loaded_data = strategy.load(valid_file)
            assert loaded_data == test_data

            # 测试覆盖现有文件
            new_data = {"updated": "data"}
            strategy.save(new_data, valid_file)

            # 验证文件被正确更新
            updated_data = strategy.load(valid_file)
            assert updated_data == new_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
