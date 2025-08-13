"""Integration tests for MCP server.

This module contains integration tests for the complete MCP server implementation,
testing the interaction between the FastMCP server and client using the in-memory
transport pattern recommended by FastMCP documentation.

The tests cover:
    - MCP tools: setup_repo_index, query_symbol, resolve_file_path
    - MCP resources: sourcecode://, line ranges, byte ranges
    - Error handling and edge cases
    - Client-server communication patterns

Test Classes:
    TestMCPServerIntegration: Comprehensive integration tests using FastMCP Client
"""

from pathlib import Path
from pprint import pprint

import fastmcp.exceptions
import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from mcp.types import TextResourceContents

from code_index.index.code_query import CodeQuerySingleResponse, QueryByName, QueryByNameRegex
from code_index.mcp_server.server import mcp
from code_index.mcp_server.services import CodeIndexService


class TestMCPServerIntegration:
    """Integration test class for MCP server functionality."""

    @pytest.fixture
    def mcp_server(self):
        """Create the MCP server instance for testing."""
        return mcp

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

void print_message(const char* msg) {
    printf("%s\\n", msg);
}

int add_numbers(int a, int b) {
    int result = a + b;
    print_message("Addition completed");  // Call to print_message
    return result;
}

int main() {
    int sum = add_numbers(5, 3);  // Call to add_numbers
    print_message("Program finished");  // Another call to print_message
    return 0;
}
"""

    @pytest.fixture
    def test_repo_python(self, tmp_path, sample_python_code):
        """Create a test Python repository."""
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()

        # Create main Python file
        main_file = repo_path / "main.py"
        main_file.write_text(sample_python_code)

        # Create additional Python file
        utils_code = '''def utility_function(x: int, y: int) -> int:
    """A utility function."""
    return x * y + 1

def another_utility() -> str:
    """Another utility function."""
    return "utility result"
'''
        utils_file = repo_path / "utils.py"
        utils_file.write_text(utils_code)

        return repo_path

    @pytest.fixture
    def test_repo_c(self, tmp_path, sample_c_code):
        """Create a test C repository."""
        repo_path = tmp_path / "c_repo"
        repo_path.mkdir()

        # Create main C file
        main_file = repo_path / "main.c"
        main_file.write_text(sample_c_code)

        # Create header file
        header_code = """#ifndef UTILS_H
#define UTILS_H

void helper_function(int value);
int multiply(int a, int b);

#endif
"""
        header_file = repo_path / "utils.h"
        header_file.write_text(header_code)

        return repo_path

    @pytest.fixture(autouse=True, scope="function")
    def reset_code_index_service_internal(self):
        """Reset CodeIndexService before each test.

        Note we should not clear the singleton instance itself, as that instance is referenced
        elsewhere, for example it is bound to the tools in the MCP server.
        """
        CodeIndexService.get_instance()._clear_indexer()
        yield

    @pytest.mark.asyncio
    async def test_resolve_file_path_tool(self, mcp_server, tmp_path):
        """Test the resolve_file_path tool."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        test_file = repo_path / "subdir" / "test.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# test file")

        async with Client(mcp_server) as client:
            # Test with relative path
            result = await client.call_tool(
                "resolve_file_path", {"repo_path": str(repo_path), "file_path": "subdir/test.py"}
            )

            resolved_path = Path(result.data)
            assert resolved_path.is_absolute()
            assert resolved_path.exists()
            assert resolved_path.name == "test.py"

            # Test with absolute path
            result = await client.call_tool(
                "resolve_file_path", {"repo_path": str(repo_path), "file_path": str(test_file)}
            )

            resolved_path = Path(result.data)
            assert resolved_path == test_file.resolve()

    @pytest.mark.asyncio
    async def test_setup_repo_index_tool_python(self, mcp_server, test_repo_python):
        """Test the setup_repo_index tool with Python repository."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "setup_repo_index",
                {"repo_path": str(test_repo_python), "language": "python", "strategy": "json"},
            )

            # Tool should complete with a success msg
            assert isinstance(result.data, str)
            assert result.data.lower().startswith("success")

            # Verify cache file was created
            cache_file = test_repo_python / ".code_index.cache" / "index.json"
            assert cache_file.exists()

    @pytest.mark.asyncio
    async def test_setup_repo_index_tool_c(self, mcp_server, test_repo_c):
        """Test the setup_repo_index tool with C repository."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "setup_repo_index",
                {"repo_path": str(test_repo_c), "language": "c", "strategy": "sqlite"},
            )

            # Tool should complete without error
            assert result.data.lower().startswith("success")

            # Verify cache file was created
            cache_file = test_repo_c / ".code_index.cache" / "index.sqlite"
            assert cache_file.exists()

    @pytest.mark.asyncio
    async def test_setup_repo_index_tool_invalid_language(self, mcp_server, tmp_path):
        """Test setup_repo_index tool with invalid language."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        async with Client(mcp_server) as client:
            with pytest.raises(Exception):  # Should raise an AssertionError
                await client.call_tool(
                    "setup_repo_index",
                    {
                        "repo_path": str(repo_path),
                        "language": "javascript",  # Unsupported language
                        "strategy": "json",
                    },
                )

    @pytest.mark.asyncio
    async def test_query_symbol_tool_by_name(self, mcp_server, test_repo_python):
        """Test the query_symbol tool with name-based query."""
        async with Client(mcp_server) as client:
            # First setup the repository
            await client.call_tool(
                "setup_repo_index",
                {"repo_path": str(test_repo_python), "language": "python", "strategy": "json"},
            )

            # Query for a specific function
            query = QueryByName(name="hello_world")
            result: CallToolResult = await client.call_tool("query_symbol", {"query": query})

            # print(type(result))
            # print(type(result.data))
            # assert isinstance(result.data, CodeQueryResponse)
            # NOTE: the .data attribute is a pydantic model that fastmcp rebuilds from the JSON schema.
            # It behaves like the original model `CodeQueryResponse` but is not the same type. So we do
            # not test the isinstance here.

            assert isinstance(result.structured_content, dict)
            assert len(result.data.results) > 0

            # Check that we found the function
            found_function = False
            for item in result.structured_content["results"]:
                item = CodeQuerySingleResponse.model_validate(item)
                # item here behaves like CodeQuerySingleResponse but is not the same type
                assert hasattr(item, "func_like")
                if item.func_like.name == "hello_world":
                    found_function = True
                    break
            assert found_function

    @pytest.mark.asyncio
    async def test_query_symbol_tool_by_name_regex(self, mcp_server, test_repo_python):
        """Test the query_symbol tool with regex-based query."""
        async with Client(mcp_server) as client:
            # First setup the repository
            await client.call_tool(
                "setup_repo_index",
                {"repo_path": str(test_repo_python), "language": "python", "strategy": "json"},
            )

            # Query using regex pattern
            query = QueryByNameRegex(name_regex=r".*_sum")
            result = await client.call_tool("query_symbol", {"query": query})

            # assert isinstance(result.data, CodeQueryResponse)
            assert len(result.data.results) > 0

            # Should find calculate_sum function
            found_calculate_sum = False
            for item in result.structured_content["results"]:
                item = CodeQuerySingleResponse.model_validate(item)
                if item.func_like.name == "calculate_sum":
                    found_calculate_sum = True
                    break
            assert found_calculate_sum

    @pytest.mark.skip(reason="Does not work when running the whole test suite")
    @pytest.mark.asyncio
    async def test_query_symbol_tool_without_setup(self, mcp_server):
        """Test query_symbol tool without setting up repository first."""
        CodeIndexService.get_instance()._clear_indexer()
        async with Client(mcp_server) as client:
            query = QueryByName(name="test_function")

            # Should raise an MCP error, not a regular exception

            with pytest.raises(fastmcp.exceptions.ToolError):
                await client.call_tool("query_symbol", {"query": query})

    @pytest.mark.asyncio
    async def test_fetch_source_code_resource_full_file(
        self, mcp_server, test_repo_python, sample_python_code
    ):
        """Test fetching full source code using MCP resource."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            result = await client.read_resource(f"sourcecode://{main_file}")

            # Handle the fact that read_resource returns a list of TextResourceContents
            assert isinstance(result, list)
            assert len(result) > 0
            assert result[0].text == sample_python_code

    @pytest.mark.asyncio
    async def test_fetch_source_code_resource_nonexistent_file(self, mcp_server, tmp_path):
        """Test fetching source code for non-existent file."""
        nonexistent_file = tmp_path / "nonexistent.py"

        async with Client(mcp_server) as client:
            with pytest.raises(Exception):  # Should raise FileNotFoundError
                await client.read_resource(f"sourcecode://{nonexistent_file}")

    @pytest.mark.asyncio
    async def test_fetch_source_code_by_line_range_tool(self, mcp_server, test_repo_python):
        """Test fetching source code by line range using MCP tool."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            # Get lines 1-3 using the tool interface
            result = await client.call_tool(
                "fetch_source_code_by_lineno_range",
                {"file_path": str(main_file), "start_line": 1, "end_line": 3},
            )

            lines = result.data.split("\n")
            assert len(lines) == 3
            assert lines[0].startswith("def hello_world")
            assert '"""Greet someone with their name."""' in lines[1]

    @pytest.mark.asyncio
    async def test_fetch_source_code_by_line_range_invalid_range(
        self, mcp_server, test_repo_python
    ):
        """Test fetching source code with invalid line range using tool."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            with pytest.raises(Exception):  # Should raise ValueError
                await client.call_tool(
                    "fetch_source_code_by_lineno_range",
                    {"file_path": str(main_file), "start_line": 5, "end_line": 2},
                )

    @pytest.mark.asyncio
    async def test_fetch_source_code_by_line_range_out_of_bounds(
        self, mcp_server, test_repo_python
    ):
        """Test fetching source code with out-of-bounds line range using tool."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            # Request lines beyond file length - should adjust automatically
            result = await client.call_tool(
                "fetch_source_code_by_lineno_range",
                {"file_path": str(main_file), "start_line": 1, "end_line": 1000},
            )

            # Should return the entire file content (adjusted bounds)
            assert len(result.data) > 0
            assert "def hello_world" in result.data

    @pytest.mark.asyncio
    async def test_fetch_source_code_by_byte_range_tool(self, mcp_server, test_repo_python):
        """Test fetching source code by byte range using MCP tool."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            # Get first 50 bytes using the tool interface
            result = await client.call_tool(
                "fetch_source_code_by_byte_range",
                {"file_path": str(main_file), "start_byte": 0, "end_byte": 50},
            )

            assert len(result.data.encode("utf-8")) <= 50
            assert result.data.startswith("def hello_world")

    @pytest.mark.asyncio
    async def test_fetch_source_code_by_byte_range_invalid_range(
        self, mcp_server, test_repo_python
    ):
        """Test fetching source code with invalid byte range using tool."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            with pytest.raises(Exception):  # Should raise ValueError
                await client.call_tool(
                    "fetch_source_code_by_byte_range",
                    {"file_path": str(main_file), "start_byte": 100, "end_byte": 50},
                )

    @pytest.mark.asyncio
    async def test_fetch_source_code_by_byte_range_out_of_bounds(
        self, mcp_server, test_repo_python
    ):
        """Test fetching source code with out-of-bounds byte range using tool."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            # Request bytes beyond file length - should adjust automatically
            result = await client.call_tool(
                "fetch_source_code_by_byte_range",
                {"file_path": str(main_file), "start_byte": 0, "end_byte": 10000},
            )

            # Should return the entire file content (adjusted bounds)
            assert len(result.data) > 0
            assert "def hello_world" in result.data

    @pytest.mark.asyncio
    async def test_full_workflow_python_repository(
        self, mcp_server, test_repo_python, sample_python_code
    ):
        """Test complete workflow: setup, query, and fetch for Python repository."""
        async with Client(mcp_server) as client:
            # Step 1: Setup repository index
            await client.call_tool(
                "setup_repo_index",
                {"repo_path": str(test_repo_python), "language": "python", "strategy": "json"},
            )

            # Step 2: Query for functions
            query = QueryByName(name="calculate_sum")
            query_result = await client.call_tool("query_symbol", {"query": query})
            assert len(query_result.data.results) > 0

            # Step 3: Fetch source code for the file containing the function
            main_file = test_repo_python / "main.py"
            source_result = await client.read_resource(f"sourcecode://{main_file}")

            assert "".join([part.text for part in source_result]) == sample_python_code

            # Step 4: Fetch specific lines around the function using the new tool
            lines_result = await client.call_tool(
                "fetch_source_code_by_lineno_range",
                {"file_path": str(main_file), "start_line": 5, "end_line": 8},
            )
            assert "calculate_sum" in lines_result.data

    @pytest.mark.asyncio
    async def test_full_workflow_c_repository(self, mcp_server, test_repo_c, sample_c_code):
        """Test complete workflow: setup, query, and fetch for C repository."""
        async with Client(mcp_server) as client:
            # Step 1: Setup repository index
            await client.call_tool(
                "setup_repo_index",
                {"repo_path": str(test_repo_c), "language": "c", "strategy": "sqlite"},
            )

            # Step 2: Query for functions
            query = QueryByName(name="add_numbers")
            query_result = await client.call_tool("query_symbol", {"query": query})
            assert len(query_result.data.results) > 0

            # Step 3: Fetch source code
            main_file = test_repo_c / "main.c"
            source_result = await client.read_resource(f"sourcecode://{main_file}")
            assert "".join([part.text for part in source_result]) == sample_c_code

            # Step 4: Fetch specific byte range using the new tool
            bytes_result = await client.call_tool(
                "fetch_source_code_by_byte_range",
                {"file_path": str(main_file), "start_byte": 20, "end_byte": 100},
            )
            assert len(bytes_result.data) > 0

    @pytest.mark.asyncio
    async def test_resource_uri_parsing(self, mcp_server, test_repo_python, sample_python_code):
        """Test that resource URIs are parsed correctly."""
        main_file = test_repo_python / "main.py"

        async with Client(mcp_server) as client:
            # Test various URI formats
            test_cases = [
                f"sourcecode://{main_file}",
            ]

            for uri in test_cases:
                try:
                    result: list[TextResourceContents] = await client.read_resource(uri)
                    print(type(result))
                    pprint(result)
                except Exception as e:
                    pytest.fail(f"Failed to parse URI {uri}: {e}")

                assert isinstance(result, list)
                assert len(result) > 0
                assert result[0].text.startswith("def hello_world")
                # join all texts if multiple parts
                full_text = "".join([part.text for part in result])
                assert full_text == sample_python_code

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, mcp_server, test_repo_python):
        """Test concurrent MCP operations."""
        import asyncio

        async with Client(mcp_server) as client:
            # Setup repository first
            await client.call_tool(
                "setup_repo_index",
                {"repo_path": str(test_repo_python), "language": "python", "strategy": "json"},
            )

            # Create multiple concurrent operations using the new tool interfaces
            main_file = test_repo_python / "main.py"
            tasks = [
                client.read_resource(f"sourcecode://{main_file}"),
                client.call_tool(
                    "fetch_source_code_by_lineno_range",
                    {"file_path": str(main_file), "start_line": 1, "end_line": 5},
                ),
                client.call_tool("query_symbol", {"query": QueryByName(name="hello_world")}),
                client.call_tool(
                    "fetch_source_code_by_byte_range",
                    {"file_path": str(main_file), "start_byte": 0, "end_byte": 50},
                ),
            ]

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All operations should succeed
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    pytest.fail(f"Task {i} failed: {result}")
                assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
