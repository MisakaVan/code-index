# Code Index Developer Instructions

**ALWAYS follow these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info provided here.**

Code Index is a Python 3.12+ repository-level source code indexer that utilizes tree-sitter to parse source code files and creates indices of function and method definitions and references. It supports Python, C, and C++ programming languages and provides both a CLI tool and MCP (Model Context Protocol) server for AI tool integration.

## Working Effectively

### Bootstrap and Environment Setup
1. **Install uv package manager** (REQUIRED):
   ```bash
   # Install uv - this may fail in restricted environments
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # OR if curl fails:
   python3 -m pip install uv
   export PATH=$HOME/.local/bin:$PATH
   ```

2. **Install dependencies**:
   ```bash
   # Primary approach with uv (may fail due to network restrictions)
   uv sync --group dev
   
   # Fallback approach with pip
   pip install -e .
   # For development dependencies (may fail due to network restrictions):
   pip install pytest pytest-asyncio ruff pre-commit mypy sphinx sphinx-book-theme
   ```

3. **Verify installation**:
   ```bash
   python3 -m code_index --help  # Should complete in ~0.5 seconds
   ```

### Build and Test
- **NEVER CANCEL builds or tests** - All operations complete quickly (under 1 second for most tasks)
- **Basic functionality test**: `python3 examples/basic_usage.py` -- takes ~0.5 seconds
- **Self-indexing test**: `python3 -m code_index . -l python` -- takes ~0.8 seconds, indexes 1135+ symbols
- **Language support test**: 
  - Python: `python3 -m code_index test_data/python -l python` -- ~0.4 seconds
  - C: `python3 -m code_index test_data/c -l c` -- ~0.4 seconds  
  - C++: `python3 -m code_index test_data/cpp -l cpp` -- ~0.4 seconds

### Testing Infrastructure
- **Full test suite**: `uv run pytest tests/` -- NEVER CANCEL: May take 2-5 minutes if all dependencies available
- **Note**: Test suite may fail due to missing dependencies from network restrictions
- **Basic validation**: `find . -name "*.py" -exec python3 -m py_compile {} \;` -- syntax validation works reliably
- **Manual testing**: Use examples and CLI commands for validation when automated tests unavailable

### Pre-commit and Code Quality
- **Run quality checks**: `uv run pre-commit run --all-files` -- NEVER CANCEL: Takes 1-3 minutes
- **Manual validation when tools unavailable**:
  ```bash
  # Python syntax check
  python3 -m py_compile file.py
  # YAML validation  
  python3 -c "import yaml; yaml.safe_load(open('file.yaml'))"
  ```

### Documentation
- **Build documentation**: NEVER CANCEL: Takes 2-4 minutes
  ```bash
  cd docs
  uv run sphinx-build -a -v ./source ./build/html
  ```
- **Fallback if dependencies missing**: Review existing docs in `docs/source/` directory

## CLI Tool Usage

### Basic Commands
```bash
# Index a Python repository (default)
python3 -m code_index /path/to/repo

# Index with specific language
python3 -m code_index /path/to/repo -l python|c|cpp

# Specify output format and location
python3 -m code_index /path/to/repo --dump-type json|sqlite -o output_file

# Help and usage
python3 -m code_index --help
```

### MCP Server
```bash
# Start MCP server for AI tool integration
python3 -m code_index.mcp_server.server

# Test MCP server import
python3 -c "from code_index.mcp_server.server import main; print('MCP server works')"
```

## Validation Scenarios

### Core Functionality Test
**ALWAYS validate changes by running this complete user scenario:**

1. **Index the current repository**:
   ```bash
   python3 -m code_index . -l python --output /tmp/test_index.json
   ```
   - Should complete in ~0.8 seconds
   - Should index 1135+ symbols
   - Should create JSON file ~4.8MB in size

2. **Test basic usage example**:
   ```bash
   python3 examples/basic_usage.py
   ```
   - Should complete in ~0.5 seconds
   - Should create temporary C project and index it
   - Should demonstrate JSON and SQLite export

3. **Test multi-language support**:
   ```bash
   python3 -m code_index test_data/python -l python
   python3 -m code_index test_data/c -l c  
   python3 -m code_index test_data/cpp -l cpp
   ```
   - Each should complete in ~0.4 seconds
   - Should process test data successfully

4. **Test MCP server startup**:
   ```bash
   timeout 3 python3 -m code_index.mcp_server.server
   ```
   - Should show FastMCP banner and start successfully

## Important Project Structure

### Key Directories
- `code_index/` - Main package source code
- `tests/` - Test suite (pytest-based, may require full environment)
- `examples/` - Working usage examples (always test these)
- `docs/` - Sphinx documentation source
- `test_data/` - Sample code for testing different languages
- `scripts/explore_tree_sitter/` - Tree-sitter debugging utilities

### Configuration Files
- `pyproject.toml` - Main project configuration and dependencies
- `ruff.toml` - Code formatting and linting configuration
- `.pre-commit-config.yaml` - Pre-commit hooks configuration
- `uv.lock` - Dependency lock file for uv package manager

### Entry Points
- `python3 -m code_index` - CLI tool main entry point
- `python3 -m code_index.mcp_server.server` - MCP server entry point
- `code-index` script (when installed) - Alternative CLI entry point
- `code-index-mcp-server` script (when installed) - Alternative MCP server entry point

## Network and Environment Limitations

### Known Issues
- **Network timeouts** may prevent installation of development dependencies
- **uv sync** may fail due to network restrictions - use `pip install -e .` as fallback
- **Testing dependencies** (pytest, ruff, sphinx) may not install in restricted environments
- **Pre-commit hooks** may not work without full dependency installation

### Reliable Workarounds
- Use `pip install -e .` for basic functionality (core dependencies work reliably)
- Use manual syntax validation: `python3 -m py_compile file.py`
- Test functionality using examples and CLI commands rather than automated test suite
- Focus on core functionality validation which works without network access

## Common Tasks

### After Making Changes
1. **Always test core functionality**: Run the validation scenarios above
2. **Check syntax**: `find . -name "*.py" -exec python3 -m py_compile {} \;`
3. **Test examples**: `python3 examples/basic_usage.py`
4. **Verify CLI**: `python3 -m code_index --help`
5. **Run quality checks** (if available): `uv run pre-commit run --all-files`

### Tree-sitter Development
- Use scripts in `scripts/explore_tree_sitter/` to understand AST structures
- Example: `python3 scripts/explore_tree_sitter/inspect_python_ast.py`

### Debugging
- Check logs in `code_index/utils/logger.py` 
- Set `CODE_INDEX_LOG_LEVEL=DEBUG` in environment for verbose output
- Warning messages about "Unexpected function node type" are normal

## Project Overview

### Core Components
- **Language Processors**: Parse code using tree-sitter (Python, C, C++)
- **Index System**: Store and query function definitions and references  
- **Persistence**: JSON and SQLite export/import capabilities
- **MCP Integration**: Model Context Protocol server for AI tools
- **CLI Interface**: Command-line tool for batch processing

### Supported Languages
- **Python**: Full support for functions, methods, classes
- **C**: Functions and declarations
- **C++**: Functions, methods, classes (basic support)

### Output Formats
- **JSON**: Human-readable, portable format
- **SQLite**: Database format for efficient querying

## MCP Integration

**For MCP-related development tasks:**

### Core MCP Concept
The Model Context Protocol (MCP) is an open standard that enables AI applications to securely connect to external data sources, tools, and services. Code Index implements an MCP server to provide code analysis capabilities to AI tools.

### MCP Documentation
- **MCP Protocol**: https://modelcontextprotocol.io/llms.txt
- **FastMCP Framework**: https://gofastmcp.com/llms.txt

### MCP Server Features
- **Repository indexing**: Setup and manage code indices
- **Symbol querying**: Find function definitions and references
- **Source code fetching**: Retrieve code by line or byte ranges
- **Cross-referencing**: Navigate between definitions and usages
