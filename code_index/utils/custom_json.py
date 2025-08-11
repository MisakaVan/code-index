"""Custom JSON serialization utilities for code indexer data structures.

This module provides enhanced JSON encoding and decoding capabilities for handling
complex data structures used in the code indexer, including dataclasses, Path objects,
and custom type registration for serialization.

The module supports:
    - Automatic dataclass serialization/deserialization
    - Path object handling (automatic conversion to/from strings)
    - Type registration system for custom classes
    - Strict/non-strict deserialization modes

Classes:
    EnhancedJSONEncoder: Custom JSON encoder for handling non-standard types.

Functions:
    register_json_type: Decorator for registering dataclasses for JSON serialization.
    custom_json_decoder: Custom JSON decoder for reconstructing objects.
    dump_index_to_json: Utility function for saving index data to JSON files.
    load_index_from_json: Utility function for loading index data from JSON files.
"""

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, Type, TypeVar

from .logger import logger


class EnhancedJSONEncoder(json.JSONEncoder):
    """Enhanced JSON encoder for handling non-standard Python types.

    This encoder extends the standard JSONEncoder to automatically handle:
        - pathlib.Path objects (converted to strings)
        - dataclass objects (converted to dictionaries with type information)

    The encoder preserves type information by adding a special "__class__" field
    to serialized dataclass objects, enabling proper reconstruction during
    deserialization.
    """

    def default(self, o):
        """Serialize objects that are not natively JSON serializable.

        Args:
            o: The object to serialize.

        Returns:
            A JSON-serializable representation of the object.

        Raises:
            TypeError: If the object type is not supported by this encoder.
        """
        # Convert Path objects to strings
        if isinstance(o, Path):
            return str(o)

        # Convert dataclass objects to dictionaries with type information
        if is_dataclass(o):
            # Use manual field extraction to avoid recursion issues
            dict_data = {f.name: getattr(o, f.name) for f in fields(o)}
            dict_data["__class__"] = o.__class__.__name__  # Add type info for deserialization
            return dict_data

        # Fall back to default encoder for all other types
        return super().default(o)


T = TypeVar("T")

JSON_TYPE_REGISTRY: dict[str, Type[Any]] = {}
"""Global registry mapping class names to their types for JSON deserialization.

This dictionary is automatically populated when classes are decorated with
@register_json_type and is used by custom_json_decoder to reconstruct
the correct object types during JSON deserialization.

The registry maps class names (strings) to their corresponding type objects,
enabling the decoder to instantiate the proper classes when encountering
serialized dataclass objects in JSON data.
"""


def register_json_type(cls: Type[T]) -> Type[T]:
    """Register a dataclass type for JSON serialization support.

    This decorator registers a dataclass in the global type registry, enabling
    automatic serialization and deserialization through the custom JSON utilities.
    Only dataclasses can be registered.

    Args:
        cls: The dataclass type to register. Must be a dataclass.

    Returns:
        The same class (unmodified), allowing use as a decorator.

    Raises:
        ValueError: If the provided class is not a dataclass.

    Example:
        >>> @register_json_type
        ... @dataclass
        ... class MyData:
        ...     value: int

        >>> # MyData is now registered and can be serialized/deserialized
    """
    if not is_dataclass(cls):
        logger.warning(
            f"Attempted to register {cls.__name__} which is not a dataclass. Skipping registration."
        )
    JSON_TYPE_REGISTRY[cls.__name__] = cls
    return cls


def custom_json_decoder(dct: Dict, strict=False) -> object:
    """Custom JSON decoder for reconstructing objects from dictionaries.

    This decoder handles the reconstruction of registered dataclass objects
    and automatic Path object conversion during JSON deserialization.

    Args:
        dct: Dictionary containing serialized object data.
        strict: If True, raises exceptions when encountering unregistered classes.
            If False, returns the dictionary unchanged for unregistered types.

    Returns:
        The reconstructed object if type information is available and registered,
        otherwise the original dictionary.

    Raises:
        ValueError: If strict=True and an unregistered class is encountered.

    Example:
        >>> data = {"value": 42, "__class__": "MyData"}
        >>> obj = custom_json_decoder(data)
        >>> isinstance(obj, MyData)
        True
    """
    # Handle Path objects stored as strings
    if "file_path" in dct and isinstance(dct["file_path"], str):
        dct["file_path"] = Path(dct["file_path"])

    # Handle registered dataclass objects
    if "__class__" in dct:
        class_name = dct.pop("__class__")
        cls = JSON_TYPE_REGISTRY.get(class_name)
        if cls is None:
            if strict:
                raise ValueError(f"Class {class_name} not registered in JSON_TYPE_REGISTRY.")
        elif is_dataclass(cls):
            # Convert string paths to Path objects for fields typed as Path
            for field_info in fields(cls):
                field_name = field_info.name
                if (
                    field_name in dct
                    and isinstance(dct[field_name], str)
                    and field_info.type == Path
                ):
                    dct[field_name] = Path(dct[field_name])
            # noinspection PyArgumentList
            return cls(**dct)
    return dct  # Return original dictionary if no matching class found


def dump_index_to_json(index: dict, output_path: Path):
    """Save index data to a JSON file with enhanced encoding.

    This function serializes index data to JSON format using the EnhancedJSONEncoder
    to handle complex data types like dataclasses and Path objects.

    Args:
        index: The index data dictionary to serialize.
        output_path: Path where the JSON file should be written.

    Raises:
        IOError: If the file cannot be written due to permissions or disk issues.

    Example:
        >>> index_data = {"functions": [some_function_data]}
        >>> dump_index_to_json(index_data, Path("index.json"))
    """
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False, cls=EnhancedJSONEncoder)


def load_index_from_json(input_path: Path, strict=False):
    """Load index data from a JSON file with custom decoding.

    This function deserializes index data from JSON format using the custom
    decoder to reconstruct dataclass objects and handle Path conversion.

    Args:
        input_path: Path to the JSON file to load.
        strict: If True, raises exceptions for unregistered classes during
            deserialization. If False, leaves unregistered objects as
            dictionaries.

    Returns:
        The deserialized index data with proper object types reconstructed.

    Raises:
        IOError: If the file cannot be read.
        ValueError: If strict=True and unregistered classes are encountered.
        json.JSONDecodeError: If the file contains invalid JSON.

    Example:
        >>> data = load_index_from_json(Path("index.json"))
        >>> # Returns properly typed objects based on registry
    """
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f, object_hook=lambda dct: custom_json_decoder(dct, strict))
    return data
