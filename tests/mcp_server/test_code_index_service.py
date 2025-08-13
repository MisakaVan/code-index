"""Tests for CodeIndexService.

This module contains unit tests for the CodeIndexService class, which handles
code repository indexing and symbol querying operations for the MCP server.

The tests cover:
    - Repository setup and indexing functionality
    - Symbol querying with various search criteria
    - Cache management and persistence strategies
    - Error handling and edge cases

Test Classes:
    TestCodeIndexService: Comprehensive tests for the CodeIndexService class
"""

from unittest.mock import MagicMock, patch

import pytest

from code_index.index.code_query import QueryByName, QueryByNameRegex
from code_index.mcp_server.models import AllSymbolsResponse
from code_index.mcp_server.services import CodeIndexService
from code_index.models import Function, Method


class TestCodeIndexService:
    """Test class for CodeIndexService functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh CodeIndexService instance for each test."""
        # Reset the singleton instance to ensure test isolation
        CodeIndexService._instance = None
        return CodeIndexService.get_instance()

    @pytest.fixture
    def sample_python_code(self):
        """Provide sample Python code for testing."""
        return '''def hello_world(name: str) -> str:
    """Greet someone with their name."""
    return f"Hello, {name}!"

def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two integers."""
    result = a + b
    hello_world("Calculator")  # Call to hello_world
    return result

class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.history = []

    def add(self, a: int, b: int) -> int:
        """Add two numbers and store in history."""
        result = calculate_sum(a, b)  # Call to calculate_sum
        self.history.append(f"{a} + {b} = {result}")
        return result
'''

    @pytest.fixture
    def sample_c_code(self):
        """Provide sample C code for testing."""
        return """#include <stdio.h>

void print_number(int num) {
    printf("Number: %d\\n", num);
}

int add_numbers(int a, int b) {
    int result = a + b;
    print_number(result);  // Call to print_number
    return result;
}

int main() {
    int sum = add_numbers(5, 3);  // Call to add_numbers
    print_number(sum);  // Another call to print_number
    return 0;
}
"""

    def test_singleton_pattern(self):
        """Test that CodeIndexService follows singleton pattern."""
        service1 = CodeIndexService.get_instance()
        service2 = CodeIndexService.get_instance()

        assert service1 is service2
        assert id(service1) == id(service2)

    def test_get_cache_config_auto_strategy_no_existing_cache(self, tmp_path):
        """Test cache config with auto strategy when no cache exists."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        cache_path, strategy = CodeIndexService._get_cache_config(repo_path, "auto")

        # Should default to SQLite when no cache exists
        expected_path = repo_path / ".code_index.cache" / "index.sqlite"
        assert cache_path == expected_path
        assert strategy.__class__.__name__ == "SqlitePersistStrategy"

    def test_get_cache_config_json_strategy(self, tmp_path):
        """Test cache config with explicit JSON strategy."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        cache_path, strategy = CodeIndexService._get_cache_config(repo_path, "json")

        expected_path = repo_path / ".code_index.cache" / "index.json"
        assert cache_path == expected_path
        assert strategy.__class__.__name__ == "SingleJsonFilePersistStrategy"

    def test_get_cache_config_sqlite_strategy(self, tmp_path):
        """Test cache config with explicit SQLite strategy."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        cache_path, strategy = CodeIndexService._get_cache_config(repo_path, "sqlite")

        expected_path = repo_path / ".code_index.cache" / "index.sqlite"
        assert cache_path == expected_path
        assert strategy.__class__.__name__ == "SqlitePersistStrategy"

    def test_get_cache_config_auto_strategy_with_existing_json(self, tmp_path):
        """Test auto strategy detection with existing JSON cache."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        cache_dir = repo_path / ".code_index.cache"
        cache_dir.mkdir()

        # Create existing JSON cache file
        json_cache = cache_dir / "index.json"
        json_cache.write_text("{}")

        cache_path, strategy = CodeIndexService._get_cache_config(repo_path, "auto")

        assert cache_path == json_cache
        assert strategy.__class__.__name__ == "SingleJsonFilePersistStrategy"

    def test_get_cache_config_auto_strategy_with_existing_sqlite(self, tmp_path):
        """Test auto strategy detection with existing SQLite cache."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        cache_dir = repo_path / ".code_index.cache"
        cache_dir.mkdir()

        # Create existing SQLite cache file
        sqlite_cache = cache_dir / "index.sqlite"
        sqlite_cache.write_text("dummy sqlite content")

        cache_path, strategy = CodeIndexService._get_cache_config(repo_path, "auto")

        assert cache_path == sqlite_cache
        assert strategy.__class__.__name__ == "SqlitePersistStrategy"

    def test_get_cache_config_invalid_strategy(self, tmp_path):
        """Test that invalid strategy raises ValueError."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        with pytest.raises(ValueError, match="Unsupported cache strategy: invalid"):
            CodeIndexService._get_cache_config(repo_path, "invalid")

    def test_setup_repo_index_python_fresh_index(self, service, sample_python_code, tmp_path):
        """Test setting up repository index for Python with fresh indexing."""
        # Create test repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Setup repository index
        service.setup_repo_index(repo_path, "python", "json")

        # Verify indexer is initialized
        assert service._indexer is not None

        # Verify cache file is created
        cache_path = repo_path / ".code_index.cache" / "index.json"
        assert cache_path.exists()

        # Verify functions are indexed
        all_functions = service._indexer.get_all_functions()
        function_names = [func.name for func in all_functions]
        assert "hello_world" in function_names
        assert "calculate_sum" in function_names

    def test_setup_repo_index_c_fresh_index(self, service, sample_c_code, tmp_path):
        """Test setting up repository index for C with fresh indexing."""
        # Create test repository
        repo_path = tmp_path / "c_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.c"
        test_file.write_text(sample_c_code)

        # Setup repository index
        service.setup_repo_index(repo_path, "c", "sqlite")

        # Verify indexer is initialized
        assert service._indexer is not None

        # Verify cache file is created
        cache_path = repo_path / ".code_index.cache" / "index.sqlite"
        assert cache_path.exists()

        # Verify functions are indexed
        all_functions = service._indexer.get_all_functions()
        function_names = [func.name for func in all_functions]
        assert "print_number" in function_names
        assert "add_numbers" in function_names
        assert "main" in function_names

    def test_setup_repo_index_load_existing_cache(self, service, sample_python_code, tmp_path):
        """Test loading existing cache when setting up repository index."""
        # Create test repository and index it first
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # First setup to create cache
        service.setup_repo_index(repo_path, "python", "json")
        cache_path = repo_path / ".code_index.cache" / "index.json"
        assert cache_path.exists()

        # Reset service and setup again (should load from cache)
        CodeIndexService._instance = None
        service2 = CodeIndexService.get_instance()

        # Mock the indexer creation to check if load_index is called
        with patch(
            "code_index.mcp_server.services.code_index_service.CodeIndexer"
        ) as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer.load_index = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            service2.setup_repo_index(repo_path, "python", "json")

            # Verify load_index was called since cache exists
            mock_indexer.load_index.assert_called_once()

    def test_setup_repo_index_unsupported_language(self, service, tmp_path):
        """Test that unsupported language raises assertion error."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        with pytest.raises(AssertionError):
            service.setup_repo_index(repo_path, "javascript", "json")

    def test_setup_repo_index_indexing_failure(self, service, tmp_path):
        """Test handling of indexing failure."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        with patch(
            "code_index.mcp_server.services.code_index_service.CodeIndexer"
        ) as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer.index_project.side_effect = Exception("Indexing failed")
            mock_indexer_class.return_value = mock_indexer

            with pytest.raises(RuntimeError, match="Failed to index project"):
                service.setup_repo_index(repo_path, "python", "json")

    def test_setup_repo_index_cache_load_failure(self, service, tmp_path):
        """Test handling of cache loading failure."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        cache_dir = repo_path / ".code_index.cache"
        cache_dir.mkdir()

        # Create corrupted cache file
        json_cache = cache_dir / "index.json"
        json_cache.write_text("corrupted json content")

        with pytest.raises(RuntimeError, match="Failed to load index data"):
            service.setup_repo_index(repo_path, "python", "json")

    def test_setup_repo_index_cache_dump_failure(self, service, sample_python_code, tmp_path):
        """Test handling of cache dump failure."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        with patch(
            "code_index.mcp_server.services.code_index_service.CodeIndexer"
        ) as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer.dump_index.side_effect = Exception("Dump failed")
            mock_indexer_class.return_value = mock_indexer

            with pytest.raises(RuntimeError, match="Failed to persist index data"):
                service.setup_repo_index(repo_path, "python", "json")

    def test_query_symbol_without_indexer(self, service):
        """Test that querying without initialized indexer raises error."""
        query = QueryByName(name="test_function")

        with pytest.raises(RuntimeError, match="Indexer is not initialized"):
            service.query_symbol(query)

    def test_query_symbol_by_name(self, service, sample_python_code, tmp_path):
        """Test querying symbols by name."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        service.setup_repo_index(repo_path, "python", "json")

        # Query for a specific function
        query = QueryByName(name="hello_world")
        response = service.query_symbol(query)
        results = response.results

        assert len(results) > 0
        # Check that we found the function
        found_function = False
        for result in results:
            if hasattr(result, "func_like") and result.func_like.name == "hello_world":
                found_function = True
                break
        assert found_function

    def test_query_symbol_by_name_regex(self, service, sample_python_code, tmp_path):
        """Test querying symbols by name regex."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        service.setup_repo_index(repo_path, "python", "json")

        # Query using regex pattern
        query = QueryByNameRegex(name_regex=r".*_sum")
        results = service.query_symbol(query).results

        assert len(results) > 0
        # Should find calculate_sum function
        found_calculate_sum = False
        for result in results:
            if hasattr(result, "func_like") and result.func_like.name == "calculate_sum":
                found_calculate_sum = True
                break
        assert found_calculate_sum

    def test_query_symbol_no_results(self, service, sample_python_code, tmp_path):
        """Test querying for non-existent symbol."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        service.setup_repo_index(repo_path, "python", "json")

        # Query for non-existent function
        query = QueryByName(name="nonexistent_function")
        results = service.query_symbol(query).results

        assert len(results) == 0

    def test_service_reinitialization_warning(self, service, sample_python_code, tmp_path):
        """Test that reinitializing indexer shows warning."""
        # Setup repository first time
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        service.setup_repo_index(repo_path, "python", "json")

        # Setup again should log warning
        with patch("code_index.mcp_server.services.code_index_service.logger") as mock_logger:
            service.setup_repo_index(repo_path, "python", "json")
            mock_logger.warning.assert_called_with(
                "Indexer is already initialized, reinitializing..."
            )

    def test_get_all_symbols(self, service, sample_python_code, tmp_path):
        """Test getting all symbols from the index."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        service.setup_repo_index(repo_path, "python", "json")

        # Get all symbols
        response = service.get_all_symbols()
        symbols = response.symbols

        assert isinstance(response, AllSymbolsResponse)
        # __init__, add, append, calculate_sum, hello_world
        assert len(symbols) == 5

        symbol_names = [s.name for s in symbols]
        expected_names = ["hello_world", "calculate_sum", "add", "__init__", "append"]

        # Check if the names are correct by comparing sorted lists
        assert sorted(symbol_names) == sorted(expected_names)

        # Check the type of the symbols
        assert all(isinstance(s, (Function, Method)) for s in symbols)

        # A more detailed check
        symbol_map = {s.name: s for s in symbols}
        assert isinstance(symbol_map["hello_world"], Function)
        assert isinstance(symbol_map["calculate_sum"], Function)
        assert isinstance(symbol_map["add"], Method)
        assert isinstance(symbol_map["__init__"], Method)
        assert isinstance(symbol_map["append"], Method)
        assert symbol_map["add"].class_name == "Calculator"
        assert symbol_map["__init__"].class_name == "Calculator"
        assert symbol_map["append"].class_name is None

    def test_get_all_symbols_no_indexer(self, service):
        """Test getting all symbols raises error if indexer is not initialized."""
        with pytest.raises(RuntimeError, match="Indexer is not initialized"):
            service.get_all_symbols()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
