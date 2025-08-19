MCP integration
===============

Integrating the functionality of code-index with the MCP (ModelContextProtocol) enables LLMs/agents to efficiently query and retrieve code definitions, references, and other relevant information from indexed projects.


MCP Protocol
------------

The Model Context Protocol (MCP) is an open standard that enables AI applications to securely connect to external data sources, tools, and services. It follows a client-server architecture where an AI application (the MCP host) establishes connections to one or more MCP servers through dedicated MCP clients.

Key concepts of MCP include:

- **MCP Host**: The AI application that coordinates multiple MCP clients (e.g., Claude Desktop, Visual Studio Code)
- **MCP Client**: A component that maintains a connection to an MCP server and retrieves context for the host
- **MCP Server**: A program that provides context, tools, and resources to MCP clients

MCP operates on two layers:

- **Data Layer**: Implements JSON-RPC 2.0 protocol for message exchange, lifecycle management, and core primitives like tools, resources, and prompts
- **Transport Layer**: Manages communication channels and authentication, supporting both stdio (local processes) and HTTP (remote servers) transports

This architecture allows AI applications to extend their capabilities beyond static training data by accessing real-time information, executing functions, and interacting with various systems in a standardized way.

For detailed information about the MCP architecture, see the official documentation at https://modelcontextprotocol.io/docs/learn/architecture

MCP Server Process Model
------------------------

MCP servers operate as independent processes, separate from the AI applications that use them. This separation provides several benefits including process isolation, language independence, and deployment flexibility.

Process Architecture
~~~~~~~~~~~~~~~~~~~~

- **Separate Process Execution**: MCP servers run as standalone processes, either locally on the same machine as the AI application or remotely on different servers
- **No Direct Integration**: There is no direct code-level integration between MCP servers and AI applications/agents
- **Process Isolation**: Each MCP server runs in its own memory space, providing fault tolerance and security boundaries

Communication Protocols
~~~~~~~~~~~~~~~~~~~~~~~~

MCP servers communicate with AI applications through text-based protocols over standard communication channels:

- **STDIO Transport**: For local servers, communication occurs through standard input/output streams (stdin/stdout)
- **HTTP Transport**: For remote servers, communication uses HTTP requests and responses with JSON payloads
- **JSON-RPC 2.0**: All communication follows the JSON-RPC 2.0 specification for message formatting and protocol semantics

Text-Based Interface
~~~~~~~~~~~~~~~~~~~~

- **Input**: MCP servers receive JSON-RPC requests as text through their configured transport layer
- **Processing**: The server processes the request using its internal logic and data sources
- **Output**: Results are returned as JSON-RPC responses in text format through the same transport channel
- **Stateless Operation**: Each request/response cycle is independent, allowing for scalable and reliable operation

This design allows MCP servers to be implemented in any programming language, deployed anywhere, and integrated with any MCP-compatible AI application without requiring specific runtime dependencies or direct code coupling.

Code Repository Analysis with MCP
---------------------------------

The code-index MCP server provides LLMs and AI agents with capabilities for analyzing and exploring codebases. By encapsulating code indexing and querying functionality within the MCP protocol, these tools become portable across different AI platforms and can be integrated into various workflows.

Security Analysis Capabilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Vulnerability Detection**: Help LLMs inspect each function and find potential security vulnerabilities
- **Data Flow Analysis**: Trace how data flows through functions and modules to identify potential exploit vectors or information leakage paths
- **Attack Surface Mapping**: Identify entry points, external interfaces, and user input handling functions that could be targeted
- **Dependency Analysis**: Examine how external libraries and dependencies are used throughout the codebase

Code Exploration and Understanding
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Definition Discovery**: Locate function, class, and variable definitions across multiple files and projects
- **Reference Tracking**: Follow how code elements are used and referenced throughout the codebase
- **Call Graph Analysis**: Understand the relationships and dependencies between different parts of the code
- **Pattern Recognition**: Search for specific coding patterns, architectural decisions, or implementation approaches

MCP Portability Advantage
~~~~~~~~~~~~~~~~~~~~~~~~~~

The key benefit of wrapping these capabilities in MCP is **portability and reusability**. Once implemented as an MCP server, these code analysis tools can be:

- **Injected into any MCP-compatible AI agent** (Claude Desktop, custom agents, etc.)
- **Used across different development environments** without reimplementation
- **Shared between teams and projects** with consistent interfaces
- **Combined with other MCP servers** to create comprehensive analysis pipelines
- **Integrated into existing workflows** without platform-specific adaptations

This standardized approach means that a security analyst using Claude Desktop, a developer using a custom AI agent, or an automated CI/CD pipeline can all leverage the same code analysis capabilities through their respective MCP-enabled environments.

MCP Server Implementation
-------------------------

The CodeIndex MCP Server helps LLMs run code-indexing on projects, and provides interface for querying indexed symbols, source code fetching, and other code-related operations. These functionalities can be used by any MCP-compatible AI application or agent.

All MCP server services are thread-safe, enabling multiple AI agents to safely analyze repositories in parallel and update the code index concurrently without race conditions.

There is a usage example in the ``examples/code_index_agent.py`` file, which uses ``LangChain`` framework to build an agent with mcp tools.

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
