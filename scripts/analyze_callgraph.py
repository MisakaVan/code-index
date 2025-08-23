#!/usr/bin/env python3
"""
Call graph analysis tool for code repositories.
"""

import argparse
import sys
from pathlib import Path

from code_index.mcp_server.services import CodeIndexService, GraphAnalyzerService


def analyze_callgraph(repo_path: Path, language: str, cache_strategy: str = "json") -> int:
    """
    Analyze the call graph of a code repository.

    Args:
        repo_path: Path to the repository to analyze
        language: Programming language (e.g., 'c', 'cpp', 'python')
        cache_strategy: Cache strategy ('json' or 'sqlite')

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if not repo_path.exists():
        print(f"Error: Repository not found at {repo_path}")
        return 1

    print(f"Analyzing {language.upper()} codebase at: {repo_path}")
    print("=" * 60)

    # Initialize services
    code_index_service = CodeIndexService.get_instance()
    graph_analyzer_service = GraphAnalyzerService.get_instance()

    try:
        # Setup repository index
        print("Setting up repository index...")
        code_index_service.setup_repo_index(repo_path, language, cache_strategy)

        # Get basic indexing information
        all_functions = code_index_service.indexer.get_all_functions()
        print(f"Total functions indexed: {len(all_functions)}")

        # Get call graph overview
        print("\nGenerating call graph overview...")
        overview = graph_analyzer_service.get_call_graph_overview()

        # Display statistics
        print("\nCall Graph Statistics:")
        print(f"  Nodes (definitions): {overview.stats.num_nodes}")
        print(f"  Edges (calls): {overview.stats.num_edges}")
        print(f"  Unresolved calls: {overview.stats.unresolved_calls}")
        print(f"  Build time: {overview.stats.build_seconds:.4f} seconds")

        # Display SCC information
        print("\nStrongly Connected Components (SCCs):")
        print(f"  Total SCCs: {overview.scc_overview.count}")

        # Show largest SCCs
        largest_sccs = sorted(overview.scc_overview.details, key=lambda x: x.size, reverse=True)[:5]
        print("  Top 5 largest SCCs:")
        for i, scc in enumerate(largest_sccs):
            print(f"    {i + 1}. SCC {scc.scc_id}: {scc.size} nodes")
            if scc.nodes:
                # Show a few example functions in this SCC
                example_funcs = []
                for node in scc.nodes[:3]:  # Show first 3 functions
                    file_name = Path(node.location.file_path).name
                    # Extract function name from the file (this is approximate)
                    example_funcs.append(f"{file_name}:{node.location.start_lineno}")
                if example_funcs:
                    print(f"       Examples: {', '.join(example_funcs)}")

        # Display entry points
        print("\nEntry Points (functions with no callers):")
        print(f"  Total entry points: {len(overview.entrypoints)}")
        if overview.entrypoints:
            print("  Examples:")
            for i, entry in enumerate(overview.entrypoints[:5]):
                file_name = Path(entry.location.file_path).name
                print(f"    {i + 1}. {file_name}:{entry.location.start_lineno}")

        # Display end points
        print("\nEnd Points (functions that call no others):")
        print(f"  Total end points: {len(overview.endpoints)}")
        if overview.endpoints:
            print("  Examples:")
            for i, endpoint in enumerate(overview.endpoints[:5]):
                file_name = Path(endpoint.location.file_path).name
                print(f"    {i + 1}. {file_name}:{endpoint.location.start_lineno}")

        # Show some function examples by file
        print("\nFunction Distribution by File:")
        file_func_count = {}
        for func in all_functions:
            definitions = code_index_service.index.get_definitions(func)
            for defn in definitions:
                file_name = Path(defn.location.file_path).name
                file_func_count[file_name] = file_func_count.get(file_name, 0) + 1

        # Show top files by function count
        top_files = sorted(file_func_count.items(), key=lambda x: x[1], reverse=True)[:10]
        for file_name, count in top_files:
            print(f"  {file_name}: {count} functions")

        # Get topological order
        print("\nTopological Analysis:")
        topo_order = graph_analyzer_service.get_topological_order()
        print(f"  Functions in topological order: {len(topo_order)}")

        print("\nAnalysis complete!")
        return 0

    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback

        traceback.print_exc()
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze call graph of code repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze Lua C codebase
  python analyze_callgraph.py test_data/lua c

  # Analyze a Python project
  python analyze_callgraph.py /path/to/python/project python

  # Use SQLite cache strategy
  python analyze_callgraph.py test_data/lua c --cache sqlite
        """.strip(),
    )

    parser.add_argument("repo_path", type=Path, help="Path to the repository to analyze")

    parser.add_argument(
        "language", choices=["c", "cpp", "python"], help="Programming language of the repository"
    )

    parser.add_argument(
        "--cache",
        choices=["json", "sqlite"],
        default="json",
        help="Cache strategy to use (default: json)",
    )

    args = parser.parse_args()

    return analyze_callgraph(args.repo_path, args.language, args.cache)


if __name__ == "__main__":
    sys.exit(main())
