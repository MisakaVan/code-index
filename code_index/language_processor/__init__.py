"""Language processor module for code indexing.

This module provides language-specific processors for parsing and analyzing
source code using tree-sitter. Each processor implements the LanguageProcessor
protocol to handle language-specific syntax and semantics for function/method
definitions and references.

The module includes:
- Base classes and protocols for language processing
- Concrete implementations for Python, C, and C++
- Factory function for creating processor instances
"""

from typing import Optional

from .base import LanguageProcessor, QueryContext
from .impl_c import CProcessor
from .impl_cpp import CppProcessor
from .impl_python import PythonProcessor


def language_processor_factory(name: str) -> Optional[LanguageProcessor]:
    """Create a language processor instance based on the language name.

    Args:
        name: The name of the programming language (e.g., 'python', 'c', 'cpp').

    Returns:
        A language processor instance for the specified language, or None if
        no processor is available for the given language name.

    Example:
        >>> processor = language_processor_factory("python")
        >>> if processor:
        ...     # Use the processor to analyze Python code
        ...     pass
    """
    processors = {
        "python": PythonProcessor,
        "c": CProcessor,
        "cpp": CppProcessor,
    }
    processor_class = processors.get(name)
    if processor_class:
        return processor_class()

    print(f"Warning: No language processor found for '{name}'")
    return None
