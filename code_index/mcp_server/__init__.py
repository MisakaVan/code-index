"""Model Context Protocol (MCP) server implementation for CodeIndex.

This module provides a FastMCP-based server that exposes CodeIndex functionality
through the Model Context Protocol. It enables AI models to interact with code
repositories by providing tools for code indexing, symbol querying, and source
code fetching.

The server exposes the following capabilities:
    - Repository indexing for multiple programming languages (Python, C, C++)
    - Symbol querying with various search strategies
    - Source code fetching with support for full files, line ranges, and byte ranges
    - File path resolution utilities

Example:
    To run the MCP server:

    .. code-block:: python

        from code_index.mcp_server.server import main

        main()

Note:
    This module requires FastMCP and uses stdio transport for communication
    with MCP clients.
"""
