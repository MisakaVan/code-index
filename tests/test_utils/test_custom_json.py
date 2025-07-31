import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from code_index.utils.custom_json import (
    register_json_type,
    EnhancedJSONEncoder,
    custom_json_decoder,
    dump_index_to_json,
    load_index_from_json,
    JSON_TYPE_REGISTRY,
)


# 在每个测试前清理注册表，避免测试间相互影响
@pytest.fixture(autouse=True)
def clear_registry():
    original_registry = JSON_TYPE_REGISTRY.copy()
    JSON_TYPE_REGISTRY.clear()

    # 重新注册测试用的数据类
    register_json_type(SampleDataClass)
    register_json_type(ComplexSampleData)

    yield
    JSON_TYPE_REGISTRY.clear()
    JSON_TYPE_REGISTRY.update(original_registry)


@dataclass
class SampleDataClass:
    name: str
    value: int
    items: list = field(default_factory=list)


@dataclass
class ComplexSampleData:
    title: str
    path: Path
    nested_data: SampleDataClass
    numbers: list = field(default_factory=list)


# 注册测试数据类
register_json_type(SampleDataClass)
register_json_type(ComplexSampleData)


class TestEnhancedJSONEncoder:
    """测试增强的JSON编码器"""

    def test_encode_path_object(self):
        """测试Path对象的编码"""
        data = {"file_path": Path("/home/user/file.txt")}
        encoded = json.dumps(data, cls=EnhancedJSONEncoder)
        decoded = json.loads(encoded)

        assert decoded["file_path"] == "/home/user/file.txt"

    def test_encode_registered_dataclass(self):
        """测试已注册数据类的编码"""
        instance = SampleDataClass(name="test", value=42, items=[1, 2, 3])
        encoded = json.dumps(instance, cls=EnhancedJSONEncoder)
        decoded = json.loads(encoded)

        assert decoded["__class__"] == "SampleDataClass"
        assert decoded["name"] == "test"
        assert decoded["value"] == 42
        assert decoded["items"] == [1, 2, 3]

    def test_encode_complex_nested_data(self):
        """测试复杂嵌套数据的编码"""
        nested = SampleDataClass(name="nested", value=100)
        instance = ComplexSampleData(
            title="Complex Test", path=Path("/tmp/test"), nested_data=nested, numbers=[1, 2, 3, 4]
        )

        encoded = json.dumps(instance, cls=EnhancedJSONEncoder)
        decoded = json.loads(encoded)

        assert decoded["__class__"] == "ComplexSampleData"
        assert decoded["title"] == "Complex Test"
        assert decoded["path"] == "/tmp/test"
        assert decoded["nested_data"]["__class__"] == "SampleDataClass"
        assert decoded["nested_data"]["name"] == "nested"
        assert decoded["numbers"] == [1, 2, 3, 4]


class TestCustomJSONDecoder:
    """测试自定义JSON解码器"""

    def test_decode_registered_dataclass(self):
        """测试已注册数据类的解码"""
        data = {"__class__": "SampleDataClass", "name": "test", "value": 42, "items": [1, 2, 3]}

        result = custom_json_decoder(data)

        assert isinstance(result, SampleDataClass)
        assert result.name == "test"
        assert result.value == 42
        assert result.items == [1, 2, 3]

    def test_decode_file_path_conversion(self):
        """测试file_path字段的自动转换"""
        data = {"file_path": "/home/user/document.txt", "other": "value"}

        result = custom_json_decoder(data)

        assert isinstance(result, dict)
        assert isinstance(result["file_path"], Path)
        assert str(result["file_path"]) == "/home/user/document.txt"
        assert result["other"] == "value"

    def test_decode_unregistered_class_non_strict(self):
        """测试在非严格模式下解码未注册的类"""
        data = {"__class__": "UnregisteredClass", "field1": "value1", "field2": 123}

        result = custom_json_decoder(data, strict=False)

        # 应该返回原始字典（去掉__class__）
        assert isinstance(result, dict)
        assert result == {"field1": "value1", "field2": 123}

    def test_decode_unregistered_class_strict_mode(self):
        """测试在严格模式下解码未注册的类应该抛出异常"""
        data = {"__class__": "UnregisteredClass", "field1": "value1"}

        with pytest.raises(ValueError, match="Class UnregisteredClass not registered"):
            custom_json_decoder(data, strict=True)

    def test_decode_without_class_info(self):
        """测试解码没有__class__信息的普通字典"""
        data = {"normal": "dict", "value": 42}

        result = custom_json_decoder(data)

        assert result == data


class TestRoundTripSerialization:
    """测试完整的序列化和反序列化过程"""

    def test_simple_dataclass_roundtrip(self):
        """测试简单数据类的往返序列化"""
        original = SampleDataClass(name="roundtrip", value=99, items=["a", "b", "c"])

        # 编码
        encoded = json.dumps(original, cls=EnhancedJSONEncoder)

        # 解码
        decoded = json.loads(encoded, object_hook=custom_json_decoder)

        assert isinstance(decoded, SampleDataClass)
        assert decoded == original

    def test_complex_nested_roundtrip(self):
        """测试复杂嵌套数据的往返序列化"""
        nested = SampleDataClass(name="inner", value=50, items=[10, 20])
        original = ComplexSampleData(
            title="Roundtrip Test",
            path=Path("/var/log/test.log"),
            nested_data=nested,
            numbers=[100, 200, 300],
        )

        # 编码
        encoded = json.dumps(original, cls=EnhancedJSONEncoder)

        # 解码
        decoded = json.loads(encoded, object_hook=custom_json_decoder)

        assert isinstance(decoded, ComplexSampleData)
        assert decoded.title == original.title
        assert isinstance(decoded.path, Path)
        assert decoded.path == original.path
        assert isinstance(decoded.nested_data, SampleDataClass)
        assert decoded.nested_data == original.nested_data
        assert decoded.numbers == original.numbers


class TestFileOperations:
    """测试文件转储和加载操作"""

    def test_dump_and_load_index(self):
        """测试索引的转储和加载"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_index.json"

            # 创建测试数据
            data1 = SampleDataClass(name="entry1", value=1, items=["x", "y"])
            data2 = SampleDataClass(name="entry2", value=2, items=["z"])

            index_data = {
                "entry1": data1,
                "entry2": data2,
                "metadata": {"version": "1.0", "count": 2},
            }

            # 转储到文件
            dump_index_to_json(index_data, output_file)

            # 验证文件存在
            assert output_file.exists()

            # 从文件加载
            loaded_data = load_index_from_json(output_file)

            # 验证加载的数据
            assert isinstance(loaded_data["entry1"], SampleDataClass)
            assert isinstance(loaded_data["entry2"], SampleDataClass)
            assert loaded_data["entry1"] == data1
            assert loaded_data["entry2"] == data2
            assert loaded_data["metadata"] == {"version": "1.0", "count": 2}

    def test_load_with_strict_mode(self):
        """测试在严格模式下加载包含未注册类的文件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "strict_test.json"

            # 手动创建包含未注册类的JSON文件
            invalid_data = {
                "valid_entry": {
                    "__class__": "SampleDataClass",
                    "name": "valid",
                    "value": 1,
                    "items": [],
                },
                "invalid_entry": {"__class__": "UnknownClass", "field": "value"},
            }

            with test_file.open("w") as f:
                json.dump(invalid_data, f)

            # 在严格模式下应该抛出异常
            with pytest.raises(ValueError, match="Class UnknownClass not registered"):
                load_index_from_json(test_file, strict=True)

            # 在非严格模式下应该成功加载
            loaded = load_index_from_json(test_file, strict=False)
            assert isinstance(loaded["valid_entry"], SampleDataClass)
            assert isinstance(loaded["invalid_entry"], dict)


class TestDataClassRegistry:
    """测试数据类注册表功能"""

    def test_register_dataclass(self):
        """测试注册数据类"""

        @register_json_type
        @dataclass
        class NewDataClass:
            field: str

        assert "NewDataClass" in JSON_TYPE_REGISTRY
        assert JSON_TYPE_REGISTRY["NewDataClass"] == NewDataClass

    def test_register_non_dataclass_raises_error(self):
        """测试注册非数据类应该抛出异常"""

        class RegularClass:
            pass

        with pytest.raises(ValueError, match="Only dataclasses can be registered"):
            register_json_type(RegularClass)

    def test_registry_isolation_between_tests(self):
        """测试测试间的注册表隔离"""
        # 这个测试验证 clear_registry fixture 是否正常工作
        initial_count = len(JSON_TYPE_REGISTRY)

        @register_json_type
        @dataclass
        class TemporaryClass:
            temp_field: str

        assert len(JSON_TYPE_REGISTRY) == initial_count + 1
        # 在下一个测试中，这个类不应该存在于注册表中


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
