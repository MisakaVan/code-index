# Copilot Instructions

## Project Overview

`uv` is used as the primary package manager for this project, and it is recommended to use `uv run` to execute commands. This ensures that the correct environment is activated and dependencies are managed properly.

## Tests

Before and after making changes, it is recommended to run the tests to ensure that everything is functioning correctly. You can run the tests using the following command:

```bash
uv run pytest tests/
```

which will launch the whole test suite. If you want to run a specific test file, you can use:

```bash
uv run pytest tests/test_file.py
```

## Pre-commit Hook

```bash
uv run pre-commit run --all-files
```

This will format the code (and also runs the tests) to ensure that everything is in order before committing changes. It is recommended to run this command before you finish a job.


## What is MCP

**1. Core Concept: What is MCP?**
* **Summary**: The Model Context Protocol (MCP) is an emerging open standard designed to give AI models (like yourself) a unified and secure way to interact with external tools, data sources, and systems. Think of it as "USB-C for AI tools," allowing a model to call functions, query databases, and read/write files, enabling it to go beyond its static training data.
* **Official LLM-friendly Docs**: `https://modelcontextprotocol.io/llms.txt`

**2. My Development Framework: FastMCP**
* **Context**: I am primarily using Python and a high-performance framework called `FastMCP`. Its design is inspired by FastAPI, making it easy to use.
* **FastMCP Project & Docs**: `https://gofastmcp.com/llms.txt`

**Your Task**:
Before you answer any of my specific programming questions about the mcp development, it is **essential** that you first review the content at the URLs provided above. This will be the foundation for all our communication.

Please let me know when you are ready, and we can begin. For example, I might ask, "How can I create a tool using FastMCP that takes a string parameter and returns its uppercase version?"
