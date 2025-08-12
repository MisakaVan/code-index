"""
Pretty printer for tree-sitter AST nodes with enhanced formatting and analysis capabilities.
"""

from collections import Counter
from typing import Dict, Optional

import tree_sitter as ts


class ASTPrettyPrinter:
    """Enhanced AST pretty printer with syntax highlighting and detailed node information."""

    def __init__(
        self, show_positions: bool = True, show_text: bool = True, max_text_length: int = 50
    ):
        """
        Initialize the AST pretty printer.

        Args:
            show_positions: Whether to show byte positions for nodes
            show_text: Whether to show the source text for leaf nodes
            max_text_length: Maximum length of text to display before truncating
        """
        self.show_positions = show_positions
        self.show_text = show_text
        self.max_text_length = max_text_length

    def print_tree(
        self,
        node: ts.Node,
        source_bytes: Optional[bytes] = None,
        indent: str = "",
        is_last_sibling: bool = True,
        level: int = 0,
    ) -> None:
        """
        Recursively print AST tree with enhanced formatting.

        Args:
            node: The tree-sitter node to print
            source_bytes: Source code bytes for extracting text
            indent: Current indentation string
            is_last_sibling: Whether this node is the last sibling (for tree drawing)
            level: Current depth level in the tree
        """
        # Get node text if available
        text_info = ""
        if self.show_text and source_bytes and node.child_count == 0:  # Leaf node
            text = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
            if len(text) > self.max_text_length:
                text = text[: self.max_text_length - 3] + "..."
            # Escape special characters for display
            text = repr(text)
            text_info = f" = {text}"

        # Get position info
        pos_info = ""
        if self.show_positions:
            pos_info = f" [{node.start_byte}:{node.end_byte}]"

        # Prepare indentation and connectors
        connector = "└─" if is_last_sibling else "├─"
        additional_indent = "  " if is_last_sibling else "│ "
        assert len(connector) == 2
        assert len(additional_indent) == 2

        # Level info
        level_info = f"[L{level}]"

        # Print the current node
        print(f"{indent}{connector}{level_info} {node.type}{pos_info}{text_info}")

        # Print children with increased indentation
        for i, child in enumerate(node.children):
            _is_last_sibling = i == len(node.children) - 1
            self.print_tree(
                child,
                source_bytes,
                indent + additional_indent,
                _is_last_sibling,
                level + 1,
            )

    @staticmethod
    def iterate_tree(node: ts.Node):
        """
        Generator to iterate over all nodes in the AST.

        Args:
            node: The root node to start iteration

        Yields:
            Each node in the AST
        """
        yield node
        for child in node.children:
            yield from ASTPrettyPrinter.iterate_tree(child)

    def analyze_node_types(self, node: ts.Node) -> Dict[str, int]:
        """
        Analyze and count different node types in the AST using iterate_tree.

        Args:
            node: The root node to analyze

        Returns:
            Dictionary mapping node types to their occurrence counts
        """
        # Use Counter with iterate_tree for efficient counting
        node_types = Counter(n.type for n in self.iterate_tree(node))
        return dict(node_types)

    def find_nodes_by_type(self, node: ts.Node, target_type: str) -> list[ts.Node]:
        """
        Find all nodes of a specific type in the AST using iterate_tree.

        Args:
            node: The root node to search
            target_type: The node type to find

        Returns:
            List of nodes matching the target type
        """
        return [n for n in self.iterate_tree(node) if n.type == target_type]

    def print_analysis_summary(self, node: ts.Node, source_bytes: Optional[bytes] = None) -> None:
        """
        Print a summary analysis of the AST.

        Args:
            node: The root node to analyze
            source_bytes: Source code bytes for context
        """
        print("\n" + "=" * 60)
        print("AST ANALYSIS SUMMARY")
        print("=" * 60)

        # Basic statistics
        total_nodes = self._count_nodes(node)
        max_depth = self._calculate_depth(node)
        print(f"Total nodes: {total_nodes}")
        print(f"Maximum depth: {max_depth}")

        # Node type distribution
        types_count = self.analyze_node_types(node)
        print("\nNode type distribution:")
        for node_type, count in sorted(types_count.items()):
            print(f"  {node_type}: {count}")

        # Common interesting node types
        interesting_types = [
            "function_definition",
            "function_declarator",
            "call_expression",
            "method_definition",
            "class_definition",
            "identifier",
        ]

        print("\nInteresting nodes found:")
        for node_type in interesting_types:
            nodes = self.find_nodes_by_type(node, node_type)
            if nodes:
                print(f"  {node_type}: {len(nodes)} occurrences")
                for i, n in enumerate(nodes[:3]):  # Show first 3
                    if source_bytes:
                        text = source_bytes[n.start_byte : n.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        text = text.replace("\n", "\\n")[:50]
                        print(f"    [{i + 1}] {text}...")

    def _count_nodes(self, node: ts.Node) -> int:
        """Count total number of nodes in the AST."""
        count = 1
        for child in node.children:
            count += self._count_nodes(child)
        return count

    def _calculate_depth(self, node: ts.Node) -> int:
        """Calculate the maximum depth of the AST."""
        if not node.children:
            return 1
        return 1 + max(self._calculate_depth(child) for child in node.children)


def print_code_and_ast(
    code: str, language: str, title: str = "", printer: Optional[ASTPrettyPrinter] = None
) -> None:
    """
    Convenience function to print code and its AST.

    Args:
        code: Source code to analyze
        language: Language name for tree-sitter
        title: Optional title for the output
        printer: Optional custom AST printer
    """
    from tree_sitter import Parser
    from tree_sitter_language_pack import get_language

    if printer is None:
        printer = ASTPrettyPrinter()

    parser = Parser()
    parser.language = get_language(language)

    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)

    print("\n" + "=" * 80)
    if title:
        print(f"ANALYSIS: {title}")
        print("=" * 80)
    print("SOURCE CODE:")
    print("-" * 40)
    print(code)
    print("-" * 40)
    print("AST STRUCTURE:")
    printer.print_tree(tree.root_node, source_bytes)

    # Print analysis summary
    printer.print_analysis_summary(tree.root_node, source_bytes)
    print("=" * 80)
