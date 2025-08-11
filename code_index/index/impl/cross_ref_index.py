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
    SymbolDefinition,
    SymbolReference,
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


class ReferenceDict(dict[PureReference, Reference]):
    """A specialized dictionary that maintains the invariant: key == value.to_pure().

    When accessing a key that doesn't exist, it creates a new Reference with that
    PureReference as its location and stores it.
    """

    def __getitem__(self, key: PureReference) -> Reference:
        if key not in self:
            # Create a new Reference with the pure key as its fingerprint
            new_reference = Reference(location=key.location)
            self[key] = new_reference
        return super().__getitem__(key)

    def __setitem__(self, key: PureReference, value: Reference) -> None:
        # Ensure invariant: key == value.to_pure()
        if key != value.to_pure():
            raise ValueError(f"Key {key} does not match value.to_pure() {value.to_pure()}")
        super().__setitem__(key, value)

    def merge_or_insert(self, value: Reference) -> None:
        """Merges a Reference into the dictionary or inserts it if not present.

        If the pure key doesn't exist, creates a new entry.
        If it exists, merges the information (extends the called_by list in-place).

        Args:
            value: The Reference to merge or insert.
        """
        key = value.to_pure()
        existing = self[key]  # This will create if not present due to our __getitem__

        existing.merge(value)


class DefinitionDict(dict[PureDefinition, Definition]):
    """A specialized dictionary that maintains the invariant: key == value.to_pure().

    When accessing a key that doesn't exist, it creates a new Definition with that
    PureDefinition as its location and stores it.
    """

    def __getitem__(self, key: PureDefinition) -> Definition:
        if key not in self:
            # Create a new Definition with the pure key as its fingerprint
            new_definition = Definition(location=key.location)
            self[key] = new_definition
        return super().__getitem__(key)

    def __setitem__(self, key: PureDefinition, value: Definition) -> None:
        # Ensure invariant: key == value.to_pure()
        if key != value.to_pure():
            raise ValueError(f"Key {key} does not match value.to_pure() {value.to_pure()}")
        super().__setitem__(key, value)

    def merge_or_insert(self, value: Definition) -> None:
        """Merges a Definition into the dictionary or inserts it if not present.

        If the pure key doesn't exist, creates a new entry.
        If it exists, merges the information (extends the calls list in-place).

        Args:
            value: The Definition to merge or insert.
        """
        key = value.to_pure()
        existing = self[key]  # This will create if not present due to our __getitem__

        existing.merge(value)


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

        definitions: DefinitionDict = field(default_factory=DefinitionDict)
        """A dictionary mapping PureDefinition to Definition.

        Invariant: forall k, v in definitions: k = v.to_pure()
        """
        references: ReferenceDict = field(default_factory=ReferenceDict)
        """A dictionary mapping PureReference to Reference.

        Invariant: forall k, v in references: k = v.to_pure()
        """

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
                key = definition.to_pure()
                info.definitions[key] = definition
            for reference in func_like_info.references:
                key = reference.to_pure()
                info.references[key] = reference
            return info

        def update_from(self, other: CrossRefIndex.Info | FunctionLikeInfo):
            """Updates this Info object with data from another Info or FunctionLikeInfo.

            Uses merge_or_insert to properly merge information when the same pure keys exist.
            """
            if isinstance(other, FunctionLikeInfo):
                other = CrossRefIndex.Info.from_function_like_info(other)
            assert isinstance(other, CrossRefIndex.Info)

            # Use merge_or_insert to properly merge references and definitions
            for reference in other.references.values():
                self.references.merge_or_insert(reference)

            for definition in other.definitions.values():
                self.definitions.merge_or_insert(definition)

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
        """Adds a function or method definition to the index with cross-referencing.

        This method not only stores the definition but also establishes bidirectional
        cross-references. For each function call within this definition, it ensures
        that the called function's references list includes this definition as a caller.

        Example:
            Given a definition of function `foo` that calls functions `bar` and `baz`:

            .. code-block:: python

                # Definition of foo() that calls bar() and baz()
                foo_definition = Definition(
                    location=CodeLocation(...),  # where foo is defined
                    calls=[
                        SymbolReference(symbol=Function(name="bar"), reference=PureReference(...)),
                        SymbolReference(symbol=Function(name="baz"), reference=PureReference(...)),
                    ],
                )

                # Adding this definition will:
                # 1. Store foo's definition in self.data[foo].definitions
                # 2. Add foo to bar's called_by list: self.data[bar].references[...].called_by
                # 3. Add foo to baz's called_by list: self.data[baz].references[...].called_by
                index.add_definition(Function(name="foo"), foo_definition)

        Args:
            func_like: The function or method information.
            definition: The definition details including location and context.
        """
        # First, add the definition using merge_or_insert to conform to the invariant
        self.data[func_like].definitions.merge_or_insert(definition)

        # Now do cross-referencing: for each call this definition makes,
        # ensure this definition is in the called_by list of that reference
        for symbol_reference in definition.calls:
            called_func_like = symbol_reference.symbol
            pure_reference = symbol_reference.reference

            # Get or create the reference in the called function's references
            target_reference = self.data[called_func_like].references[pure_reference]

            # Create a SymbolDefinition for this definition to add to called_by
            symbol_definition = SymbolDefinition(symbol=func_like, definition=definition.to_pure())

            # Add this definition to the called_by list if not already present
            if symbol_definition not in target_reference.called_by:
                target_reference.called_by.append(symbol_definition)

    def add_reference(self, func_like: FunctionLike, reference: Reference):
        """Adds a function or method reference to the index with cross-referencing.

        This method not only stores the reference but also establishes bidirectional
        cross-references. For each caller in the reference's called_by list, it ensures
        that the caller's definition includes this reference in its calls list.

        Example:
            Given a reference to function `bar` that is called by functions `foo` and `main`:

            .. code-block:: python

                # Reference to bar() that is called by foo() and main()
                bar_reference = Reference(
                    location=CodeLocation(...),  # where bar is called
                    called_by=[
                        SymbolDefinition(
                            symbol=Function(name="foo"), definition=PureDefinition(...)
                        ),
                        SymbolDefinition(
                            symbol=Function(name="main"), definition=PureDefinition(...)
                        ),
                    ],
                )

                # Adding this reference will:
                # 1. Store bar's reference in self.data[bar].references
                # 2. Add bar to foo's calls list: self.data[foo].definitions[...].calls
                # 3. Add bar to main's calls list: self.data[main].definitions[...].calls
                index.add_reference(Function(name="bar"), bar_reference)

        Args:
            func_like: The function or method information.
            reference: The reference details including location and context.
        """
        # First, add the reference using merge_or_insert to conform to the invariant
        self.data[func_like].references.merge_or_insert(reference)

        # Now do cross-referencing: for each caller in the called_by list,
        # ensure this reference is in the calls list of that definition
        for symbol_definition in reference.called_by:
            caller_func_like = symbol_definition.symbol
            pure_definition = symbol_definition.definition

            # Get or create the definition in the caller function's definitions
            caller_definition = self.data[caller_func_like].definitions[pure_definition]

            # Create a SymbolReference for this reference to add to calls
            symbol_reference = SymbolReference(symbol=func_like, reference=reference.to_pure())

            # Add this reference to the calls list if not already present
            if symbol_reference not in caller_definition.calls:
                caller_definition.calls.append(symbol_reference)

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
