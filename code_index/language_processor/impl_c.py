# code_index/language_processor/impl_c.py

"""C language processor implementation.

This module provides a concrete implementation of the LanguageProcessor protocol
for C source code. It handles C-specific syntax for function definitions and
function calls using tree-sitter.

The processor supports:
- Function definitions with various declaration patterns
- Function calls and references
- Handling of function pointers and complex declarators
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


class CProcessor(BaseLanguageProcessor):
    """Language processor for C source code.

    Handles parsing and analysis of C function definitions and calls.
    Supports various C function declaration patterns including:
    - Simple function definitions
    - Functions with storage class specifiers
    - Functions returning pointers
    - Function pointer declarations
    """

    def __init__(self):
        """Initialize the C processor with language-specific configuration."""
        super().__init__(
            name="c",
            language=get_language("c"),
            extensions=[".c", ".h"],
            def_query_str="""
                (function_definition) @function.definition
            """,
            ref_query_str="""
                (call_expression) @function.call
            """,
        )

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        """Process a C function definition node.

        Handles function_definition nodes with various declaration patterns:
        1. Simple: primitive_type -> function_declarator -> compound_statement
        2. With modifiers: storage_class_specifier -> primitive_type -> function_declarator -> compound_statement
        3. Pointer return: storage_class_specifier -> primitive_type -> pointer_declarator -> compound_statement

        Args:
            node: A function_definition syntax tree node.
            ctx: Query context containing file information.

        Returns:
            A tuple of (Function, Definition) if successful, None if the function
            name cannot be extracted or the definition format is not recognized.
        """
        # Extract function name from various AST patterns
        func_name = self._extract_function_name(node, ctx)
        if not func_name:
            return None

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

    def _extract_function_name(self, function_def_node: Node, ctx: QueryContext) -> str | None:
        """Extract function name from a function_definition node.

        Handles various C function declaration patterns by traversing the
        declarator field which may be either a function_declarator or
        pointer_declarator containing a function_declarator.

        Args:
            function_def_node: The function_definition node to process.
            ctx: Query context for accessing source bytes.

        Returns:
            The function name as a string, or None if extraction fails.
        """
        # Find the declarator field, could be function_declarator or pointer_declarator
        declarator_node = function_def_node.child_by_field_name("declarator")
        if not declarator_node:
            return None

        # If it's a pointer_declarator, search for nested function_declarator
        if declarator_node.type == "pointer_declarator":
            # Look for function_declarator in pointer_declarator children
            for child in declarator_node.children:
                if child.type == "function_declarator":
                    declarator_node = child
                    break
            else:
                return None

        # Now declarator_node should be function_declarator
        if declarator_node.type != "function_declarator":
            return None

        # Extract function name from function_declarator
        name_node = declarator_node.child_by_field_name("declarator")
        if not name_node or name_node.type != "identifier":
            return None

        return ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

    def handle_reference(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """Process a C function call expression.

        Handles call_expression nodes to extract the called function name.
        Uses the entire call_expression range including function name,
        parentheses, and arguments for accurate location tracking.

        Args:
            node: A call_expression syntax tree node.
            ctx: Query context containing file information.

        Returns:
            A tuple of (Function, PureReference) if successful, None if the call
            expression doesn't have a recognizable function identifier.
        """
        name_node = node.child_by_field_name("function")
        if not name_node or name_node.type != "identifier":
            return None

        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        # Use the entire call_expression node range, including function name, parentheses and arguments
        return (
            Function(name=func_name),
            Reference(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=node.start_point[0] + 1,
                    start_col=node.start_point[1],
                    end_lineno=node.end_point[0] + 1,
                    end_col=node.end_point[1],
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                ),
            ),
        )

    def _extract_preceding_comment(self, node: Node, ctx: QueryContext) -> str | None:
        """Extract the preceding comment/documentation for a C function definition.

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
                comments.append(self._clean_c_comment(comment_text))
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

    def _clean_c_comment(self, raw_comment: str) -> str:
        """Clean up a C comment by removing comment delimiters and normalizing whitespace.

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
