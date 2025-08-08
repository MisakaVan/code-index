from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Iterable, Iterator

from .code_query import CodeQuery, CodeQuerySingleResponse
from ..models import (
    Definition,
    Reference,
    FunctionLikeInfo,
    FunctionLike,
    IndexData,
)


class PersistStrategy(ABC):
    """Abstract base class for persistence strategies.

    Defines the interface for saving and loading index data to/from persistent
    storage. Implementations can support various formats like JSON, SQLite, etc.
    """

    def __init__(self):
        """Initialize the persist strategy."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        """Returns a string representation of the persist strategy.

        Returns:
            A compact summary of the strategy configuration.
        """
        return f"{self.__class__.__name__}()"

    @abstractmethod
    def save(self, data: IndexData, path: Path):
        """Saves index data to the specified path.

        Args:
            data: The index data to save.
            path: The file path where data will be saved.
        """
        pass

    @abstractmethod
    def load(self, path: Path) -> IndexData:
        """Loads index data from the specified path.

        Args:
            path: The file path from which to load data.

        Returns:
            The loaded index data.
        """
        pass


class BaseIndex(ABC):
    """Abstract base class for code symbol indexes.

    Encapsulates CRUD operations and storage for a codebase index containing
    function and method definitions and references. Provides a unified interface
    for different index implementations.
    """

    def __init__(self):
        pass

    def __str__(self) -> str:
        """Returns a string representation of the index.

        Returns:
            A compact summary of the index contents.
        """
        return f"{self.__class__.__name__}({len(self)} items)"

    @abstractmethod
    def __repr__(self) -> str:
        pass

    @abstractmethod
    def add_definition(self, func_like: FunctionLike, definition: Definition):
        """Adds a function or method definition to the index.

        Args:
            func_like: The function or method information.
            definition: The definition details including location and context.
        """
        pass

    @abstractmethod
    def add_reference(self, func_like: FunctionLike, reference: Reference):
        """Adds a function or method reference to the index.

        Args:
            func_like: The function or method information.
            reference: The reference details including location and context.
        """
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Returns the number of function-like items in the index.

        Returns:
            The count of indexed functions and methods.
        """
        pass

    @abstractmethod
    def __getitem__(self, func_like: FunctionLike) -> FunctionLikeInfo:
        """Gets function information from the index.

        Args:
            func_like: The function or method to retrieve.

        Returns:
            The function information if found.

        Raises:
            KeyError: If the function is not found in the index.
        """
        pass

    @abstractmethod
    def __setitem__(self, func_like: FunctionLike, info: FunctionLikeInfo):
        """Sets function information in the index.

        Args:
            func_like: The function or method key.
            info: The function information to store.
        """
        pass

    @abstractmethod
    def __delitem__(self, func_like: FunctionLike):
        """Deletes function information from the index.

        Args:
            func_like: The function or method to remove.
        """
        pass

    @abstractmethod
    def __contains__(self, func_like: FunctionLike) -> bool:
        """Checks if function exists in the index.

        Args:
            func_like: The function or method to check.

        Returns:
            True if the function exists in the index, False otherwise.
        """
        pass

    @abstractmethod
    def __iter__(self) -> Iterator[FunctionLike]:
        """Iterates over all functions in the index.

        Returns:
            An iterator of FunctionLike objects.
        """
        pass

    @abstractmethod
    def update(self, mapping: Dict[FunctionLike, FunctionLikeInfo]):
        """Updates the index with multiple function entries.

        Args:
            mapping: A dictionary mapping functions to their information.
        """
        pass

    @abstractmethod
    def items(self) -> Iterable[tuple[FunctionLike, FunctionLikeInfo]]:
        """Gets all items in the index as key-value pairs.

        Returns:
            An iterable of (FunctionLike, FunctionLikeInfo) tuples.
        """
        pass

    @abstractmethod
    def get_info(self, func_like: FunctionLike) -> FunctionLikeInfo | None:
        """Gets function information from the index.

        Args:
            func_like: The function or method to retrieve.

        Returns:
            The function information if found, None otherwise.
        """
        pass

    @abstractmethod
    def get_definitions(self, func_like: FunctionLike) -> Iterable[Definition]:
        """Gets all definitions for a function from the index.

        Args:
            func_like: The function or method to retrieve definitions for.

        Returns:
            An iterable of Definition objects.
        """
        pass

    @abstractmethod
    def get_references(self, func_like: FunctionLike) -> Iterable[Reference]:
        """Gets all references for a function from the index.

        Args:
            func_like: The function or method to retrieve references for.

        Returns:
            An iterable of Reference objects.
        """
        pass

    @abstractmethod
    def as_data(self) -> IndexData:
        """Converts the index to a serializable data format.

        Returns:
            A dictionary representation of the index data.
        """
        pass

    @abstractmethod
    def update_from_data(self, data: IndexData):
        """Updates the index with data from a serialized format.

        Args:
            data: A dictionary containing function information to load.
        """
        pass

    def persist_to(self, path: Path, save_strategy: PersistStrategy):
        """Persists the index data to a file.

        Args:
            path: The file path to save the index data.
            save_strategy: The persistence strategy to use for saving.
        """
        save_strategy.save(self.as_data(), path)

    @classmethod
    def load_from(cls, path: Path, load_strategy: PersistStrategy) -> "BaseIndex":
        """Loads index data from a file and creates a new index instance.

        Args:
            path: The file path to load the index data from.
            load_strategy: The persistence strategy to use for loading.

        Returns:
            A new BaseIndex instance with the loaded data.
        """
        loaded_data = load_strategy.load(path)
        index = cls()
        index.update_from_data(loaded_data)
        return index

    @abstractmethod
    def handle_query(self, query: CodeQuery) -> list[CodeQuerySingleResponse]:
        """Handles a query against the index.

        Args:
            query: The query to execute against the index.

        Returns:
            An iterable of CodeQuerySingleResponse containing query results.
        """
        pass
