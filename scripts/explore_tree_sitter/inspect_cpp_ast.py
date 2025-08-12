#!/usr/bin/env python3
"""
C++ AST inspection script using tree-sitter.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ast_pretty_printer import ASTPrettyPrinter, print_code_and_ast


def analyze_cpp_sample():
    """Analyze a simple C++ code sample."""

    printer = ASTPrettyPrinter(show_positions=False, show_text=True, max_text_length=30)

    # Simple class with method and call
    simple_example = """/**
 * @brief Simple calculator class.
 */
class Calculator {
private:
    int value;

public:
    /**
     * @brief Constructor.
     * @param initial_value Starting value
     */
    Calculator(int initial_value) : value(initial_value) {}

    /**
     * @brief Add a number.
     * @param n Number to add
     * @return New value
     */
    int add(int n) {
        value += n;
        return value;
    }
};

int main() {
    Calculator calc(10);
    int result = calc.add(5);
    return 0;
}"""

    print_code_and_ast(simple_example, "cpp", "Simple C++ Class", printer)


if __name__ == "__main__":
    print("C++ AST Analysis using Tree-sitter")
    print("=" * 50)
    analyze_cpp_sample()
