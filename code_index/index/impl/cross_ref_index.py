from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Iterator, TypeAlias

from ...index.base import BaseIndex
from ...index.code_query import (
    CodeQuery,
    CodeQuerySingleResponse,
    FilterOption,
    QueryByKey,
    QueryByName,
    QueryByNameRegex,
    QueryFullDefinition,
)
from ...models import (
    Definition,
    Function,
    FunctionLikeInfo,
    IndexData,
    IndexDataEntry,
    Method,
    PureDefinition,
    PureReference,
    Reference,
    Symbol,
    SymbolDefinition,
    SymbolReference,
)
from ...utils.logger import logger


class ReferenceDict(dict[PureReference, Reference]):
    """A specialized dictionary that maintains the invariant: key == value.to_pure().

    When accessing a key that doesn't exist, it creates a new Reference with that
    PureReference as its location and stores it.
    """

    def __getitem__(self, key: PureReference) -> Reference:
        if key not in self:
            # Create a new Reference with the pure key as its fingerprint
            new_reference = Reference.from_pure(key)
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
            new_definition = Definition.from_pure(key)
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
                info.definitions[definition.to_pure()] = definition
            for reference in func_like_info.references:
                info.references[reference.to_pure()] = reference
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

    Index: TypeAlias = dict[Symbol, Info]

    def __init__(self) -> None:
        """Initializes an empty CrossRefIndex."""
        super().__init__()
        self.data: CrossRefIndex.Index = defaultdict(lambda: CrossRefIndex.Info())
        # Mapping for fast reverse lookup: PureDefinition -> owning symbol
        self._pure_def_to_symbol: dict[PureDefinition, Symbol] = {}
        # The keys are Symbol objects (Function, Method).
        # The values are Info objects containing definitions and references.
        # Each Info object contains:
        #   - definitions: A dictionary mapping PureDefinition to Definition.
        #   - references: A dictionary mapping PureReference to Reference.
        # These dictionaries enable fast lookups and efficient storage of
        # definitions and references at given locations in the codebase.

    def __str__(self) -> str:
        return super().__str__()

    def __repr__(self) -> str:
        """Returns a detailed string representation of the index."""
        return f"CrossRefIndex(items={len(self.data)}, total_definitions={sum(len(info.definitions) for info in self.data.values())}, total_references={sum(len(info.references) for info in self.data.values())})"

    def add_definition(self, func_like: Symbol, definition: Definition):
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
        # Maintain reverse mapping
        self._pure_def_to_symbol[definition.to_pure()] = func_like

        # Now do cross-referencing: for each call this definition makes,
        # ensure this definition is in the called_by list of that reference
        for callee in definition.calls:
            callee_func_like = callee.symbol
            cross_ref_reference = Reference.from_pure(callee.reference).add_caller(
                SymbolDefinition(
                    symbol=func_like,  # this is the function being defined
                    definition=definition.to_pure(),  # where it is defined
                )
            )
            # this should make the index aware that this function at this def loc calls the callee
            # at the callee's ref loc
            self.data[callee_func_like].references.merge_or_insert(cross_ref_reference)

    def add_reference(self, func_like: Symbol, reference: Reference):
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
        for caller in reference.called_by:
            caller_func_like = caller.symbol
            cross_ref_definition = Definition.from_pure(caller.definition).add_callee(
                SymbolReference(
                    symbol=func_like,  # this is the function being referenced
                    reference=reference.to_pure(),  # where it is referenced
                )
            )
            # this should make the index aware that this function at this ref loc is called by the caller
            # at the caller's def loc
            self.data[caller_func_like].definitions.merge_or_insert(cross_ref_definition)
            # Maintain reverse mapping for the caller's definition as it's inserted/merged here
            self._pure_def_to_symbol[caller.definition] = caller_func_like

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, func_like: Symbol) -> FunctionLikeInfo:
        if func_like not in self.data:
            raise KeyError(f"{func_like} not found in index.")
        return self.data[func_like].to_function_like_info()

    def __setitem__(self, func_like: Symbol, info: FunctionLikeInfo):
        # Delete existing entries (and purge mapping) before replacing
        if func_like in self.data:
            self.__delitem__(func_like)
        self.data[func_like] = CrossRefIndex.Info.from_function_like_info(info)
        # Register mapping for all definitions of this symbol
        for pure_def, definition in self.data[func_like].definitions.items():
            self._pure_def_to_symbol[pure_def] = func_like

    def __delitem__(self, func_like: Symbol):
        # Remove reverse mapping entries for this symbol's definitions
        info = self.data.get(func_like)
        if info is not None:
            for pure_def in list(info.definitions.keys()):
                self._pure_def_to_symbol.pop(pure_def, None)
        self.data.pop(func_like)

    def __contains__(self, func_like: Symbol) -> bool:
        return func_like in self.data

    def __iter__(self) -> Iterator[Symbol]:
        return iter(self.data)

    def update(self, mapping: dict[Symbol, FunctionLikeInfo]):
        """Updates the index with a mapping of Symbol to FunctionLikeInfo."""
        for func_like, info in mapping.items():
            self.data[func_like].update_from(info)
        # After batch update, recompute the reverse mapping for consistency
        self._recompute_pure_def_mapping()
        return self

    def items(self) -> Iterable[tuple[Symbol, FunctionLikeInfo]]:
        """Gets all items in the index as key-value pairs."""
        return ((func_like, info.to_function_like_info()) for func_like, info in self.data.items())

    def get_info(self, func_like: Symbol) -> FunctionLikeInfo | None:
        """Gets function information from the index."""
        if func_like in self.data:
            return self.data[func_like].to_function_like_info()
        return None

    def get_definitions(self, func_like: Symbol) -> Iterable[Definition]:
        """Gets all definitions for a function from the index."""
        info = self.get_info(func_like)
        if info:
            return info.definitions
        return []

    def get_references(self, func_like: Symbol) -> Iterable[Reference]:
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
        # After bulk load, recompute mapping to be safe
        self._recompute_pure_def_mapping()
        return self

    @staticmethod
    def _type_filterer(func_like: Symbol, filter_option: FilterOption) -> bool:
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

            case QueryFullDefinition(symbol=symbol, pure_definition=pure_definition):
                # Get info for the specific symbol
                if symbol not in self.data:
                    return []

                # Check if the specific definition exists in the definitions dictionary
                if pure_definition in self.data[symbol].definitions:
                    matching_definition = self.data[symbol].definitions[pure_definition]

                    # Return only the matching definition in a new FunctionLikeInfo
                    filtered_info = FunctionLikeInfo(
                        definitions=[matching_definition],
                        references=list(
                            self.data[symbol].references.values()
                        ),  # Include all references for context
                    )
                    return [CodeQuerySingleResponse(func_like=symbol, info=filtered_info)]

                return []

        raise ValueError(f"Unsupported query type: {type(query)}")

    def _recompute_pure_def_mapping(self) -> None:
        """Rebuild the PureDefinition -> Symbol reverse mapping."""
        self._pure_def_to_symbol.clear()
        for symbol, info in self.data.items():
            for pure_def in info.definitions.keys():
                self._pure_def_to_symbol[pure_def] = symbol

    def find_full_definition(
        self, pure_definition: PureDefinition
    ) -> tuple[Symbol, Definition] | None:
        """Fast resolve full Definition via maintained reverse mapping."""
        symbol = self._pure_def_to_symbol.get(pure_definition)
        if symbol is None:
            return None
        definition = self.data[symbol].definitions.get(pure_definition)
        if definition is None:
            # As a safety net, rebuild mapping once and retry
            self._recompute_pure_def_mapping()
            symbol = self._pure_def_to_symbol.get(pure_definition)
            if symbol is None:
                return None
            definition = self.data[symbol].definitions.get(pure_definition)
            if definition is None:
                return None
        return symbol, definition
