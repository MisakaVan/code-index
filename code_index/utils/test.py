"""
测试工具函数模块

提供用于测试的实用函数，包括数据比较和断言功能。
"""

import dataclasses
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from ..models import (
    IndexData,
)


def normalize_path(path: Union[Path, str]) -> str:
    """标准化路径字符串用于比较"""
    return str(Path(path).resolve())


def normalize_dataclass_for_comparison(obj: Any) -> Any:
    """
    将数据类对象转换为可比较的格式，递归处理嵌套结构

    Args:
        obj: 要转换的对象

    Returns:
        转换后的对象，适合用于比较
    """
    if dataclasses.is_dataclass(obj):
        # 将数据类转换为字典
        result = dataclasses.asdict(obj)
        # 递归处理字典中的值
        return {k: normalize_dataclass_for_comparison(v) for k, v in result.items()}
    elif isinstance(obj, dict):
        # 递归处理字典
        return {k: normalize_dataclass_for_comparison(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        # 递归处理列表/元组，并排序以忽略顺序
        items = [normalize_dataclass_for_comparison(item) for item in obj]
        # 只对可排序的项目进行排序
        try:
            return sorted(items, key=lambda x: str(x))
        except (TypeError, KeyError):
            # 如果无法排序，保持原顺序
            return items
    elif isinstance(obj, Path):
        # 标准化路径
        return normalize_path(obj)
    else:
        # 其他类型直接返回
        return obj


def normalize_index_data_for_comparison(data: IndexData) -> Dict[str, Any]:
    """
    将 IndexData 转换为标准化的字典格式用于比较

    Args:
        data: IndexData 对象

    Returns:
        标准化的字典
    """
    # 使用 dataclasses.asdict 转换整个对象
    normalized = normalize_dataclass_for_comparison(data)

    # 对顶层的 data 列表按符号名称和类型排序
    if "data" in normalized and isinstance(normalized["data"], list):
        normalized["data"] = sorted(
            normalized["data"],
            key=lambda e: (
                e.get("symbol", {}).get("name", ""),
                (
                    e.get("symbol", {}).get("__class__", {}).get("__name__", "")
                    if isinstance(e.get("symbol"), dict)
                    else str(type(e.get("symbol", "")).__name__)
                ),
            ),
        )

        # 对每个条目内部的列表也进行排序
        for entry in normalized["data"]:
            if "info" in entry and isinstance(entry["info"], dict):
                info = entry["info"]

                # 排序定义列表
                if "definitions" in info and isinstance(info["definitions"], list):
                    info["definitions"] = sorted(
                        info["definitions"],
                        key=lambda d: (
                            d.get("location", {}).get("file_path", ""),
                            d.get("location", {}).get("start_lineno", 0),
                        ),
                    )

                    # 排序每个定义中的调用列表
                    for defn in info["definitions"]:
                        if "calls" in defn and isinstance(defn["calls"], list):
                            defn["calls"] = sorted(
                                defn["calls"],
                                key=lambda c: (
                                    c.get("symbol", {}).get("name", ""),
                                    str(c.get("symbol", {})),
                                ),
                            )

                # 排序引用列表
                if "references" in info and isinstance(info["references"], list):
                    info["references"] = sorted(
                        info["references"],
                        key=lambda r: (
                            r.get("location", {}).get("file_path", ""),
                            r.get("location", {}).get("start_lineno", 0),
                        ),
                    )

    return normalized


def compare_index_data(data1: IndexData, data2: IndexData) -> Tuple[bool, List[str]]:
    """
    比较两个 IndexData 对象是否在测试意义上相等

    Args:
        data1: 第一个 IndexData 对象
        data2: 第二个 IndexData 对象

    Returns:
        Tuple[bool, List[str]]: (是否相等, 差异列表)
    """
    differences = []

    try:
        normalized1 = normalize_index_data_for_comparison(data1)
        normalized2 = normalize_index_data_for_comparison(data2)

        # 使用递归字典比较
        def compare_values(v1: Any, v2: Any, path: str = "") -> List[str]:
            """递归比较两个值"""
            diffs = []

            # if type(v1) != type(v2):
            #     diffs.append(f"{path}: Type mismatch: {type(v1).__name__} != {type(v2).__name__}")
            #     return diffs
            #
            # if isinstance(v1, dict) and isinstance(v2, dict):
            #     # 比较字典
            #     keys1, keys2 = set(v1.keys()), set(v2.keys())
            #     if keys1 != keys2:
            #         missing_in_v2 = keys1 - keys2
            #         missing_in_v1 = keys2 - keys1
            #         if missing_in_v2:
            #             diffs.append(f"{path}: Missing keys in second object: {missing_in_v2}")
            #         if missing_in_v1:
            #             diffs.append(f"{path}: Extra keys in second object: {missing_in_v1}")
            #
            #     # 比较共同的键
            #     for key in keys1 & keys2:
            #         current_path = f"{path}.{key}" if path else str(key)
            #         diffs.extend(compare_values(v1[key], v2[key], current_path))
            #
            # elif isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
            #     # 比较列表/元组
            #     if len(v1) != len(v2):
            #         diffs.append(f"{path}: List length mismatch: {len(v1)} != {len(v2)}")
            #     else:
            #         for i, (item1, item2) in enumerate(zip(v1, v2)):
            #             diffs.extend(compare_values(item1, item2, f"{path}[{i}]"))
            #
            # elif v1 != v2:
            #     # 直接值比较
            #     diffs.append(f"{path}: {v1!r} != {v2!r}")

            match v1, v2:
                case dict() as d1, dict() as d2:
                    # 比较字典
                    keys1, keys2 = set(d1.keys()), set(d2.keys())
                    if keys1 != keys2:
                        missing_in_v2 = keys1 - keys2
                        missing_in_v1 = keys2 - keys1
                        if missing_in_v2:
                            diffs.append(f"{path}: Missing keys in second object: {missing_in_v2}")
                        if missing_in_v1:
                            diffs.append(f"{path}: Extra keys in second object: {missing_in_v1}")

                    # 比较共同的键
                    for key in keys1 & keys2:
                        current_path = f"{path}.{key}" if path else str(key)
                        diffs.extend(compare_values(d1[key], d2[key], current_path))

                case (list() as l1, list() as l2) | (tuple() as l1, tuple() as l2):
                    # 比较列表/元组
                    if len(l1) != len(l2):
                        diffs.append(f"{path}: List length mismatch: {len(l1)} != {len(l2)}")
                    else:
                        for i, (item1, item2) in enumerate(zip(l1, l2)):
                            diffs.extend(compare_values(item1, item2, f"{path}[{i}]"))

                case _ if type(v1) != type(v2):
                    # 类型不匹配
                    diffs.append(
                        f"{path}: Type mismatch: {type(v1).__name__} != {type(v2).__name__}"
                    )

                case _ if v1 != v2:
                    # 直接值比较
                    diffs.append(f"{path}: {v1!r} != {v2!r}")

            return diffs

        differences = compare_values(normalized1, normalized2)

    except Exception as e:
        differences.append(f"Error during comparison: {e}")

    return len(differences) == 0, differences


def assert_index_data_equal(
    actual: IndexData,
    expected: IndexData,
    msg: str = "IndexData objects are not equal",
) -> None:
    """
    断言两个 IndexData 对象在测试意义上相等

    Args:
        actual: 实际的 IndexData 对象
        expected: 期望的 IndexData 对象
        msg: 断言失败时的消息

    Raises:
        AssertionError: 如果两个对象不相等
    """
    is_equal, differences = compare_index_data(actual, expected)

    if not is_equal:
        error_msg = f"{msg}\n" + "\n".join(f"  - {diff}" for diff in differences)
        raise AssertionError(error_msg)
