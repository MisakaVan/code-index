# code_index/language_processor/impl_python.py

"""Python language processor implementation.

This module provides a concrete implementation of the LanguageProcessor protocol
for Python source code. It handles Python-specific syntax for function and method
definitions, as well as function and method calls using tree-sitter.

The processor supports:
- Function definitions (standalone functions)
- Method definitions (class-bound functions)
- Function calls with identifier names
- Method calls with attribute access (obj.method())
- Decorated functions and methods
"""

from tree_sitter import Node
from tree_sitter_language_pack import get_language

from .base import BaseLanguageProcessor, QueryContext
from ..models import (
    Definition,
    Reference,
    CodeLocation,
    FunctionLike,
    Function,
    FunctionLikeRef,
    Method,
)
from ..utils.logger import logger


class PythonProcessor(BaseLanguageProcessor):
    """Language processor for Python source code.

    Handles parsing and analysis of Python function and method definitions,
    as well as function and method calls. Supports Python-specific features
    like decorators, class methods, and attribute-based method calls.

    The processor distinguishes between:
    - Functions: Standalone callable definitions
    - Methods: Functions defined within a class
    - Function calls: Direct function invocation by name
    - Method calls: Attribute-based method invocation (obj.method())
    """

    def __init__(self):
        """Initialize the Python processor with language-specific configuration."""
        super().__init__(
            name="python",
            language=get_language("python"),
            extensions=[".py"],
            def_query_str="""
                [
                  (function_definition) @function.definition
                ]
            """,
            ref_query_str="""
                (call) @function.call
            """,
        )

    def handle_definition(
        self,
        node: Node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Definition] | None:
        """Process a Python function or method definition.

        Handles function_definition nodes and determines whether they represent
        standalone functions or class methods based on their context. Also
        analyzes function calls within the definition body.

        Args:
            node: A function_definition syntax tree node.
            ctx: Query context containing file information.

        Returns:
            A tuple of (symbol, definition) where symbol is either a Function
            or Method depending on the definition context, None if the function
            name cannot be extracted.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        func_name = ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode("utf8")

        # Determine if this is a method definition (inside a class)
        is_method = self._is_method_definition(node)

        # Find all function calls within the function body
        calls = []

        # Get the function body node
        body_node = node.child_by_field_name("body")
        if body_node:
            # Search for all function calls within the function body
            for call_node in self.get_reference_nodes(body_node):
                call_result = self.handle_reference(call_node, ctx)
                if call_result:
                    symbol, reference = call_result
                    calls.append(FunctionLikeRef(symbol=symbol, reference=reference))

        # Return different symbol types based on whether it's a method definition
        if is_method:
            # Try to get the class name
            class_name = self._get_class_name_for_method(node, ctx)
            symbol = Method(name=func_name, class_name=class_name)
        else:
            symbol = Function(name=func_name)

        # Determine definition range: if parent is decorated_definition, start from decorators
        definition_node = self._get_definition_range_node(node)

        return (
            symbol,
            Definition(
                location=CodeLocation(
                    file_path=ctx.file_path,
                    start_lineno=definition_node.start_point[0] + 1,
                    start_col=definition_node.start_point[1],
                    end_lineno=definition_node.end_point[0] + 1,
                    end_col=definition_node.end_point[1],
                    start_byte=definition_node.start_byte,
                    end_byte=definition_node.end_byte,
                ),
                calls=calls,
            ),
        )

    def _get_definition_range_node(self, function_node: Node) -> Node:
        """Get the node to use for definition range, including decorators if present.

        Args:
            function_node: The function_definition node.

        Returns:
            The decorated_definition node if the function has decorators,
            otherwise the function_definition node itself.
        """
        # Check if parent node is decorated_definition
        if function_node.parent and function_node.parent.type == "decorated_definition":
            return function_node.parent
        return function_node

    def _is_method_definition(self, node: Node) -> bool:
        """Check if a function definition is inside a class (i.e., is a method).

        Args:
            node: The function_definition node to check.

        Returns:
            True if the function is defined within a class, False otherwise.
        """
        current = node.parent
        while current:
            if current.type == "class_definition":
                return True
            current = current.parent
        return False

    def _get_class_name_for_method(self, node: Node, ctx: QueryContext) -> str | None:
        """Get the name of the class that contains this method.

        Args:
            node: The function_definition node representing a method.
            ctx: Query context for accessing source bytes.

        Returns:
            The class name as a string, or None if not found.
        """
        current = node.parent
        while current:
            if current.type == "class_definition":
                name_node = current.child_by_field_name("name")
                if name_node:
                    return ctx.source_bytes[name_node.start_byte : name_node.end_byte].decode(
                        "utf8"
                    )
            current = current.parent
        return None

    def handle_reference(
        self,
        node,
        ctx: QueryContext,
    ) -> tuple[FunctionLike, Reference] | None:
        """Process a Python function or method call.

        Handles call nodes and determines whether they represent function calls
        (direct identifier calls) or method calls (attribute access calls).
        Uses the entire call node range including arguments for location tracking.

        Args:
            node: A call syntax tree node.
            ctx: Query context containing file information.

        Returns:
            A tuple of (symbol, reference) where symbol is either a Function
            or Method depending on the call type, None if the call cannot
            be processed.
        """
        # call node contains function and arguments, we need to capture the entire call node range
        function_node = node.child_by_field_name("function")
        if not function_node:
            logger.warning(
                f"Expected 'function' node to exist in call expression at {ctx.file_path}"
            )
            return None

        # Handle function calls (function: identifier)
        if function_node.type == "identifier":
            func_name = ctx.source_bytes[function_node.start_byte : function_node.end_byte].decode(
                "utf8"
            )
            # Use the entire call node range, including function name, parentheses and arguments
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

        # Handle method calls (function: attribute)
        elif function_node.type == "attribute":
            # Find method name (the last identifier in the attribute node)
            method_name_node = None
            for child in reversed(function_node.children):
                if child.type == "identifier":
                    method_name_node = child
                    break

            if not method_name_node:
                logger.warning(f"Could not find method name in attribute node at {ctx.file_path}")
                return None

            method_name = ctx.source_bytes[
                method_name_node.start_byte : method_name_node.end_byte
            ].decode("utf8")

            # Use the entire call node range, including object expression, dot, method name, parentheses and arguments
            return (
                Method(
                    name=method_name, class_name=None
                ),  # Set class_name to None as per requirements
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

        else:
            logger.warning(
                f"Unexpected function node type '{function_node.type}' at {ctx.file_path}"
            )
            return None
