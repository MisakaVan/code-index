import json
from pathlib import Path
from typing import Any

from ..base import PersistStrategy
from ...utils.custom_json import dump_index_to_json, load_index_from_json


class SingleJsonFilePersistStrategy(PersistStrategy):
    """
    单个 JSON 文件持久化策略。
    """

    def __init__(self):
        super().__init__()

    def save(self, data: Any, path: Path):
        """
        将索引数据保存到单个 JSON 文件。

        :param data: 要保存的索引数据对象。可以是注册的 dataclass 或者其他可 JSON 序列化的对象
        :param path: 保存文件的路径
        :raises ValueError: 当路径是目录而不是文件时
        :raises FileNotFoundError: 当父目录不存在时
        :raises PermissionError: 当没有写入权限时
        """
        # 检查路径是否指向目录
        if path.exists() and path.is_dir():
            raise ValueError(f"指定的路径是一个目录，而不是文件：{path}")

        # 检查父目录是否存在
        parent_dir = path.parent
        if not parent_dir.exists():
            raise FileNotFoundError(
                f"父目录不存在：{parent_dir}。请先创建目录或使用存在的目录路径。"
            )

        # 检查父目录是否可写
        if not parent_dir.is_dir():
            raise ValueError(f"父路径不是一个目录：{parent_dir}")

        try:
            dump_index_to_json(data, path)
        except Exception as e:
            raise RuntimeError(f"保存索引数据到文件 {path} 时出错：{e}")

    def load(self, path: Path) -> Any:
        """
        从单个 JSON 文件加载索引数据。

        :param path: 要加载的 JSON 文件路径
        :return: 加载的索引数据字典
        :raises FileNotFoundError: 当文件不存在时
        :raises ValueError: 当路径是目录而不是文件时
        :raises json.JSONDecodeError: 当文件不是有效的JSON格式时
        """
        # 检查文件是否存在
        if not path.exists():
            raise FileNotFoundError(f"索引文件不存在：{path}")

        # 检查路径是否指向目录
        if path.is_dir():
            raise ValueError(f"指定的路径是一个目录，而不是文件：{path}")

        # 检查是否是普通文件
        if not path.is_file():
            raise ValueError(f"路径存在但不是普通文件：{path}")

        try:
            return load_index_from_json(path)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"文件 {path} 不是有效的JSON格式：{e.msg}", e.doc, e.pos)
        except Exception as e:
            raise RuntimeError(f"加载索引文件 {path} 时出错：{e}")
