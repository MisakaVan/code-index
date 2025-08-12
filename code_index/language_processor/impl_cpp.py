# code_index/language_processor/impl_cpp.py

"""C++ language processor implementation.

This module provides a concrete implementation of the LanguageProcessor protocol
for C++ source code. It handles C++ specific syntax for function definitions
and function calls using tree-sitter.

TODO: Method calls (member function calls with object.method() or ptr->method()
syntax) are not yet implemented. Currently only handles standalone function calls.
"""

from tree_sitter import Node
from tree_sitter_language_pack import get_language

from ..models import (
    CodeLocation,
    Definition,
    Function,
    FunctionLike,
    Reference,
    SymbolReference,
)
from .base import BaseLanguageProcessor, QueryContext


class CppProcessor(BaseLanguageProcessor):
    """Language processor for C++ source code.

    Handles parsing and analysis of C++ function definitions and calls.
    Supports standard C++ function syntax including function declarations,
    definitions, and basic function calls.

    TODO: Method calls and member function analysis not yet implemented.
    Currently focuses on standalone functions only.
    """

    def __init__(self):
        """Initialize the C++ processor with language-specific configuration."""
        super().__init__(
            name="cpp",
            language=get_language("cpp"),
            extensions=[".cpp", ".hpp", ".cc", ".h", ".cxx", ".hxx"],
            def_query_str="""
                [
                    (function_definition) @function.definition
                ]
            """,
            ref_query_str="""
                (call_expression) @function.call
            """,
        )

    def _handle_function_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[Function, Definition] | None:
        """Handle a C++ function definition node.

        Processes function_definition nodes to extract the function name and
        analyze function calls within the definition body. Also extracts
        preceding documentation comments.

        Args:
            node: A function_definition syntax tree node.
            ctx: Query context containing file information.

        Returns:
            A tuple of (Function, Definition) if successful, None if the node
            cannot be processed (e.g., malformed function definition).
        """
        assert node.type == "function_definition", f"Expected function_definition, got {node.type}"

        declarator_node = node.child_by_field_name("declarator")
        if not declarator_node or declarator_node.type != "function_declarator":
            return None

        name_node = declarator_node.child_by_field_name("declarator")
        if not name_node or name_node.type != "identifier":
            return None

        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        # Extract preceding comment/documentation
        doc_comment = self._extract_preceding_comment(node, ctx)

        # Find all function calls within the function body
        calls = []

        # Get the function body node (compound_statement)
        body_node = node.child_by_field_name("body")
        if body_node:
            # Search for all function calls within the function body
            for call_node in self.get_reference_nodes(body_node):
                call_result = self.handle_reference(call_node, ctx)
                if call_result:
                    symbol, reference = call_result
                    calls.append(SymbolReference(symbol=symbol, reference=reference.to_pure()))

        return (
            Function(name=func_name),
            Definition(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=node.start_point[0] + 1,
                    start_col=node.start_point[1],
                    end_lineno=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                ),
                doc=doc_comment,
                calls=calls,
            ),
        )

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        """Process a definition node based on its type.

        Args:
            node: The syntax tree node representing a definition.
            ctx: Query context containing file information.

        Returns:
            A tuple of (symbol, definition) if the node represents a supported
            definition type, None otherwise.
        """
        if node.type == "function_definition":
            return self._handle_function_definition(node, ctx)

        return None

    def _handle_function_call(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[Function, Reference] | None:
        """Handle a C++ function call expression.

        Processes call_expression nodes to extract the function name being called.
        Currently handles simple function calls with identifier names.

        TODO: Handle method calls (obj.method() or ptr->method() syntax).

        Args:
            node: A call_expression syntax tree node.
            ctx: Query context containing file information.

        Returns:
            A tuple of (Function, PureReference) if successful, None if the call
            expression cannot be processed.
        """
        assert node.type == "call_expression", f"Expected call_expression, got {node.type}"

        name_node = node.child_by_field_name("function")
        if not name_node or name_node.type != "identifier":
            return None

        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        return (
            Function(name=func_name),
            Reference(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=name_node.start_point[0] + 1,
                    start_col=name_node.start_point[1],
                    end_lineno=name_node.end_point[0] + 1,
                    end_col=node.end_point[1],
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                ),
            ),
        )

    def handle_reference(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """Process a function or method call reference.

        Analyzes call_expression nodes to identify the called function or method.
        Currently supports simple function calls with identifier names.

        TODO: Add support for method calls including:
        - Member function calls (obj.method())
        - Pointer-to-member calls (ptr->method())
        - Static member function calls (Class::method())

        Args:
            node: A call_expression syntax tree node.
            ctx: Query context containing file information.

        Returns:
            A tuple of (symbol, reference) if the call can be processed,
            None if the call expression format is not supported.
        """
        name_node = node.child_by_field_name("function")
        if not name_node:
            return None

        if name_node.type == "identifier":
            func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")
            return (
                Function(name=func_name),
                Reference(
                    location=CodeLocation(
                        file_path=ctx.file_path,
                        start_lineno=name_node.start_point[0] + 1,
                        start_col=name_node.start_point[1],
                        end_lineno=name_node.end_point[0] + 1,
                        end_col=name_node.end_point[1],
                        start_byte=name_node.start_byte,
                        end_byte=name_node.end_byte,
                    ),
                ),
            )

        return None

    def _extract_preceding_comment(self, node: Node, ctx: QueryContext) -> str | None:
        """Extract the preceding comment/documentation for a C++ function definition.

        Looks for comment nodes that appear immediately before the function definition.
        Handles both single-line (//) and multi-line (/* */) comment styles.

        Args:
            node: A function_definition syntax tree node.
            ctx: Query context containing file information.

        Returns:
            The comment text as a string, or None if not present.
        """
        # Look for comment nodes that precede this function definition
        current = node.prev_sibling
        comments = []

        # Traverse backwards through siblings to find comments
        while current:
            if current.type == "comment":
                comment_text = ctx.source_bytes[current.start_byte : current.end_byte].decode(
                    "utf8"
                )
                comments.append(self._clean_cpp_comment(comment_text))
            elif current.type not in [
                "preproc_include",
                "preproc_def",
                "preproc_ifdef",
                "preproc_ifndef",
                "preproc_endif",
                "preproc_else",
                "preproc_elif",
            ]:
                # Stop if we hit a non-comment, non-preprocessor node
                break
            current = current.prev_sibling

        if comments:
            # Reverse to get comments in the original order
            comments.reverse()
            return "\n".join(comments)

        return None

    def _clean_cpp_comment(self, raw_comment: str) -> str:
        """Clean up a C++ comment by removing comment delimiters and normalizing whitespace.

        Args:
            raw_comment: The raw comment text including delimiters.

        Returns:
            The cleaned comment text.
        """
        # Remove comment delimiters
        if raw_comment.startswith("/*") and raw_comment.endswith("*/"):
            content = raw_comment[2:-2]
        elif raw_comment.startswith("//"):
            content = raw_comment[2:]
        else:
            content = raw_comment

        # Clean up whitespace and common comment formatting
        lines = content.split("\n")
        cleaned_lines = []
        for line in lines:
            # Remove leading whitespace and common comment prefixes
            line = line.strip()
            if line.startswith("* "):
                line = line[2:]
            elif line.startswith("*"):
                line = line[1:]
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()
