"""
Language Processor Tests

This package contains tests for all language processors, organized by language type:

- test_python_processor.py: Tests for Python language processor
- test_c_cpp_processor.py: Tests for C and C++ language processors
- test_common.py: Common tests that apply to all language processors

Each test file contains comprehensive tests for:
- Processor initialization
- Function definition parsing
- Function reference parsing
- Edge cases (empty files, malformed code)
- Language-specific features

The common test file includes:
- Factory function tests
- Cross-language behavior verification
- QueryContext behavior tests
"""

from .test_c_cpp_processor import TestCProcessor, TestCppProcessor
from .test_common import (
    TestLanguageProcessorFactory,
    TestLanguageProcessorCommonBehavior,
    TestQueryContextBehavior,
)
from .test_python_processor import TestPythonProcessor

__all__ = [
    "TestPythonProcessor",
    "TestCProcessor",
    "TestCppProcessor",
    "TestLanguageProcessorFactory",
    "TestLanguageProcessorCommonBehavior",
    "TestQueryContextBehavior",
]
