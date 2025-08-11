Basic Usage
===========

This guide shows you how to get started with CodeIndex for basic code analysis tasks. The complete working example is available at ``examples/basic_usage.py``.

Overview
--------

The basic usage example demonstrates the core functionality of CodeIndex:

1. **Creating a Sample C Repository** - Sets up a temporary project with a main.c file containing function declarations, definitions, and calls
2. **Setting Up CodeIndexer** - Configures the indexer with a C processor and CrossRefIndex for cross-referencing capabilities
3. **Indexing and Querying** - Processes the project and demonstrates various query methods for finding definitions and references
4. **Persisting Data** - Saves index data to both JSON and SQLite formats
5. **Loading and Verification** - Loads saved data and verifies functionality

Key Features Demonstrated
-------------------------

Project Setup
~~~~~~~~~~~~~

The example creates a sample C project with functions that have both declarations and definitions, allowing demonstration of:

- Function definition detection
- Function reference tracking
- Cross-referencing between declarations and calls

Indexer Configuration
~~~~~~~~~~~~~~~~~~~~~

Shows how to set up CodeIndexer with:

- **CProcessor**: Language processor for C code parsing using tree-sitter
- **CrossRefIndex**: Advanced index implementation for better cross-referencing
- **Relative paths**: Configuration to store file paths relative to project root

Query Capabilities
~~~~~~~~~~~~~~~~~~

Demonstrates multiple ways to query the indexed data:

- **find_definitions()**: Find all definition locations for a function name
- **find_references()**: Find all reference/call locations for a function name
- **get_function_info()**: Get comprehensive information including both definitions and references
- **QueryByName**: Advanced exact name queries with type filtering
- **QueryByNameRegex**: Pattern-based searching using regular expressions

Persistence Options
~~~~~~~~~~~~~~~~~~~

Shows how to save and load index data using different strategies:

- **JSON Format**: Human-readable format using SingleJsonFilePersistStrategy
- **SQLite Format**: Database format using SqlitePersistStrategy
- **Load Verification**: Creating new indexer instances and loading saved data

Running the Example
-------------------

To run the complete example:

.. code-block:: bash

    cd /path/to/CodeIndex
    python examples/basic_usage.py

Next Steps
----------

After running this example, you can:

- Modify the C code to add more functions and see how indexing changes
- Try different query patterns and regex searches
- Experiment with other language processors (Python, C++)
- Explore the generated JSON and SQLite files to understand the data format
- Integrate similar functionality into your own projects

For more advanced usage patterns, see the other examples in the ``examples/`` directory.
