MCP integration
===============

Integrating the functionality of code-index with the MCP (ModelContextProtocol) enables LLMs/agents to efficiently query and retrieve code definitions, references, and other relevant information from indexed projects.

MCP Server
----------

.. automodule:: code_index.mcp_server.server
   :members:
   :show-inheritance:


Services
~~~~~~~~

Services that act as backend for MCP requests, providing access to indexed code data and source code fetching.

.. autoclass:: code_index.mcp_server.services.CodeIndexService
    :members:
    :show-inheritance:

.. autoclass:: code_index.mcp_server.services.SourceCodeFetchService
    :members:
    :show-inheritance:
