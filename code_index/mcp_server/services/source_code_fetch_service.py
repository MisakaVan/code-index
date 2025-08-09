"""Source code fetching service for the MCP server.

This module provides the SourceCodeFetchService class, which handles all source code
retrieval operations for the MCP server. It supports multiple access patterns for
fetching code content from files in repositories.

The service provides:
    - Full file content retrieval with UTF-8 decoding
    - Line-based code snippets with 1-based indexing
    - Byte-based code snippets with 0-based indexing
    - LRU caching for improved performance on repeated requests
    - Automatic bounds checking and adjustment with warnings

Key Features:
    - Singleton pattern for consistent state management
    - Asynchronous operations for better performance
    - Comprehensive error handling for file operations
    - Intelligent bounds adjustment with user feedback via MCP context

Classes:
    SourceCodeFetchService: Singleton service for source code fetching operations

Example:
    Basic usage of the service:

    .. code-block:: python

        service = SourceCodeFetchService.get_instance()

        # Fetch full file
        content = await service.fetch_full_source_code(Path("file.py"))

        # Fetch line range
        snippet = await service.fetch_by_lineno_range(
            Path("file.py"), 10, 20, ctx
        )

        # Fetch byte range
        snippet = await service.fetch_by_byte_range(
            Path("file.py"), 100, 200, ctx
        )

Note:
    This service uses LRU caching to optimize repeated file access and provides
    automatic bounds checking with user-friendly warnings through the MCP context.
"""

from pathlib import Path
from typing import Optional

from fastmcp import Context

from code_index.utils.logger import logger


class SourceCodeFetchService:
    """MCP service backend for source code fetch.

    Use async methods to fetch source code from repositories.

    """

    _instance: Optional["SourceCodeFetchService"] = None
    _file_cache: dict[Path, bytes] = {}

    @staticmethod
    def get_instance() -> "SourceCodeFetchService":
        """Get the singleton instance of SourceCodeFetchService."""
        if SourceCodeFetchService._instance is None:
            SourceCodeFetchService._instance = SourceCodeFetchService()
        return SourceCodeFetchService._instance

    def __init__(self):
        pass  # No initialization needed for this service

    async def _fetch_bytes(self, file_path: Path) -> bytes:
        """Fetch the content of a file as bytes.

        This method is cached to improve performance for repeated requests for the same file.

        Args:
            file_path: The path to the file to fetch.

        Returns:
            The content of the file as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If there is an error reading the file.

        """
        # Simple in-memory cache for testing
        if file_path in self._file_cache:
            return self._file_cache[file_path]

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = file_path.read_bytes()
            self._file_cache[file_path] = content
            return content
        except IOError as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise e

    async def fetch_bytes(self, file_path: Path) -> bytes:
        """Fetch the full source code of a file.

        Args:
            file_path: The path to the file to fetch.

        Returns:
            The content of the file as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If there is an error reading the file.

        """
        try:
            return await self._fetch_bytes(file_path)
        except FileNotFoundError as e:
            logger.error(f"File not found: {file_path}")
            raise e
        except IOError as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error fetching file {file_path}: {e}")
            raise e

    async def fetch_full_source_code(self, file_path: Path) -> str:
        """Fetch the full source code of a file.

        Args:
            file_path: The path to the file to fetch.

        Returns:
            The content of the file as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If there is an error reading the file.
            UnicodeDecodeError: If the file cannot be decoded as UTF-8.

        """
        try:
            content = await self.fetch_bytes(file_path)
            return content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as e:
            logger.error(f"Error decoding file {file_path}: {e}")
            raise e

    async def fetch_by_lineno_range(
        self, file_path: Path, start_line: int, end_line: int, ctx: Context
    ) -> str:
        """Fetch a snippet of source code from a file by line range.

        Args:
            file_path: The path to the file to fetch.
            start_line: The starting line number (1-based, inclusive).
            end_line: The ending line number (1-based, inclusive).
            ctx: FastMCP context

        Returns:
            The content of the specified lines as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If there is an error reading the file.
            UnicodeDecodeError: If the file cannot be decoded as UTF-8.
            ValueError: If start_line or end_line are out of bounds.

        """
        if start_line > end_line:
            raise ValueError(
                f"start_line ({start_line}) cannot be greater than end_line ({end_line})."
            )

        full_source_code = await self.fetch_full_source_code(file_path)

        lines = full_source_code.splitlines()

        if start_line < 1:
            await ctx.log(
                f"start_line ({start_line}) is less than 1, adjusting to 1.", level="warning"
            )
            start_line = 1
        if end_line > len(lines):
            await ctx.log(
                f"end_line ({end_line}) is greater than total lines ({len(lines)}), adjusting to {len(lines)}.",
                level="warning",
            )
            end_line = len(lines)

        snippet = "\n".join(lines[start_line - 1 : end_line])
        return snippet

    async def fetch_by_byte_range(
        self, file_path: Path, start_byte: int, end_byte: int, ctx: Context
    ):
        """Fetch a snippet of source code from a file by byte range.

        Args:
            file_path: The path to the file to fetch.
            start_byte: The starting byte offset (0-based, inclusive).
            end_byte: The ending byte offset (0-based, exclusive).
            ctx: FastMCP context

        Returns:
            The content of the specified byte range as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            IOError: If there is an error reading the file.
            UnicodeDecodeError: If the file cannot be decoded as UTF-8.
            ValueError: If start_byte or end_byte are out of bounds.
        """
        if start_byte > end_byte:
            raise ValueError(
                f"start_byte ({start_byte}) cannot be greater than end_byte ({end_byte})."
            )

        full_source_code_bytes = await self.fetch_bytes(file_path)

        if start_byte < 0:
            await ctx.log(
                f"start_byte ({start_byte}) is less than 0, adjusting to 0.", level="warning"
            )
            start_byte = 0
        if end_byte > len(full_source_code_bytes):
            await ctx.log(
                f"end_byte ({end_byte}) is greater than total bytes ({len(full_source_code_bytes)}), adjusting to {len(full_source_code_bytes)}.",
                level="warning",
            )
            end_byte = len(full_source_code_bytes)
        snippet = full_source_code_bytes[start_byte:end_byte]
        return snippet.decode("utf-8", errors="strict")
