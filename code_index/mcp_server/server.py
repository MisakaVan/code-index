"""FastMCP server implementation for CodeIndex.

This module implements the main MCP server using the FastMCP framework. It provides
tools and resources for code repository analysis, including:

- Code indexing and symbol querying through CodeIndexService
- Source code fetching with multiple access patterns (full file, line ranges, byte ranges)
- File path resolution utilities for repository navigation

The server exposes MCP resources for:
    - Full source code retrieval: ``sourcecode://{file_path}``


The server exposes MCP tools for:
    - Repository setup and indexing
    - Symbol querying with flexible search criteria
    - File path resolution within repositories
    - Fetching source code snippets by line or byte ranges


Example:
    Run the server directly:

    .. code-block:: bash

        python -m code_index.mcp_server.server

    Or run via fastmcp CLI:

    .. code-block:: bash

        uv run fastmcp run code_index/mcp_server/server.py:mcp --project .


Note:
    The server uses stdio transport and is designed to be used with MCP-compatible
    AI models and tools.
"""

from pathlib import Path
from typing import Literal

from fastmcp import Context, FastMCP

from code_index.index.code_query import CodeQuery, CodeQueryResponse
from code_index.mcp_server.models import AllSymbolsResponse
from code_index.mcp_server.services import CodeIndexService, SourceCodeFetchService

mcp = FastMCP("CodeIndexService")
"""FastMCP server instance for CodeIndexService.

This instance can be exported to and run by the FastMCP cli.
"""


# register source code fetching as FastMCP resources


def resolve_file_path(repo_path: Path, file_path: Path) -> Path:
    """Resolve the full path of a file within a repository.

    Args:
        repo_path: The path to the repository.
        file_path: Either an absolute path, or a path relative to the repository.

    Returns:
        The full path to the file.

    """
    return (repo_path / file_path).resolve().absolute()


async def fetch_source_code(file_path: str) -> str:
    """Fetch the full source code of a file.

    Args:
        file_path: The path to the file to fetch, in the format 'sourcecode://{file_path}'.

    Note:
        In case the relative path may not be addressed correctly, it is recommended to resolve the
        absolute path using `resolve_file_path` before calling this function.

    Returns:
        The content of the file as a string.

    """
    path = Path(file_path)
    service = SourceCodeFetchService.get_instance()
    return await service.fetch_full_source_code(path)


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

    Note:
        In case the relative path may not be addressed correctly, it is recommended to resolve the
        absolute path using `resolve_file_path` before calling this function.

    Returns:
        The content of the specified lines as a string.

    """
    if start_line > end_line:
        raise ValueError(f"start_line ({start_line}) cannot be greater than end_line ({end_line}).")

    service = SourceCodeFetchService.get_instance()
    return await service.fetch_by_lineno_range(file_path, start_line, end_line, ctx)


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

    Note:
        In case the relative path may not be addressed correctly, it is recommended to resolve the
        absolute path using `resolve_file_path` before calling this function.

    Returns:
        The content of the specified byte range as a string.

    """
    if start_byte >= end_byte:
        raise ValueError(
            f"start_byte ({start_byte}) cannot be greater than or equal to end_byte ({end_byte})."
        )

    service = SourceCodeFetchService.get_instance()
    return await service.fetch_by_byte_range(file_path, start_byte, end_byte, ctx)


def setup_repo_index(
    repo_path: Path,
    language: Literal["python", "c", "cpp"],
    strategy: Literal["json", "sqlite", "auto"] = "auto",
) -> None:
    """Set up the indexer for a repository.

    This initializes the indexer with the specified language processor. Then it indexes the repository using the
    indexer. If any cached index data exists, it will be loaded into the indexer.

    Args:
        repo_path: The path to the repository to index.
        language: The programming language of the repository (e.g., 'python', 'c', 'cpp').
        strategy: The persistence strategy for the index data ('json', 'sqlite', or 'auto'). This will determine in
            which format the index data is stored to or loaded from cache.

            - 'auto': Try to select the corresponding strategy according to the format of the cached index data. If
                no cached data exists, it will default to 'sqlite'.
            - 'json': Use JSON format for the index data.
            - 'sqlite': Use SQLite format for the index data.

    """
    return CodeIndexService.get_instance().setup_repo_index(
        repo_path=repo_path,
        language=language,
        strategy=strategy,
    )


def query_symbol(query: CodeQuery) -> CodeQueryResponse:
    """Query the index for symbols matching the given query.

    `symbol` here refers to a `Function-like` entity, which can be anything with its definition or call site
    like a function, class constructor, method. There are multiple ways to query symbols, such as by name,
    by name regex, etc.

    Args:
        query: The query object containing search parameters.

    Returns:
        A response object containing the results of the query. There can be multiple results, each containing the
        location of the symbol, its name, and other relevant information.
    """
    return CodeIndexService.get_instance().query_symbol(query)


def get_all_symbols() -> AllSymbolsResponse:
    """Get a sorted list of all unique symbols in the index.

    Returns:
        A response object containing a sorted list of all symbol names.
    """
    return CodeIndexService.get_instance().get_all_symbols()


# This is a workaround for sphinx autodoc to recognize the docstrings of the undecorated functions above
# Now register the functions as FastMCP tools and resources

mcp.tool(
    name="resolve_file_path",
    annotations={"readOnlyHint": True},
)(resolve_file_path)

mcp.resource(
    "sourcecode://{file_path*}",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)(fetch_source_code)

mcp.tool(
    name="fetch_source_code_by_lineno_range",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)(fetch_source_code_by_lineno_range)

mcp.tool(
    name="fetch_source_code_by_byte_range",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)(fetch_source_code_by_byte_range)

mcp.tool(name="setup_repo_index")(setup_repo_index)

mcp.tool("query_symbol")(query_symbol)

mcp.tool("get_all_symbols", annotations={"readOnlyHint": True})(get_all_symbols)


def main():
    """Main entry point for the MCP server.

    Starts the FastMCP server using stdio transport for communication
    with MCP clients.
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
