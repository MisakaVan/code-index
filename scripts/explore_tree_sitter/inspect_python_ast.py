#!/usr/bin/env python3
"""
Python AST inspection script using tree-sitter.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ast_pretty_printer import ASTPrettyPrinter, print_code_and_ast


def analyze_python_sample():
    """Analyze a simple Python code sample."""

    printer = ASTPrettyPrinter(show_positions=False, show_text=True, max_text_length=30)

    # Simple function with docstring and call
    simple_example = '''def greet(name):
    """Say hello to someone."""
    return f"Hello, {name}!"

result = greet("World")
print(result)'''

    print_code_and_ast(simple_example, "python", "Simple Python Function", printer)


if __name__ == "__main__":
    print("Python AST Analysis using Tree-sitter")
    print("=" * 50)
    analyze_python_sample()
