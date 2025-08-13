"""Service layer for the MCP server implementation.

This module contains the business logic services that power the MCP server's
functionality. It provides two main services:

- CodeIndexService: Handles repository indexing and symbol querying
- SourceCodeFetchService: Manages source code retrieval operations

These services are designed as singletons and provide the core functionality
exposed through the MCP server's tools and resources.

Classes:
    CodeIndexService: Service for code repository indexing and symbol queries
    SourceCodeFetchService: Service for source code fetching operations
"""

from .code_index_service import CodeIndexService
from .llm_traverse_codebase import RepoAnalyseService
from .source_code_fetch_service import SourceCodeFetchService
