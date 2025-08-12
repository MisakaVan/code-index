"""Testing utilities for code indexer data comparison and validation.

This module provides specialized utilities for testing code indexer functionality,
particularly for comparing complex data structures like IndexData objects that
contain nested dataclasses, lists, and Path objects.

The utilities handle normalization of data structures to enable reliable comparison
by sorting lists, normalizing paths, and converting dataclasses to comparable formats
while preserving semantic meaning.

Functions:
    normalize_path: Standardize path strings for comparison.
    normalize_dataclass_for_comparison: Convert dataclass objects to comparable format.
    normalize_index_data_for_comparison: Normalize IndexData for testing comparison.
    compare_index_data: Compare two IndexData objects with detailed diff reporting.
    assert_index_data_equal: Assertion function for IndexData equality testing.
"""

import dataclasses
from pathlib import Path
from typing import Any, Tuple, Union

from pydantic import BaseModel

from ..models import (
    IndexData,
)


def normalize_path(path: Union[Path, str]) -> str:
    """Normalize path strings for reliable cross-platform comparison.

    Converts path objects to resolved absolute path strings to ensure
    consistent comparison regardless of the original path format or
    current working directory.

    Args:
        path: Path object or string to normalize.

    Returns:
        Normalized absolute path string.

    Example:
        >>> normalize_path("./src/../src/main.py")
        "/absolute/path/to/src/main.py"
    """
    return str(Path(path).resolve())


def normalize_dataclass_for_comparison(obj: Any) -> Any:
    """Convert dataclass objects to comparable format with recursive processing.

    This function recursively processes complex data structures containing
    dataclasses, dictionaries, lists, and other types to create a normalized
    representation suitable for equality comparison in tests.

    The normalization process:
        - Converts dataclasses to dictionaries
        - Recursively processes nested structures
        - Sorts lists and tuples when possible (for order-independent comparison)
        - Normalizes Path objects to strings

    Args:
        obj: The object to normalize (can be any type).

    Returns:
        Normalized representation of the object suitable for comparison.

    Example:
        >>> @dataclass
        ... class TestData:
        ...     items: list[str]
        >>> obj = TestData(items=["b", "a"])
        >>> normalized = normalize_dataclass_for_comparison(obj)
        >>> normalized["items"]
        ["a", "b"]  # Sorted for consistent comparison
    """
    if isinstance(obj, BaseModel):
        # Convert Pydantic model to dictionary
        result = obj.model_dump()
        # Recursively process dictionary values
        return {k: normalize_dataclass_for_comparison(v) for k, v in result.items()}
    if dataclasses.is_dataclass(obj):
        # Convert dataclass to dictionary
        # assert it is an instance of dataclass, not a class
        if isinstance(obj, type):
            raise TypeError("Expected an instance of a dataclass, not a class.")
        result = dataclasses.asdict(obj)
        # Recursively process dictionary values
        return {k: normalize_dataclass_for_comparison(v) for k, v in result.items()}
    elif isinstance(obj, dict):
        # Recursively process dictionaries
        return {k: normalize_dataclass_for_comparison(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        # Recursively process lists/tuples and sort for order-independent comparison
        items = [normalize_dataclass_for_comparison(item) for item in obj]
        # Only sort items that are sortable
        try:
            return sorted(items, key=lambda x: str(x))
        except (TypeError, KeyError):
            # If sorting fails, maintain original order
            return items
    elif isinstance(obj, Path):
        # Normalize paths
        return normalize_path(obj)
    else:
        # Return other types unchanged
        return obj


def normalize_index_data_for_comparison(data: IndexData) -> dict[str, Any]:
    """Normalize IndexData objects for reliable test comparison.

    Converts IndexData to a standardized dictionary format with consistent
    ordering of nested structures. This enables reliable equality testing
    by eliminating order dependencies that don't affect semantic meaning.

    The normalization process:
        - Converts the entire IndexData to a dictionary
        - Sorts data entries by symbol name and type
        - Sorts definitions by file path and line number
        - Sorts references by file path and line number
        - Sorts function calls within definitions

    Args:
        data: IndexData object to normalize.

    Returns:
        Normalized dictionary representation suitable for comparison.

    Example:
        >>> index_data = IndexData(type="simple", data=[...])
        >>> normalized = normalize_index_data_for_comparison(index_data)
        >>> # All nested lists are now consistently sorted
    """
    # Convert entire object using dataclasses.asdict
    normalized = normalize_dataclass_for_comparison(data)

    # Sort top-level data list by symbol name and type
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

        # Sort lists within each entry
        for entry in normalized["data"]:
            if "info" in entry and isinstance(entry["info"], dict):
                info = entry["info"]

                # Sort definitions list
                if "definitions" in info and isinstance(info["definitions"], list):
                    info["definitions"] = sorted(
                        info["definitions"],
                        key=lambda d: (
                            d.get("location", {}).get("file_path", ""),
                            d.get("location", {}).get("start_lineno", 0),
                        ),
                    )

                    # Sort calls list within each definition
                    for defn in info["definitions"]:
                        if "calls" in defn and isinstance(defn["calls"], list):
                            defn["calls"] = sorted(
                                defn["calls"],
                                key=lambda c: (
                                    c.get("symbol", {}).get("name", ""),
                                    str(c.get("symbol", {})),
                                ),
                            )

                # Sort references list
                if "references" in info and isinstance(info["references"], list):
                    info["references"] = sorted(
                        info["references"],
                        key=lambda r: (
                            r.get("location", {}).get("file_path", ""),
                            r.get("location", {}).get("start_lineno", 0),
                        ),
                    )

    return normalized


def compare_index_data(data1: IndexData, data2: IndexData) -> Tuple[bool, list[str]]:
    """Compare two IndexData objects for test equality with detailed difference reporting.

    Performs a deep comparison of two IndexData objects after normalization,
    providing detailed information about any differences found. This is useful
    for debugging test failures and understanding how data structures differ.

    Args:
        data1: First IndexData object to compare.
        data2: Second IndexData object to compare.

    Returns:
        A tuple containing:
            - bool: True if objects are equal, False otherwise
            - list[str]: List of difference descriptions (empty if equal)

    Example:
        >>> data1 = IndexData(...)
        >>> data2 = IndexData(...)
        >>> is_equal, differences = compare_index_data(data1, data2)
        >>> if not is_equal:
        ...     for diff in differences:
        ...         print(f"Difference: {diff}")
    """
    differences = []

    try:
        normalized1 = normalize_index_data_for_comparison(data1)
        normalized2 = normalize_index_data_for_comparison(data2)

        # Recursive value comparison with detailed difference tracking
        def compare_values(v1: Any, v2: Any, path: str = "") -> list[str]:
            """Recursively compare two values and track differences.

            Args:
                v1: First value to compare.
                v2: Second value to compare.
                path: Current path in the data structure (for error reporting).

            Returns:
                List of difference descriptions.
            """
            diffs = []

            match v1, v2:
                case dict() as d1, dict() as d2:
                    # Compare dictionaries
                    keys1, keys2 = set(d1.keys()), set(d2.keys())
                    if keys1 != keys2:
                        missing_in_v2 = keys1 - keys2
                        missing_in_v1 = keys2 - keys1
                        if missing_in_v2:
                            diffs.append(f"{path}: Missing keys in second object: {missing_in_v2}")
                        if missing_in_v1:
                            diffs.append(f"{path}: Extra keys in second object: {missing_in_v1}")

                    # Compare common keys
                    for key in keys1 & keys2:
                        current_path = f"{path}.{key}" if path else str(key)
                        diffs.extend(compare_values(d1[key], d2[key], current_path))

                case (list() as l1, list() as l2) | (tuple() as l1, tuple() as l2):
                    # Compare lists/tuples
                    if len(l1) != len(l2):
                        diffs.append(f"{path}: List length mismatch: {len(l1)} != {len(l2)}")
                    else:
                        for i, (item1, item2) in enumerate(zip(l1, l2)):
                            diffs.extend(compare_values(item1, item2, f"{path}[{i}]"))

                case _ if type(v1) is not type(v2):
                    # Type mismatch
                    diffs.append(
                        f"{path}: Type mismatch: {type(v1).__name__} != {type(v2).__name__}"
                    )

                case _ if v1 != v2:
                    # Direct value comparison
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
    """Assert that two IndexData objects are equal in testing context.

    This function provides a detailed assertion for IndexData equality,
    showing specific differences when the assertion fails. It's designed
    to be used in unit tests where detailed failure information is needed.

    Args:
        actual: The actual IndexData object (from test execution).
        expected: The expected IndexData object (reference/baseline).
        msg: Custom message to include in assertion failure.

    Raises:
        AssertionError: If the objects are not equal, with detailed difference
                       information in the error message.

    Example:
        >>> def test_indexing():
        ...     actual_data = index_some_code()
        ...     expected_data = load_expected_data()
        ...     assert_index_data_equal(
        ...         actual_data, expected_data, "Code indexing produced unexpected results"
        ...     )
    """
    is_equal, differences = compare_index_data(actual, expected)

    if not is_equal:
        error_msg = f"{msg}\n" + "\n".join(f"  - {diff}" for diff in differences)
        raise AssertionError(error_msg)
