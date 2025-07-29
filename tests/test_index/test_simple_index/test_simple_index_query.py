"""
Test SimpleIndex query functionality.
"""

import pytest
from pathlib import Path

from code_index.models import (
    CodeLocation,
    Definition,
    Reference,
    FunctionLikeInfo,
    Function,
    Method,
)
from code_index.index.simple_index import SimpleIndex
from code_index.index.code_query import (
    QueryByKey,
    QueryByName,
    QueryByNameRegex,
    FilterOption,
    CodeQuerySingleResponse,
)


class TestSimpleIndexQuery:
    """Test SimpleIndex query functionality."""

    def setup_method(self):
        """Set up test data."""
        self.index = SimpleIndex()

        # Create test data
        self.func1 = Function(name="test_func")
        self.func2 = Function(name="another_func")
        self.method1 = Method(name="test_method", class_name="TestClass")
        self.method2 = Method(name="test_func", class_name="AnotherClass")  # Same name as func1

        # Create test locations
        self.loc1 = CodeLocation(
            file_path=Path("test1.py"),
            start_lineno=1,
            start_col=0,
            end_lineno=1,
            end_col=10,
            start_byte=0,
            end_byte=10,
        )
        self.loc2 = CodeLocation(
            file_path=Path("test2.py"),
            start_lineno=5,
            start_col=4,
            end_lineno=7,
            end_col=8,
            start_byte=50,
            end_byte=80,
        )
        self.loc3 = CodeLocation(
            file_path=Path("test3.py"),
            start_lineno=10,
            start_col=0,
            end_lineno=15,
            end_col=0,
            start_byte=100,
            end_byte=150,
        )

        # Create test definitions and references
        self.def1 = Definition(location=self.loc1)
        self.def2 = Definition(location=self.loc2)
        self.def3 = Definition(location=self.loc3)

        self.ref1 = Reference(location=self.loc1)
        self.ref2 = Reference(location=self.loc2)

        # Add test data to index
        self.index.add_definition(self.func1, self.def1)
        self.index.add_reference(self.func1, self.ref1)

        self.index.add_definition(self.func2, self.def2)
        self.index.add_reference(self.func2, self.ref2)

        self.index.add_definition(self.method1, self.def3)
        self.index.add_definition(self.method2, self.def1)  # Same location as func1

    def test_query_by_key_existing_function(self):
        """Test QueryByKey for existing function."""
        query = QueryByKey(func_like=self.func1)
        results = list(self.index.handle_query(query))

        assert len(results) == 1
        response = results[0]
        assert response.func_like == self.func1
        assert isinstance(response.info, FunctionLikeInfo)
        assert len(response.info.definitions) == 1
        assert response.info.definitions[0] == self.def1
        assert len(response.info.references) == 1
        assert response.info.references[0] == self.ref1

    def test_query_by_key_existing_method(self):
        """Test QueryByKey for existing method."""
        query = QueryByKey(func_like=self.method1)
        results = list(self.index.handle_query(query))

        assert len(results) == 1
        response = results[0]
        assert response.func_like == self.method1
        assert isinstance(response.info, FunctionLikeInfo)
        assert len(response.info.definitions) == 1
        assert response.info.definitions[0] == self.def3
        assert len(response.info.references) == 0

    def test_query_by_key_non_existing(self):
        """Test QueryByKey for non-existing function."""
        non_existing_func = Function(name="non_existing")
        query = QueryByKey(func_like=non_existing_func)
        results = list(self.index.handle_query(query))

        assert len(results) == 0

    def test_query_by_name_all_filter(self):
        """Test QueryByName with ALL filter."""
        query = QueryByName(name="test_func", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should find both the function and method with same name
        assert len(results) == 2

        # Sort by type for consistent testing
        results.sort(key=lambda r: type(r.func_like).__name__)

        # First should be Function
        assert isinstance(results[0].func_like, Function)
        assert results[0].func_like.name == "test_func"
        assert len(results[0].info.definitions) == 1
        assert results[0].info.definitions[0] == self.def1

        # Second should be Method
        assert isinstance(results[1].func_like, Method)
        assert results[1].func_like.name == "test_func"
        assert results[1].func_like.class_name == "AnotherClass"
        assert len(results[1].info.definitions) == 1
        assert results[1].info.definitions[0] == self.def1

    def test_query_by_name_function_filter(self):
        """Test QueryByName with FUNCTION filter."""
        query = QueryByName(name="test_func", type_filter=FilterOption.FUNCTION)
        results = list(self.index.handle_query(query))

        # Should find only the function, not the method
        assert len(results) == 1
        response = results[0]
        assert isinstance(response.func_like, Function)
        assert response.func_like.name == "test_func"
        assert len(response.info.definitions) == 1
        assert response.info.definitions[0] == self.def1
        assert len(response.info.references) == 1
        assert response.info.references[0] == self.ref1

    def test_query_by_name_method_filter(self):
        """Test QueryByName with METHOD filter."""
        query = QueryByName(name="test_func", type_filter=FilterOption.METHOD)
        results = list(self.index.handle_query(query))

        # Should find only the method, not the function
        assert len(results) == 1
        response = results[0]
        assert isinstance(response.func_like, Method)
        assert response.func_like.name == "test_func"
        assert response.func_like.class_name == "AnotherClass"
        assert len(response.info.definitions) == 1
        assert response.info.definitions[0] == self.def1
        assert len(response.info.references) == 0

    def test_query_by_name_no_matches(self):
        """Test QueryByName with no matches."""
        query = QueryByName(name="non_existing_func")
        results = list(self.index.handle_query(query))

        assert len(results) == 0

    def test_query_by_name_method_only(self):
        """Test QueryByName for method-only name."""
        query = QueryByName(name="test_method", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        assert len(results) == 1
        response = results[0]
        assert isinstance(response.func_like, Method)
        assert response.func_like.name == "test_method"
        assert response.func_like.class_name == "TestClass"
        assert len(response.info.definitions) == 1
        assert response.info.definitions[0] == self.def3

    def test_query_by_name_function_only(self):
        """Test QueryByName for function-only name."""
        query = QueryByName(name="another_func", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        assert len(results) == 1
        response = results[0]
        assert isinstance(response.func_like, Function)
        assert response.func_like.name == "another_func"
        assert len(response.info.definitions) == 1
        assert response.info.definitions[0] == self.def2
        assert len(response.info.references) == 1
        assert response.info.references[0] == self.ref2

    def test_multiple_definitions_same_function(self):
        """Test function with multiple definitions."""
        # Add another definition for func1
        additional_def = Definition(location=self.loc2)
        self.index.add_definition(self.func1, additional_def)

        query = QueryByKey(func_like=self.func1)
        results = list(self.index.handle_query(query))

        assert len(results) == 1
        response = results[0]
        assert response.func_like == self.func1
        # Should have both definitions
        assert len(response.info.definitions) == 2
        assert self.def1 in response.info.definitions
        assert additional_def in response.info.definitions

    def test_multiple_references_same_function(self):
        """Test function with multiple references."""
        # Add another reference for func1
        additional_ref = Reference(location=self.loc3)
        self.index.add_reference(self.func1, additional_ref)

        query = QueryByKey(func_like=self.func1)
        results = list(self.index.handle_query(query))

        assert len(results) == 1
        response = results[0]
        assert response.func_like == self.func1
        # Should have both references
        assert len(response.info.references) == 2
        assert self.ref1 in response.info.references
        assert additional_ref in response.info.references

    def test_default_type_filter(self):
        """Test QueryByName with default type_filter (should be ALL)."""
        query = QueryByName(name="test_func")  # No type_filter specified
        results = list(self.index.handle_query(query))

        # Should find both function and method (default is ALL)
        assert len(results) == 2

    def test_unsupported_query_type(self):
        """Test handling of unsupported query type."""

        # Create a mock unsupported query type
        class UnsupportedQuery:
            pass

        unsupported_query = UnsupportedQuery()

        with pytest.raises(ValueError, match="Unsupported query type"):
            list(self.index.handle_query(unsupported_query))

    def test_empty_index_queries(self):
        """Test queries on empty index."""
        empty_index = SimpleIndex()

        # Test QueryByKey on empty index
        query_key = QueryByKey(func_like=self.func1)
        results = list(empty_index.handle_query(query_key))
        assert len(results) == 0

        # Test QueryByName on empty index
        query_name = QueryByName(name="test_func")
        results = list(empty_index.handle_query(query_name))
        assert len(results) == 0

    def test_method_with_none_class_name(self):
        """Test method with None class_name."""
        method_no_class = Method(name="anonymous_method", class_name=None)
        def_no_class = Definition(location=self.loc1)

        self.index.add_definition(method_no_class, def_no_class)

        # Query by key should find it
        query_key = QueryByKey(func_like=method_no_class)
        results = list(self.index.handle_query(query_key))

        assert len(results) == 1
        response = results[0]
        assert response.func_like == method_no_class
        assert response.func_like.class_name is None

        # Query by name with METHOD filter should find it
        query_name = QueryByName(name="anonymous_method", type_filter=FilterOption.METHOD)
        results = list(self.index.handle_query(query_name))

        assert len(results) == 1
        assert results[0].func_like == method_no_class

    def test_case_sensitive_name_matching(self):
        """Test that name matching is case sensitive."""
        query = QueryByName(name="Test_Func")  # Different case
        results = list(self.index.handle_query(query))

        # Should not find "test_func"
        assert len(results) == 0

    # QueryByNameRegex tests
    def test_query_by_name_regex_simple_pattern(self):
        """Test QueryByNameRegex with simple regex pattern."""
        # Add some additional test data with specific patterns
        func3 = Function(name="debug_helper")
        method3 = Method(name="debug_method", class_name="DebugClass")

        self.index.add_definition(func3, self.def1)
        self.index.add_definition(method3, self.def2)

        # Query for anything starting with "test"
        query = QueryByNameRegex(name_regex=r"^test", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should find test_func (Function), test_func (Method), and test_method
        assert len(results) == 3
        names = {r.func_like.name for r in results}
        assert names == {"test_func", "test_method"}

    def test_query_by_name_regex_ending_pattern(self):
        """Test QueryByNameRegex with ending pattern."""
        # Add functions ending with "_func"
        func3 = Function(name="helper_func")
        func4 = Function(name="util_func")
        method3 = Method(name="process_func", class_name="Worker")

        self.index.add_definition(func3, self.def1)
        self.index.add_definition(func4, self.def2)
        self.index.add_definition(method3, self.def3)

        # Query for anything ending with "_func"
        query = QueryByNameRegex(name_regex=r"_func$", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should find test_func, another_func, helper_func, util_func, process_func
        assert len(results) == 6  # 2 test_func (Function + Method) + 4 new ones
        names = {r.func_like.name for r in results}
        assert "test_func" in names
        assert "another_func" in names
        assert "helper_func" in names
        assert "util_func" in names
        assert "process_func" in names

    def test_query_by_name_regex_containing_pattern(self):
        """Test QueryByNameRegex with containing pattern."""
        # Add functions containing "method"
        func3 = Function(name="get_method_info")
        method3 = Method(name="call_method", class_name="Caller")

        self.index.add_definition(func3, self.def1)
        self.index.add_definition(method3, self.def2)

        # Query for anything containing "method"
        query = QueryByNameRegex(name_regex=r"method", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should find test_method, get_method_info, call_method
        assert len(results) == 3
        names = {r.func_like.name for r in results}
        assert names == {"test_method", "get_method_info", "call_method"}

    def test_query_by_name_regex_function_filter(self):
        """Test QueryByNameRegex with FUNCTION filter."""
        # Add mixed functions and methods
        func3 = Function(name="test_helper")
        method3 = Method(name="test_worker", class_name="TestClass")

        self.index.add_definition(func3, self.def1)
        self.index.add_definition(method3, self.def2)

        # Query for functions starting with "test"
        query = QueryByNameRegex(name_regex=r"^test", type_filter=FilterOption.FUNCTION)
        results = list(self.index.handle_query(query))

        # Should find only functions: test_func, test_helper
        assert len(results) == 2
        for result in results:
            assert isinstance(result.func_like, Function)
        names = {r.func_like.name for r in results}
        assert names == {"test_func", "test_helper"}

    def test_query_by_name_regex_method_filter(self):
        """Test QueryByNameRegex with METHOD filter."""
        # Add mixed functions and methods
        func3 = Function(name="test_helper")
        method3 = Method(name="test_worker", class_name="TestClass")

        self.index.add_definition(func3, self.def1)
        self.index.add_definition(method3, self.def2)

        # Query for methods starting with "test"
        query = QueryByNameRegex(name_regex=r"^test", type_filter=FilterOption.METHOD)
        results = list(self.index.handle_query(query))

        # Should find only methods: test_func (Method), test_method, test_worker
        assert len(results) == 3
        for result in results:
            assert isinstance(result.func_like, Method)
        names = {r.func_like.name for r in results}
        assert names == {"test_func", "test_method", "test_worker"}

    def test_query_by_name_regex_complex_pattern(self):
        """Test QueryByNameRegex with complex regex pattern."""
        # Add functions with numbers and underscores
        func3 = Function(name="func_v1")
        func4 = Function(name="func_v2")
        func5 = Function(name="func_test")
        method3 = Method(name="method_v1", class_name="TestClass")

        self.index.add_definition(func3, self.def1)
        self.index.add_definition(func4, self.def2)
        self.index.add_definition(func5, self.def3)
        self.index.add_definition(method3, self.def1)

        # Query for names matching pattern: word_v followed by digit
        query = QueryByNameRegex(name_regex=r"\w+_v\d+$", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should find func_v1, func_v2, method_v1
        assert len(results) == 3
        names = {r.func_like.name for r in results}
        assert names == {"func_v1", "func_v2", "method_v1"}

    def test_query_by_name_regex_no_matches(self):
        """Test QueryByNameRegex with pattern that matches nothing."""
        query = QueryByNameRegex(name_regex=r"^nonexistent_pattern", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        assert len(results) == 0

    def test_query_by_name_regex_invalid_pattern(self):
        """Test QueryByNameRegex with invalid regex pattern."""
        # Invalid regex pattern (unclosed bracket)
        query = QueryByNameRegex(name_regex=r"[invalid", type_filter=FilterOption.ALL)

        with pytest.raises(ValueError, match="Invalid regex pattern"):
            list(self.index.handle_query(query))

    def test_query_by_name_regex_case_sensitive(self):
        """Test QueryByNameRegex is case sensitive."""
        # Add function with mixed case
        func3 = Function(name="TestFunction")
        self.index.add_definition(func3, self.def1)

        # Query for lowercase "test"
        query = QueryByNameRegex(name_regex=r"^test", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should not find "TestFunction", only "test_func" and "test_method"
        names = {r.func_like.name for r in results}
        assert "TestFunction" not in names
        assert "test_func" in names
        assert "test_method" in names

    def test_query_by_name_regex_case_insensitive(self):
        """Test QueryByNameRegex with case insensitive flag."""
        # Add function with mixed case
        func3 = Function(name="TestFunction")
        self.index.add_definition(func3, self.def1)

        # Query for "test" with case insensitive flag
        query = QueryByNameRegex(name_regex=r"(?i)^test", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should find both "TestFunction" and functions starting with "test"
        names = {r.func_like.name for r in results}
        assert "TestFunction" in names
        assert "test_func" in names
        assert "test_method" in names

    def test_query_by_name_regex_default_filter(self):
        """Test QueryByNameRegex with default type_filter (should be ALL)."""
        # Add mixed functions and methods
        func3 = Function(name="regex_func")
        method3 = Method(name="regex_method", class_name="TestClass")

        self.index.add_definition(func3, self.def1)
        self.index.add_definition(method3, self.def2)

        # Query without specifying type_filter
        query = QueryByNameRegex(name_regex=r"^regex")
        results = list(self.index.handle_query(query))

        # Should find both function and method
        assert len(results) == 2
        names = {r.func_like.name for r in results}
        assert names == {"regex_func", "regex_method"}

    def test_query_by_name_regex_empty_pattern(self):
        """Test QueryByNameRegex with empty pattern."""
        # Empty pattern should match all names
        query = QueryByNameRegex(name_regex=r"", type_filter=FilterOption.ALL)
        results = list(self.index.handle_query(query))

        # Should find all functions and methods in the index
        # At minimum: test_func (Function), test_func (Method), another_func, test_method
        assert len(results) >= 4
        names = {r.func_like.name for r in results}
        assert "test_func" in names
        assert "another_func" in names
        assert "test_method" in names
