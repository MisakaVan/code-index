"""FastMCP server implementation for CodeIndex.

This module implements the main MCP server using the FastMCP framework. It provides
tools and resources for code repository analysis, including:

- Code indexing and symbol querying through CodeIndexService
- Source code fetching with multiple access patterns (full file, line ranges, byte ranges)
- File path resolution utilities for repository navigation

The server exposes MCP tools for:
    - Repository setup and indexing
    - Symbol querying with flexible search criteria
    - File path resolution within repositories

The server exposes MCP resources for:
    - Full source code retrieval: ``sourcecode://{file_path}``
    - Line-based code snippets: ``sourcecode://{file_path}/?start_line={start}&end_line={end}``
    - Byte-based code snippets: ``sourcecode://{file_path}/?start_byte={start}&end_byte={end}``

Example:
    Run the server directly:

    .. code-block:: bash

        python -m code_index.mcp_server.server

    Or import and run programmatically:

    .. code-block:: python

        from code_index.mcp_server.server import main
        main()

Note:
    The server uses stdio transport and is designed to be used with MCP-compatible
    AI models and tools.
"""

from pathlib import Path

from fastmcp import FastMCP, Context

from code_index.mcp_server.services import CodeIndexService, SourceCodeFetchService

mcp = FastMCP("CodeIndexService")


# register source code fetching as FastMCP resources


@mcp.tool("resolve_file_path")
def resolve_file_path(repo_path: Path, file_path: Path) -> Path:
    """Resolve the full path of a file within a repository.

    Args:
        repo_path: The path to the repository.
        file_path: Either an absolute path, or a path relative to the repository.

    Returns:
        The full path to the file.

    """
    return (repo_path / file_path).resolve().absolute()


@mcp.resource(
    "sourcecode://{file_path*}", annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def fetch_source_code(file_path: str) -> str:
    """Fetch the full source code of a file.

    Args:
        file_path: The path to the file to fetch, in the format 'sourcecode://{file_path}'.

    Returns:
        The content of the file as a string.

    """
    path = Path(file_path)
    service = SourceCodeFetchService.get_instance()
    return await service.fetch_full_source_code(path)


@mcp.tool(
    "fetch_source_code_by_lineno_range",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def fetch_source_code_by_lineno_range(
    file_path: Path,
    start_line: int,
    end_line: int,
    ctx: Context,
) -> str:
    """Fetch a snippet of source code from a file by line range.

    Args:
        file_path: The path to the file to fetch.
        start_line: The starting line number (1-based, inclusive).
        end_line: The ending line number (1-based, inclusive).
        ctx: FastMCP context

    Returns:
        The content of the specified lines as a string.

    """
    if start_line > end_line:
        raise ValueError(f"start_line ({start_line}) cannot be greater than end_line ({end_line}).")

    service = SourceCodeFetchService.get_instance()
    return await service.fetch_by_lineno_range(file_path, start_line, end_line, ctx)


@mcp.tool(
    "fetch_source_code_by_byte_range",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def fetch_source_code_by_byte_range(
    file_path: Path,
    start_byte: int,
    end_byte: int,
    ctx: Context,
) -> str:
    """Fetch a snippet of source code from a file by byte range.

    Args:
        file_path: The path to the file to fetch.
        start_byte: The starting byte offset (0-based, inclusive).
        end_byte: The ending byte offset (0-based, exclusive).
        ctx: FastMCP context

    Returns:
        The content of the specified byte range as a string.

    """
    if start_byte >= end_byte:
        raise ValueError(
            f"start_byte ({start_byte}) cannot be greater than or equal to end_byte ({end_byte})."
        )

    service = SourceCodeFetchService.get_instance()
    return await service.fetch_by_byte_range(file_path, start_byte, end_byte, ctx)


# CodeIndex Service methods
mcp.tool(CodeIndexService.get_instance().setup_repo_index)
mcp.tool(CodeIndexService.get_instance().query_symbol)


def main():
    """Main entry point for the MCP server.

    Starts the FastMCP server using stdio transport for communication
    with MCP clients.
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
