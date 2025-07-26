import json
from pathlib import Path
from dataclasses import is_dataclass, fields
from typing import Dict


class EnhancedJSONEncoder(json.JSONEncoder):
    """
    一个增强的 JSON 编码器，用于处理非原生支持的类型。

    - 自动将 pathlib.Path 对象转换为字符串。
    - 自动将任何 dataclass 对象转换为字典。
    """

    def default(self, o):
        # 如果对象是 Path 对象，则将其转换为字符串
        if isinstance(o, Path):
            return str(o)

        if is_dataclass(o):
            # do not use asdict to avoid recursion issues.
            dict_data = {f.name: getattr(o, f.name) for f in fields(o)}
            dict_data["__class__"] = o.__class__.__name__  # for deserializing
            return dict_data

        # 对于其他所有类型，使用默认的编码器
        return super().default(o)


JSON_TYPE_REGISTRY: Dict[str, type] = {}


def register_json_type(cls: type):
    """
    注册一个类型到 JSON 编码器，以便在序列化时能够正确处理。

    :param cls: 要注册的类型。
    """
    if not is_dataclass(cls):
        raise ValueError("Only dataclasses can be registered.")
    JSON_TYPE_REGISTRY[cls.__name__] = cls
    return cls


def custom_json_decoder(dct: Dict, strict=False) -> object:
    """
    自定义 JSON 解码器，用于将字典转换回相应的对象。

    :param dct: 包含类名和属性的字典。
    :param strict: 如果为 True，则在类未注册时抛出异常。
    :return: 解码后的对象。
    """
    if "file_path" in dct and isinstance(dct["file_path"], str):
        dct["file_path"] = Path(dct["file_path"])

    if "__class__" in dct:
        class_name = dct.pop("__class__")
        cls = JSON_TYPE_REGISTRY.get(class_name)
        if cls:
            # 检查数据类的字段，将应该是Path类型的字符串字段转换为Path对象
            if is_dataclass(cls):
                for field_info in fields(cls):
                    field_name = field_info.name
                    if (
                        field_name in dct
                        and isinstance(dct[field_name], str)
                        and field_info.type == Path
                    ):
                        dct[field_name] = Path(dct[field_name])
            return cls(**dct)
        elif strict:
            raise ValueError(f"Class {class_name} not registered in JSON_TYPE_REGISTRY.")
    return dct  # 返回原始字典，如果没有匹配的类


def dump_index_to_json(index: dict, output_path: Path):
    """
    将索引数据以 JSON 格式写入文件。
    """
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False, cls=EnhancedJSONEncoder)


def load_index_from_json(input_path: Path, strict=False) -> dict:
    """
    从 JSON 文件加载索引数据。

    :param input_path: 输入文件路径。
    :param strict: 如果为 True，则在类未注册时抛出异常。
    :return: 解码后的索引数据。
    """
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f, object_hook=lambda dct: custom_json_decoder(dct, strict))
    return data
