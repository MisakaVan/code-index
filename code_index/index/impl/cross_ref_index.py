from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Iterator, TypeAlias

from ...models import (
    Definition,
    Function,
    FunctionLike,
    FunctionLikeInfo,
    IndexData,
    IndexDataEntry,
    Method,
    PureDefinition,
    PureReference,
    Reference,
)
from ...utils.logger import logger
from ..base import BaseIndex
from ..code_query import (
    CodeQuery,
    CodeQuerySingleResponse,
    FilterOption,
    QueryByKey,
    QueryByName,
    QueryByNameRegex,
)


class CrossRefIndex(BaseIndex):
    """A cross-reference index implementation of the BaseIndex.

    This index focuses on storing and retrieving cross-references between
    function/method definitions and their references. It is designed to efficiently
    handle queries related to where functions/methods are defined and where they
    are referenced in the codebase.
    """

    ReferenceDict: TypeAlias = dict[PureReference, Reference]
    """The keys are PureReference objects which provide a unique identifier for each reference."""
    DefinitionDict: TypeAlias = dict[PureDefinition, Definition]
    """The keys are PureDefinition objects which provide a unique identifier for each definition."""

    @dataclass
    class Info:
        """Contains information about a function or method.

        This class manages both definitions and references with hashmaps for fast lookups.
        """

        definitions: CrossRefIndex.DefinitionDict = field(default_factory=defaultdict)
        references: CrossRefIndex.ReferenceDict = field(default_factory=defaultdict)

        def to_function_like_info(self) -> FunctionLikeInfo:
            """Converts this Info object to a FunctionLikeInfo object."""
            return FunctionLikeInfo(
                definitions=list(self.definitions.values()),
                references=list(self.references.values()),
            )

        @classmethod
        def from_function_like_info(cls, func_like_info: FunctionLikeInfo) -> CrossRefIndex.Info:
            """Creates an Info object from a FunctionLikeInfo object."""
            info = cls()
            for definition in func_like_info.definitions:
                key = PureDefinition(**definition.model_dump())
                info.definitions[key] = definition
            for reference in func_like_info.references:
                key = PureReference(**reference.model_dump())
                info.references[key] = reference
            return info

        def update_from(self, other: CrossRefIndex.Info | FunctionLikeInfo):
            """Updates this Info object with data from another Info or FunctionLikeInfo."""
            if isinstance(other, FunctionLikeInfo):
                other = CrossRefIndex.Info.from_function_like_info(other)
            assert isinstance(other, CrossRefIndex.Info)
            self.references.update(other.references)
            self.definitions.update(other.definitions)

        def __str__(self) -> str:
            return (
                f"Info(count_def={len(self.definitions):>3}, count_ref={len(self.references):>3})"
            )

    Index: TypeAlias = dict[FunctionLike, Info]

    def __init__(self):
        """Initializes an empty CrossRefIndex."""
        super().__init__()
        self.data: CrossRefIndex.Index = defaultdict(lambda: CrossRefIndex.Info())
        """Internal dictionary storing function/method information.

        The keys are FunctionLike objects (Function, Method).
        The values are Info objects containing definitions and references.

        Each Info object contains:
            - definitions: A dictionary mapping PureDefinition to Definition.
            - references: A dictionary mapping PureReference to Reference.

            These dictionaries enable fast lookups and efficient storage of
            definitions and references at given locations in the codebase.
        """

    def __str__(self) -> str:
        return super().__str__()

    def __repr__(self) -> str:
        """Returns a detailed string representation of the index."""
        return f"CrossRefIndex(items={len(self.data)}, total_definitions={sum(len(info.definitions) for info in self.data.values())}, total_references={sum(len(info.references) for info in self.data.values())})"

    def add_definition(self, func_like: FunctionLike, definition: Definition):
        """Adds a function or method definition to the index.

        Args:
            func_like: The function or method information.
            definition: The definition details including location and context.
        """
        key = PureDefinition(**definition.model_dump())
        self.data[func_like].definitions[key] = definition

    def add_reference(self, func_like: FunctionLike, reference: Reference):
        """Adds a function or method reference to the index.

        Args:
            func_like: The function or method information.
            reference: The reference details including location and context.
        """
        key = PureReference(**reference.model_dump())
        self.data[func_like].references[key] = reference

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, func_like: FunctionLike) -> FunctionLikeInfo:
        if func_like not in self.data:
            raise KeyError(f"{func_like} not found in index.")
        return self.data[func_like].to_function_like_info()

    def __setitem__(self, func_like: FunctionLike, info: FunctionLikeInfo):
        self.data[func_like] = CrossRefIndex.Info.from_function_like_info(info)

    def __delitem__(self, func_like: FunctionLike):
        self.data.pop(func_like)

    def __contains__(self, func_like: FunctionLike) -> bool:
        return func_like in self.data

    def __iter__(self) -> Iterator[FunctionLike]:
        return iter(self.data)

    def update(self, mapping: dict[FunctionLike, FunctionLikeInfo]):
        """Updates the index with a mapping of FunctionLike to FunctionLikeInfo."""
        for func_like, info in mapping.items():
            self.data[func_like].update_from(info)
        return self

    def items(self) -> Iterable[tuple[FunctionLike, FunctionLikeInfo]]:
        """Gets all items in the index as key-value pairs."""
        return ((func_like, info.to_function_like_info()) for func_like, info in self.data.items())

    def get_info(self, func_like: FunctionLike) -> FunctionLikeInfo | None:
        """Gets function information from the index."""
        if func_like in self.data:
            return self.data[func_like].to_function_like_info()
        return None

    def get_definitions(self, func_like: FunctionLike) -> Iterable[Definition]:
        """Gets all definitions for a function from the index."""
        info = self.get_info(func_like)
        if info:
            return info.definitions
        return []

    def get_references(self, func_like: FunctionLike) -> Iterable[Reference]:
        """Gets all references for a function from the index."""
        info = self.get_info(func_like)
        if info:
            return info.references
        return []

    def as_data(self) -> IndexData:
        """Converts the index data to a serializable IndexData object."""
        entries = [
            IndexDataEntry(
                symbol=func_like,
                info=info.to_function_like_info(),
            )
            for func_like, info in self.data.items()
        ]
        return IndexData(type="cross_ref_index", data=entries, metadata=None)

    def update_from_data(self, data: IndexData):
        """Updates the index from a serialized IndexData object."""
        if data.type != "cross_ref_index":
            logger.warning(f"loading data with type {data.type} into CrossRefIndex")
        for entry in data.data:
            self[entry.symbol] = entry.info
        return self

    @staticmethod
    def _type_filterer(func_like: FunctionLike, filter_option: FilterOption) -> bool:
        """Filters function-like objects based on type criteria.

        Args:
            func_like: The function or method to filter.
            filter_option: The filter criteria to apply.

        Returns:
            True if the function matches the filter criteria, False otherwise.
        """
        match filter_option, func_like:
            case FilterOption.ALL, _:
                return True
            case FilterOption.FUNCTION, Function():
                return True
            case FilterOption.METHOD, Method():
                return True
            case _:
                return False

    def handle_query(self, query: CodeQuery) -> list[CodeQuerySingleResponse]:
        """Handles different types of code queries and returns matching results.

        Args:
            query: The query to process (QueryByKey, QueryByName, or QueryByNameRegex).

        Returns:
            List of matching symbols with their information.

        Raises:
            ValueError: If the query type is unsupported or regex pattern is invalid.
        """
        match query:
            case QueryByKey(func_like=func_like):
                if func_like in self.data:
                    info = self.data[func_like].to_function_like_info()
                    return [CodeQuerySingleResponse(func_like=func_like, info=info)]
                return []

            case QueryByName(name=name, type_filter=filter_option):
                func_likes = filter(
                    lambda fl: fl.name == name and self._type_filterer(fl, filter_option),
                    self.data.keys(),
                )
                ret = []
                for func_like in func_likes:
                    info = self.data[func_like].to_function_like_info()
                    ret.append(CodeQuerySingleResponse(func_like=func_like, info=info))
                return ret

            case QueryByNameRegex(name_regex=name_regex, type_filter=filter_option):
                try:
                    pattern = re.compile(name_regex)
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern '{name_regex}': {e}")

                func_likes = filter(
                    lambda fl: pattern.search(fl.name) and self._type_filterer(fl, filter_option),
                    self.data.keys(),
                )
                ret = []
                for func_like in func_likes:
                    info = self.data[func_like].to_function_like_info()
                    ret.append(CodeQuerySingleResponse(func_like=func_like, info=info))
                return ret

        raise ValueError(f"Unsupported query type: {type(query)}")
