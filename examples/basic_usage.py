#!/usr/bin/env python3
"""Basic usage example demonstrating core CodeIndex functionality.

This example shows how to:
1. Create a sample C repository
2. Set up CodeIndexer with CrossRefIndex
3. Index the project and query for definitions/references
4. Persist index data to both JSON and SQLite formats
5. Load and verify saved index data

Run this example with:
    python examples/basic_usage.py
"""

import tempfile
from pathlib import Path

from code_index.index.code_query import FilterOption, QueryByName, QueryByNameRegex
from code_index.index.impl.cross_ref_index import CrossRefIndex
from code_index.index.persist import SingleJsonFilePersistStrategy, SqlitePersistStrategy
from code_index.indexer import CodeIndexer
from code_index.language_processor import CProcessor
from code_index.models import Function


def create_sample_c_project() -> Path:
    """Create a temporary directory with a sample C project."""
    # Create a temporary directory for our sample project
    project_dir = Path(tempfile.mkdtemp(prefix="code_index_example_"))

    # Create main.c with some sample functions
    main_c_content = """
#include <stdio.h>
#include <stdlib.h>

// Function declarations
int add(int a, int b);
int multiply(int a, int b);
void print_result(int result);

// Main function
int main() {
    int x = 5;
    int y = 3;

    int sum = add(x, y);
    print_result(sum);

    int product = multiply(x, y);
    print_result(product);

    return 0;
}

// Function definitions
int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

void print_result(int result) {
    printf("Result: %d\\n", result);
}
"""

    # Write the C file
    main_c_path = project_dir / "main.c"
    main_c_path.write_text(main_c_content)

    print(f"Created sample project at: {project_dir}")
    return project_dir


def setup_indexer() -> CodeIndexer:
    """Set up CodeIndexer with C processor and CrossRefIndex."""
    # Initialize the C language processor
    c_processor = CProcessor()

    # Create a CrossRefIndex for better cross-referencing capabilities
    cross_ref_index = CrossRefIndex()

    # Initialize the indexer with the C processor and CrossRefIndex
    indexer = CodeIndexer(processor=c_processor, index=cross_ref_index, store_relative_paths=True)

    print(f"Initialized indexer: {indexer}")
    return indexer


def index_and_query_project(indexer: CodeIndexer, project_dir: Path):
    """Index the project and demonstrate various query capabilities."""
    # Index the entire project
    indexer.index_project(project_dir)

    # Get overview of indexed functions
    all_functions = indexer.get_all_functions()
    print(f"\nIndexed {len(all_functions)} functions:")
    for func in all_functions:
        print(f"  - {func.name}")

    # 1. Find all definitions of the 'add' function
    definitions = indexer.find_definitions("add")
    print(f"\nFound {len(definitions)} definition(s) of 'add':")
    for defn in definitions:
        print(f"  Definition at {defn.location.file_path}:{defn.location.start_lineno}")

    # 2. Find all references to the 'add' function
    references = indexer.find_references("add")
    print(f"\nFound {len(references)} reference(s) to 'add':")
    for ref in references:
        print(f"  Reference at {ref.location.file_path}:{ref.location.start_lineno}")

    # 3. Get comprehensive information about a function
    add_function = Function(name="add")
    func_info = indexer.get_function_info(add_function)
    if func_info:
        print("\nComprehensive info for 'add':")
        print(f"  Definitions: {len(func_info.definitions)}")
        print(f"  References: {len(func_info.references)}")

    # 4. Use advanced queries through the index
    # Query by exact name
    name_query = QueryByName(name="multiply", type_filter=FilterOption.FUNCTION)
    query_results = indexer.index.handle_query(name_query)
    print("\nQuery results for 'multiply':")
    for result in query_results:
        print(f"  Function: {result.func_like.name}")
        print(f"  Definitions: {len(result.info.definitions)}")
        print(f"  References: {len(result.info.references)}")

    # 5. Query by regex pattern (find all functions ending with 't')
    regex_query = QueryByNameRegex(name_regex=r".*t$", type_filter=FilterOption.FUNCTION)
    regex_results = indexer.index.handle_query(regex_query)
    print("\nFunctions ending with 't':")
    for result in regex_results:
        print(f"  Function: {result.func_like.name}")


def persist_index_data(indexer: CodeIndexer, project_dir: Path):
    """Save the index data to disk using both JSON and SQLite formats."""
    # 1. Save to JSON format
    json_output_path = project_dir / "index.json"
    json_strategy = SingleJsonFilePersistStrategy()
    indexer.dump_index(json_output_path, json_strategy)
    print(f"\nSaved index to JSON: {json_output_path}")

    # 2. Save to SQLite format
    sqlite_output_path = project_dir / "index.db"
    sqlite_strategy = SqlitePersistStrategy()
    indexer.dump_index(sqlite_output_path, sqlite_strategy)
    print(f"Saved index to SQLite: {sqlite_output_path}")

    # Verify the files were created
    print("\nCreated files:")
    print(f"  JSON file size: {json_output_path.stat().st_size} bytes")
    print(f"  SQLite file size: {sqlite_output_path.stat().st_size} bytes")

    return json_output_path, sqlite_output_path


def load_and_verify_index(json_path: Path, sqlite_path: Path):
    """Demonstrate loading the saved index data and verify it works."""
    json_strategy = SingleJsonFilePersistStrategy()
    sqlite_strategy = SqlitePersistStrategy()

    # Create a new indexer instance and load from JSON
    new_indexer = CodeIndexer(processor=CProcessor(), index=CrossRefIndex())
    new_indexer.load_index(json_path, json_strategy)
    print(f"\nLoaded index from JSON: {len(new_indexer.get_all_functions())} functions")

    # Create another indexer and load from SQLite
    sqlite_indexer = CodeIndexer(processor=CProcessor(), index=CrossRefIndex())
    sqlite_indexer.load_index(sqlite_path, sqlite_strategy)
    print(f"Loaded index from SQLite: {len(sqlite_indexer.get_all_functions())} functions")

    # Verify the loaded data works
    loaded_definitions = new_indexer.find_definitions("main")
    print(f"Found {len(loaded_definitions)} definition(s) of 'main' in loaded index")


def main():
    """Main function demonstrating complete CodeIndex workflow."""
    print("=== CodeIndex Basic Usage Example ===\n")

    # Step 1: Create sample C project
    print("1. Creating sample C project...")
    project_dir = create_sample_c_project()

    # Step 2: Setup indexer
    print("\n2. Setting up CodeIndexer...")
    indexer = setup_indexer()

    # Step 3: Index project and query
    print("\n3. Indexing project and querying...")
    index_and_query_project(indexer, project_dir)

    # Step 4: Persist index data
    print("\n4. Persisting index data...")
    json_path, sqlite_path = persist_index_data(indexer, project_dir)

    # Step 5: Load and verify
    print("\n5. Loading and verifying index data...")
    load_and_verify_index(json_path, sqlite_path)

    print("\n=== Example completed successfully! ===")
    print(f"Project files available at: {project_dir}")


if __name__ == "__main__":
    main()
