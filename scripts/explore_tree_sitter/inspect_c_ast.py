#!/usr/bin/env python3
"""
C AST inspection script using tree-sitter.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ast_pretty_printer import ASTPrettyPrinter, print_code_and_ast


def analyze_c_sample():
    """Analyze a simple C code sample."""

    printer = ASTPrettyPrinter(show_positions=False, show_text=True, max_text_length=30)

    # Simple function with documentation comment and call
    simple_example = """/**
 * Calculate factorial of a number.
 * @param n The number
 * @return The factorial
 */
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

int main() {
    int result = factorial(5);
    printf("Result: %d\\n", result);
    return 0;
}"""

    print_code_and_ast(simple_example, "c", "Simple C Function", printer)


if __name__ == "__main__":
    print("C AST Analysis using Tree-sitter")
    print("=" * 50)
    analyze_c_sample()
