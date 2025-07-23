import json
from pathlib import Path
from dataclasses import is_dataclass, asdict
from typing import Dict

from ..models import FunctionInfo


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
            return asdict(o)

        # 对于其他所有类型，使用默认的编码器
        return super().default(o)


def dump_index_to_json(index: Dict[str, FunctionInfo], output_path: Path):
    """
    将索引数据以 JSON 格式写入文件。
    """
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(index, f, indent=4, ensure_ascii=False, cls=EnhancedJSONEncoder)
    print(f"Index data dumped to {output_path}")
