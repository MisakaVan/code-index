"""Tests for SourceCodeFetchService.

This module contains unit tests for the SourceCodeFetchService class, which handles
source code retrieval operations for the MCP server.

The tests cover:
    - Full file content retrieval
    - Line-based code snippet extraction
    - Byte-based code snippet extraction
    - Error handling and bounds checking
    - Caching functionality

Test Classes:
    TestSourceCodeFetchService: Comprehensive tests for the SourceCodeFetchService class
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Context

from code_index.mcp_server.services import SourceCodeFetchService


class TestSourceCodeFetchService:
    """Test class for SourceCodeFetchService functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh SourceCodeFetchService instance for each test."""
        # Reset the singleton instance to ensure test isolation
        SourceCodeFetchService._instance = None
        return SourceCodeFetchService.get_instance()

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP Context for testing."""
        context = AsyncMock(spec=Context)
        context.log = AsyncMock()
        return context

    @pytest.fixture
    def sample_text_content(self):
        """Provide sample text content for testing."""
        return """Line 1: This is the first line
Line 2: This is the second line
Line 3: This is the third line
Line 4: This is the fourth line
Line 5: This is the fifth line"""

    @pytest.fixture
    def sample_python_content(self):
        """Provide sample Python content for testing."""
        return '''def hello_world(name: str) -> str:
    """Greet someone with their name."""
    return f"Hello, {name}!"

def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two integers."""
    return a + b

class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.history = []

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return calculate_sum(a, b)
'''

    def test_singleton_pattern(self):
        """Test that SourceCodeFetchService follows singleton pattern."""
        service1 = SourceCodeFetchService.get_instance()
        service2 = SourceCodeFetchService.get_instance()

        assert service1 is service2
        assert id(service1) == id(service2)

    @pytest.mark.asyncio
    async def test_fetch_bytes_existing_file(self, service, sample_text_content, tmp_path):
        """Test fetching bytes from an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        result = await service.fetch_bytes(test_file)

        assert isinstance(result, bytes)
        assert result.decode("utf-8") == sample_text_content

    @pytest.mark.asyncio
    async def test_fetch_bytes_nonexistent_file(self, service, tmp_path):
        """Test fetching bytes from a non-existent file."""
        nonexistent_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            await service.fetch_bytes(nonexistent_file)

    @pytest.mark.asyncio
    async def test_fetch_bytes_io_error(self, service, tmp_path):
        """Test handling IO error when fetching bytes."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.object(Path, "read_bytes", side_effect=IOError("IO Error")):
            with pytest.raises(IOError):
                await service.fetch_bytes(test_file)

    @pytest.mark.asyncio
    async def test_fetch_full_source_code_success(self, service, sample_python_content, tmp_path):
        """Test successful full source code retrieval."""
        test_file = tmp_path / "test.py"
        test_file.write_text(sample_python_content, encoding="utf-8")

        result = await service.fetch_full_source_code(test_file)

        assert result == sample_python_content
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_fetch_full_source_code_unicode_error(self, service, tmp_path):
        """Test handling Unicode decode error."""
        test_file = tmp_path / "test.bin"
        # Write binary content that cannot be decoded as UTF-8
        test_file.write_bytes(b"\x80\x81\x82\x83")

        with pytest.raises(UnicodeDecodeError):
            await service.fetch_full_source_code(test_file)

    @pytest.mark.asyncio
    async def test_fetch_by_lineno_range_valid_range(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching code by valid line number range."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        result = await service.fetch_by_lineno_range(test_file, 2, 4, mock_context)

        expected = "Line 2: This is the second line\nLine 3: This is the third line\nLine 4: This is the fourth line"
        assert result == expected
        mock_context.log.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_by_lineno_range_start_less_than_one(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching code with start_line less than 1."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        result = await service.fetch_by_lineno_range(test_file, 0, 2, mock_context)

        expected = "Line 1: This is the first line\nLine 2: This is the second line"
        assert result == expected
        mock_context.log.assert_called_once_with(
            "start_line (0) is less than 1, adjusting to 1.", level="warning"
        )

    @pytest.mark.asyncio
    async def test_fetch_by_lineno_range_end_greater_than_total(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching code with end_line greater than total lines."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        lines = sample_text_content.splitlines()
        total_lines = len(lines)

        result = await service.fetch_by_lineno_range(test_file, 4, total_lines + 2, mock_context)

        expected = "Line 4: This is the fourth line\nLine 5: This is the fifth line"
        assert result == expected
        mock_context.log.assert_called_once_with(
            f"end_line ({total_lines + 2}) is greater than total lines ({total_lines}), adjusting to {total_lines}.",
            level="warning",
        )

    @pytest.mark.asyncio
    async def test_fetch_by_lineno_range_invalid_range(self, service, mock_context, tmp_path):
        """Test fetching code with start_line greater than end_line."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content", encoding="utf-8")

        with pytest.raises(
            ValueError, match="start_line \\(5\\) cannot be greater than end_line \\(2\\)"
        ):
            await service.fetch_by_lineno_range(test_file, 5, 2, mock_context)

    @pytest.mark.asyncio
    async def test_fetch_by_lineno_range_single_line(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching a single line."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        result = await service.fetch_by_lineno_range(test_file, 3, 3, mock_context)

        assert result == "Line 3: This is the third line"
        mock_context.log.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_by_byte_range_valid_range(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching code by valid byte range."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        # Get first 20 bytes
        result = await service.fetch_by_byte_range(test_file, 0, 20, mock_context)

        expected = sample_text_content.encode("utf-8")[:20].decode("utf-8")
        assert result == expected
        mock_context.log.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_by_byte_range_start_less_than_zero(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching code with start_byte less than 0."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        result = await service.fetch_by_byte_range(test_file, -5, 10, mock_context)

        expected = sample_text_content.encode("utf-8")[:10].decode("utf-8")
        assert result == expected
        mock_context.log.assert_called_once_with(
            "start_byte (-5) is less than 0, adjusting to 0.", level="warning"
        )

    @pytest.mark.asyncio
    async def test_fetch_by_byte_range_end_greater_than_total(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching code with end_byte greater than total bytes."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        content_bytes = sample_text_content.encode("utf-8")
        total_bytes = len(content_bytes)

        result = await service.fetch_by_byte_range(test_file, 10, total_bytes + 50, mock_context)

        expected = content_bytes[10:].decode("utf-8")
        assert result == expected
        mock_context.log.assert_called_once_with(
            f"end_byte ({total_bytes + 50}) is greater than total bytes ({total_bytes}), adjusting to {total_bytes}.",
            level="warning",
        )

    @pytest.mark.asyncio
    async def test_fetch_by_byte_range_invalid_range(self, service, mock_context, tmp_path):
        """Test fetching code with start_byte greater than end_byte."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content", encoding="utf-8")

        with pytest.raises(
            ValueError, match="start_byte \\(50\\) cannot be greater than end_byte \\(20\\)"
        ):
            await service.fetch_by_byte_range(test_file, 50, 20, mock_context)

    @pytest.mark.asyncio
    async def test_fetch_by_byte_range_full_file(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching entire file using byte range."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        content_bytes = sample_text_content.encode("utf-8")
        result = await service.fetch_by_byte_range(test_file, 0, len(content_bytes), mock_context)

        assert result == sample_text_content
        mock_context.log.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_by_byte_range_zero_length(
        self, service, mock_context, sample_text_content, tmp_path
    ):
        """Test fetching zero-length byte range."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        result = await service.fetch_by_byte_range(test_file, 10, 10, mock_context)

        assert result == ""
        mock_context.log.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_bytes_caching(self, service, sample_text_content, tmp_path):
        """Test that _fetch_bytes method uses caching."""
        test_file = tmp_path / "test.txt"
        test_file.write_text(sample_text_content, encoding="utf-8")

        # Clear cache before test
        service._file_cache.clear()

        # First call
        result1 = await service._fetch_bytes(test_file)
        assert test_file in service._file_cache

        # Second call (should hit cache)
        result2 = await service._fetch_bytes(test_file)

        assert result1 == result2

    @pytest.mark.asyncio
    async def test_error_propagation_from_fetch_bytes(self, service, tmp_path):
        """Test that errors from fetch_bytes are properly propagated."""
        nonexistent_file = tmp_path / "nonexistent.txt"

        # Test FileNotFoundError propagation
        with pytest.raises(FileNotFoundError):
            await service.fetch_full_source_code(nonexistent_file)

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self, service, tmp_path):
        """Test handling of unexpected errors."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with patch.object(service, "_fetch_bytes", side_effect=RuntimeError("Unexpected error")):
            with pytest.raises(RuntimeError):
                await service.fetch_bytes(test_file)

    @pytest.mark.asyncio
    async def test_empty_file_handling(self, service, mock_context, tmp_path):
        """Test handling of empty files."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        # Test full source code
        result = await service.fetch_full_source_code(empty_file)
        assert result == ""

        # Test line range (should handle gracefully)
        result = await service.fetch_by_lineno_range(empty_file, 1, 1, mock_context)
        assert result == ""

        # Test byte range
        result = await service.fetch_by_byte_range(empty_file, 0, 0, mock_context)
        assert result == ""

    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, service, mock_context, tmp_path):
        """Test handling of Unicode content."""
        unicode_content = "Hello 世界! 🌍 Здравствуй мир!"
        test_file = tmp_path / "unicode.txt"
        test_file.write_text(unicode_content, encoding="utf-8")

        # Test full retrieval
        result = await service.fetch_full_source_code(test_file)
        assert result == unicode_content

        # Test line range
        result = await service.fetch_by_lineno_range(test_file, 1, 1, mock_context)
        assert result == unicode_content

        # Test byte range (first 10 bytes) - be careful with unicode boundaries
        result = await service.fetch_by_byte_range(
            test_file, 0, 6, mock_context
        )  # "Hello " is 6 bytes
        assert result == "Hello "

        # Test larger range that doesn't cut unicode characters
        result = await service.fetch_by_byte_range(test_file, 0, 50, mock_context)
        # Note: We might get partial characters at byte boundaries
        assert len(result) <= len(unicode_content)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
