import re
from collections import defaultdict
from pprint import pformat
from typing import Iterable, Iterator, override

from ...models import (
    Definition,
    Function,
    FunctionLike,
    FunctionLikeInfo,
    IndexData,
    IndexDataEntry,
    Method,
    PureDefinition,
    Reference,
)
from ..base import BaseIndex
from ..code_query import (
    CodeQuery,
    CodeQuerySingleResponse,
    FilterOption,
    QueryByKey,
    QueryByName,
    QueryByNameRegex,
    QueryFullDefinition,
)


class SimpleIndex(BaseIndex):
    """A simple in-memory implementation of the BaseIndex.

    Stores all index data in memory using a dictionary. This implementation
    is suitable for small to medium-sized codebases where fast access and
    simplicity are preferred over memory efficiency.

    Attributes:
        data: Internal dictionary storing function/method information.
    """

    def __init__(self):
        """Initializes an empty SimpleIndex."""
        super().__init__()
        self.data = defaultdict(lambda: FunctionLikeInfo())

    @override
    def __repr__(self):
        """Returns a detailed string representation of the index."""
        return f"SimpleIndex(data={pformat(self.data, compact=True)})"

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
    def __len__(self) -> int:
        return len(self.data)

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
    def __iter__(self) -> Iterator[FunctionLike]:
        return iter(self.data.keys())

    @override
    def items(self) -> Iterable[tuple[FunctionLike, FunctionLikeInfo]]:
        return self.data.items()

    @override
    def update(self, mapping: dict[FunctionLike, FunctionLikeInfo]):
        for func_like, info in mapping.items():
            self[func_like] = info  # may raise KeyError if type is incorrect

    @override
    def as_data(self) -> IndexData:
        listed_data = []
        for func_like, info in self.items():
            listed_data.append(IndexDataEntry(symbol=func_like, info=info))
        return IndexData(data=listed_data, type="simple_index")

    @override
    def update_from_data(self, data: IndexData):
        if data.type != "simple_index":
            raise ValueError("Invalid data type for SimpleIndex.")
        for item in data.data:
            symbol = item.symbol
            info = item.info
            self[symbol] = info

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
        """Processes a query against the index and returns matching results.

        Args:
            query: The query to execute against the index.

        Returns:
            An iterable of CodeQuerySingleResponse containing all matches.

        Raises:
            ValueError: If the query type is unsupported or regex pattern is invalid.
        """
        match query:
            case QueryByKey(func_like=func_like):
                info = self.get_info(func_like)
                if info is None:
                    return []
                return [CodeQuerySingleResponse(func_like=func_like, info=info)]
            case QueryByName(name=name, type_filter=filter_option):
                func_likes = filter(
                    lambda fl: fl.name == name and self._type_filterer(fl, filter_option),
                    self.data.keys(),
                )
                ret = []
                for func_like in func_likes:
                    info = self.get_info(func_like)
                    assert info is not None, f"Info for {func_like} should not be None"
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
                    info = self.get_info(func_like)
                    assert info is not None, f"Info for {func_like} should not be None"
                    ret.append(CodeQuerySingleResponse(func_like=func_like, info=info))
                return ret
            case QueryFullDefinition(symbol=symbol, pure_definition=pure_definition):
                # Get info for the specific symbol
                info = self.get_info(symbol)
                if info is None:
                    return []

                # Find the definition that matches the pure_definition
                matching_definitions = [
                    definition
                    for definition in info.definitions
                    if definition.to_pure() == pure_definition
                ]

                if not matching_definitions:
                    return []

                # Return only the matching definition(s) in a new FunctionLikeInfo
                filtered_info = FunctionLikeInfo(
                    definitions=matching_definitions,
                    references=info.references,  # Include all references for context
                )
                return [CodeQuerySingleResponse(func_like=symbol, info=filtered_info)]

        raise ValueError(f"Unsupported query type: {type(query)}")

    @override
    def find_full_definition(
        self, pure_definition: PureDefinition
    ) -> tuple[FunctionLike, Definition] | None:
        """Linear scan over all symbols/definitions to locate a full definition.

        Args:
            pure_definition: The fingerprint of a definition to locate.

        Returns:
            (symbol, definition) if found; otherwise None.
        """
        for func_like, info in self.data.items():
            for definition in info.definitions:
                if definition.to_pure() == pure_definition:
                    return func_like, definition
        return None
