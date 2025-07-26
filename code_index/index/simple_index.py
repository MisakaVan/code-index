from pathlib import Path
from collections import defaultdict
from typing import Iterable, Dict, override

from ..models import (
    CodeLocation,
    Definition,
    Reference,
    FunctionLikeInfo,
    FunctionLike,
    Function,
    Method,
)
from .base import BaseIndex, PersistStrategy


class SimpleIndex(BaseIndex):
    """
    Encapsulates CRUD operations for a codebase index.
    """

    def __init__(self):
        super().__init__()
        self.data = defaultdict(lambda: FunctionLikeInfo())

    @override
    def add_definition(self, func_like: FunctionLike, definition: Definition):
        self.data[func_like].definitions.append(definition)

    @override
    def add_reference(self, func_like: FunctionLike, reference: Reference):
        self.data[func_like].references.append(reference)

    @override
    def get_info(self, func_like: FunctionLike) -> FunctionLikeInfo | None:
        # avoid inserting new key if the key is not present
        if func_like in self.data:
            return self.data[func_like]
        return None

    @override
    def get_definitions(self, func_like: FunctionLike) -> Iterable[Definition]:
        info = self.get_info(func_like)
        if info:
            return info.definitions
        return []

    @override
    def get_references(self, func_like: FunctionLike) -> Iterable[Reference]:
        info = self.get_info(func_like)
        if info:
            return info.references
        return []

    @override
    def __getitem__(self, func_like: FunctionLike) -> FunctionLikeInfo:
        result = self.get_info(func_like)
        if result is None:
            raise KeyError(f"{func_like} not found in index.")
        return result

    @override
    def __setitem__(self, func_like: FunctionLike, info: FunctionLikeInfo):
        if not isinstance(info, FunctionLikeInfo):
            raise TypeError("Value must be an instance of FunctionLikeInfo.")
        self.data[func_like] = info

    @override
    def __delitem__(self, func_like: FunctionLike):
        self.data.__delitem__(func_like)

    @override
    def __contains__(self, func_like: FunctionLike) -> bool:
        return func_like in self.data

    @override
    def __iter__(self) -> Iterable[FunctionLike]:
        return iter(self.data.keys())

    @override
    def items(self) -> Iterable[tuple[FunctionLike, FunctionLikeInfo]]:
        return self.data.items()

    @override
    def update(self, mapping: Dict[FunctionLike, FunctionLikeInfo]):
        for func_like, info in mapping.items():
            self[func_like] = info  # may raise KeyError if type is incorrect

    @override
    def as_data(self) -> dict:
        listed_data = []
        for func_like, info in self.items():
            listed_data.append(
                {
                    "symbol": func_like,
                    "info": info,
                }
            )
        return {
            "type": "simple_index",
            "data": listed_data,
        }

    @override
    def update_from_data(self, data: dict):
        if data.get("type") != "simple_index":
            raise ValueError("Invalid data type for SimpleIndex.")
        for item in data.get("data", []):
            symbol = item["symbol"]
            info = item["info"]
            self[symbol] = info
