from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator
from abc import ABC, abstractmethod

from ..models import (
    CodeLocation,
    Definition,
    Reference,
    FunctionLikeInfo,
    FunctionLike,
    Function,
    Method,
)


class PersistStrategy(ABC):
    """
    Abstract base class for save and load strategies.
    Defines the interface for saving index data.
    """

    @abstractmethod
    def save(self, data: dict, path: Path):
        """
        Save the index data to a specified path.

        :param data: The index data to save, typically a dictionary.
        :param path: The path where the index data will be saved.
        """
        pass

    @abstractmethod
    def load(self, path: Path) -> dict:
        """
        Load the index data from a specified path.

        :param path: The path from which to load the index data.
        :return: The loaded index data, typically a dictionary.
        """
        pass


class BaseIndex(ABC):
    """
    Encapsulates CRUD operations, as well as holds
    the index data for a codebase index.
    """

    def __init__(self):
        pass

    @abstractmethod
    def __repr__(self) -> str:
        pass

    @abstractmethod
    def add_definition(self, func_like: FunctionLike, definition: Definition):
        """
        Add a function-like definition to the index.

        :param func_like: The function-like information (Function or Method).
        :param definition: The definition details.
        """
        pass

    @abstractmethod
    def add_reference(self, func_like: FunctionLike, reference: Reference):
        """
        Add a function-like reference to the index.

        :param func_like: The function-like information (Function or Method).
        :param reference: The reference details.
        """
        pass

    @abstractmethod
    def __getitem__(self, func_like: FunctionLike) -> FunctionLikeInfo:
        """
        Get the function-like information from the index.

        :param func_like: The function-like information (Function or Method).
        :return: FunctionLikeInfo if found, otherwise raises KeyError.
        """
        pass

    @abstractmethod
    def __setitem__(self, func_like: FunctionLike, info: FunctionLikeInfo):
        """
        Set the function-like information in the index.

        :param func_like: The function-like information (Function or Method).
        :param info: The FunctionLikeInfo to set.
        """
        pass

    @abstractmethod
    def __delitem__(self, func_like: FunctionLike):
        """
        Delete the function-like information from the index.

        :param func_like: The function-like information (Function or Method).
        """
        pass

    @abstractmethod
    def __contains__(self, func_like: FunctionLike) -> bool:
        """
        Check if the function-like information exists in the index.

        :param func_like: The function-like information (Function or Method).
        :return: True if exists, otherwise False.
        """
        pass

    @abstractmethod
    def __iter__(self) -> Iterator[FunctionLike]:
        """
        Iterate over all function-like information in the index.

        :return: An iterable of FunctionLike objects.
        """
        pass

    @abstractmethod
    def update(self, mapping: Dict[FunctionLike, FunctionLikeInfo]):
        """
        Update the index with a mapping of function-like information.

        :param mapping: A dictionary mapping FunctionLike to FunctionLikeInfo.
        """
        pass

    @abstractmethod
    def items(self) -> Iterable[tuple[FunctionLike, FunctionLikeInfo]]:
        """
        Get all items in the index as (FunctionLike, FunctionLikeInfo) pairs.

        :return: An iterable of tuples containing FunctionLike and FunctionLikeInfo.
        """
        pass

    @abstractmethod
    def get_info(self, func_like: FunctionLike) -> FunctionLikeInfo | None:
        """
        Get the function-like information from the index.

        :param func_like: The function-like information (Function or Method).
        :return: FunctionLikeInfo if found, otherwise None.
        """
        pass

    @abstractmethod
    def get_definitions(self, func_like: FunctionLike) -> Iterable[Definition]:
        """
        Get all definitions for a function-like from the index.

        :param func_like: The function-like information (Function or Method).
        :return: An iterable of Definition objects.
        """
        pass

    @abstractmethod
    def get_references(self, func_like: FunctionLike) -> Iterable[Reference]:
        """
        Get all references for a function-like from the index.

        :param func_like: The function-like information (Function or Method).
        :return: An iterable of Reference objects.
        """
        pass

    @abstractmethod
    def as_data(self) -> dict:
        """
        Convert the index data to a dictionary format.

        :return: A dictionary representation of the index data.
        """
        pass

    @abstractmethod
    def update_from_data(self, data: dict):
        """
        Update the index with data from a dictionary.

        :param data: A dictionary containing function-like information.
        """
        pass

    def persist_to(self, path: Path, save_strategy: PersistStrategy):
        """
        Persist the index data to a path.

        :param path: The path to persist the index data.
        :param save_strategy: The strategy to use for saving the index data.
        """
        save_strategy.save(self.as_data(), path)

    @classmethod
    def load_from(cls, path: Path, load_strategy: PersistStrategy) -> "BaseIndex":
        """
        Load the index data from a path.

        :param path: The path to load the index data from.
        :param load_strategy: The strategy to use for loading the index data.
        """
        loaded_data = load_strategy.load(path)
        index = cls()
        index.update_from_data(loaded_data)
        return index
