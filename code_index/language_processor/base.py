"""Base classes and protocols for language-specific code processing.

This module defines the core interfaces and base implementations for processing
source code in different programming languages. It provides:

- QueryContext: Container for query execution context
- LanguageProcessor: Protocol defining the interface for language processors
- BaseLanguageProcessor: Base implementation with common functionality

Language processors use tree-sitter for parsing and analyzing source code to
extract function/method definitions and references.
"""

import pathlib
from dataclasses import dataclass
from itertools import chain
from typing import Protocol, List, Iterable

from tree_sitter import Language, Query, Parser, Node, QueryCursor

from ..models import Definition, FunctionLike, Reference
from ..utils.logger import logger


@dataclass
class QueryContext:
    """Context information needed for executing tree-sitter queries.

    Contains the necessary context for processing source code, including
    file path and raw source bytes for accurate node extraction.
    """

    file_path: pathlib.Path
    """Path to the source file being processed."""
    source_bytes: bytes
    """Raw bytes of the source file content."""


class LanguageProcessor(Protocol):
    """Protocol defining the interface for language-specific code processors.

    This protocol establishes the contract that all language processors must
    implement to provide consistent functionality for parsing and analyzing
    source code across different programming languages.

    Language processors are responsible for:
    - Providing language-specific configuration (extensions, queries)
    - Parsing source code using tree-sitter
    - Extracting function/method definitions and references
    - Converting syntax tree nodes to semantic models
    """

    @property
    def name(self) -> str:
        """The name of the programming language (e.g., 'python', 'cpp')."""
        ...

    @property
    def extensions(self) -> List[str]:
        """List of file extensions supported by this processor (e.g., ['.py'])."""
        ...

    @property
    def language(self) -> Language:
        """The tree-sitter Language object for parsing."""
        ...

    @property
    def parser(self) -> Parser:
        """The tree-sitter Parser object configured for this language."""
        ...

    def get_definition_query(self) -> Query:
        """Get the tree-sitter query for finding function/method definitions."""
        ...

    def get_reference_query(self) -> Query:
        """Get the tree-sitter query for finding function/method references."""
        ...

    def get_definition_nodes(self, node: Node) -> Iterable[Node]:
        """Extract all definition nodes from a syntax tree node.

        Args:
            node: The root node to search within.

        Returns:
            An iterable of nodes representing function/method definitions.
        """
        ...

    def get_reference_nodes(self, node: Node) -> Iterable[Node]:
        """Extract all reference nodes from a syntax tree node.

        Args:
            node: The root node to search within.

        Returns:
            An iterable of nodes representing function/method calls.
        """
        ...

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        """Process a function/method definition node.

        Args:
            node: The syntax tree node representing a definition.
            ctx: Context information for the query.

        Returns:
            A tuple of (symbol, definition) if successful, None if the node
            cannot be processed or doesn't match expected format.
        """
        ...

    def handle_reference(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """Process a function/method reference node.

        Args:
            node: The syntax tree node representing a reference/call.
            ctx: Context information for the query.

        Returns:
            A tuple of (symbol, reference) if successful, None if the node
            cannot be processed or doesn't match expected format.
        """
        ...


class BaseLanguageProcessor(LanguageProcessor):
    """Base implementation of LanguageProcessor with common functionality.

    This class provides a concrete implementation that encapsulates shared logic
    across all language processors. It handles:
    - Tree-sitter setup (parser, queries)
    - Common query execution patterns
    - Property management

    Subclasses need only implement the language-specific logic for handling
    individual definition and reference nodes.
    """

    def __init__(
        self,
        name: str,
        language: Language,
        extensions: List[str],
        def_query_str: str,
        ref_query_str: str,
    ):
        """Initialize the base language processor.

        Args:
            name: The name of the programming language.
            language: The tree-sitter Language object.
            extensions: List of supported file extensions.
            def_query_str: Tree-sitter query string for finding definitions.
            ref_query_str: Tree-sitter query string for finding references.
        """
        self._name = name  # language.name is problematic, so set manually
        self._extensions = extensions
        self._language = language
        self._parser = Parser(self._language)
        self._def_query = Query(self._language, def_query_str)
        self._ref_query = Query(self._language, ref_query_str)

    @property
    def name(self) -> str:
        return self._name

    @property
    def extensions(self) -> List[str]:
        return self._extensions

    @property
    def language(self) -> Language:
        return self._language

    @property
    def parser(self) -> Parser:
        return self._parser

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, extensions={self.extensions})"

    def get_definition_query(self) -> Query:
        return self._def_query

    def get_reference_query(self) -> Query:
        return self._ref_query

    def get_definition_nodes(self, node: Node) -> Iterable[Node]:
        """Extract definition nodes using the configured definition query.

        Args:
            node: The root node to search within.

        Returns:
            An iterable of nodes representing function and method definitions.
        """
        captures = QueryCursor(self.get_definition_query()).captures(node)
        func_defs = captures.get("function.definition", [])
        method_defs = captures.get("method.definition", [])
        logger.debug(f"Got {len(func_defs)} function defs and {len(method_defs)} method defs.")
        return chain(func_defs, method_defs)

    def get_reference_nodes(self, node: Node) -> Iterable[Node]:
        """Extract reference nodes using the configured reference query.

        Args:
            node: The root node to search within.

        Returns:
            An iterable of nodes representing function and method calls.
        """
        captures = QueryCursor(self.get_reference_query()).captures(node)
        func_calls = captures.get("function.call", [])
        method_calls = captures.get("method.call", [])
        logger.debug(f"Got {len(func_calls)} function calls and {len(method_calls)} method calls.")
        return chain(func_calls, method_calls)

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        """Handle a definition node - must be implemented by subclasses.

        Args:
            node: The syntax tree node representing a definition.
            ctx: Context information for the query.

        Returns:
            A tuple of (symbol, definition) if successful.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement handle_definition method."
        )

    def handle_reference(
        self,
        node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """Handle a reference node - must be implemented by subclasses.

        Args:
            node: The syntax tree node representing a reference/call.
            ctx: Context information for the query.

        Returns:
            A tuple of (symbol, reference) if successful.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement handle_reference method."
        )
