"""Code indexing service for the MCP server.

This module provides the CodeIndexService class, which serves as the main backend
service for code repository indexing and symbol querying operations in the MCP server.

The service handles:
    - Repository setup and indexing with language-specific processors
    - Persistent caching of index data (JSON or SQLite formats)
    - Symbol querying with flexible search criteria
    - Automatic cache management and loading

The service supports multiple programming languages (Python, C, C++) and provides
intelligent caching strategies to optimize performance across sessions.

Classes:
    CodeIndexService: Singleton service for code indexing and querying operations

Example:
    Basic usage of the service:

    .. code-block:: python

        service = CodeIndexService.get_instance()
        service.setup_repo_index(
            repo_path=Path("/path/to/repo"), language="python", strategy="auto"
        )
        results = service.query_symbol(query_object)

Note:
    This service is designed as a singleton to maintain state across MCP operations
    and ensure efficient resource usage.
"""

from pathlib import Path
from typing import Literal, Optional

from code_index.index.base import PersistStrategy
from code_index.index.code_query import CodeQuery, CodeQueryResponse
from code_index.index.impl.cross_ref_index import CrossRefIndex
from code_index.index.persist import SingleJsonFilePersistStrategy, SqlitePersistStrategy
from code_index.indexer import CodeIndexer
from code_index.language_processor import language_processor_factory
from code_index.utils.logger import logger


class CodeIndexService:
    """MCP service backend for code-index."""

    _instance: Optional["CodeIndexService"] = None

    @staticmethod
    def get_instance() -> "CodeIndexService":
        """Get the singleton instance of CodeIndexService."""
        if CodeIndexService._instance is None:
            CodeIndexService._instance = CodeIndexService()
        return CodeIndexService._instance

    def __init__(self):
        self._indexer: CodeIndexer | None = None

    def _clear_indexer(self) -> None:
        """Clear the current indexer instance."""
        if self._indexer is not None:
            logger.info("Clearing current indexer instance.")
            self._indexer = None
        else:
            logger.warning("No indexer instance to clear.")

    @staticmethod
    def _get_cache_config(
        repo_path: Path, strategy: Literal["json", "sqlite", "auto"]
    ) -> tuple[Path, PersistStrategy]:
        """Get the cache file path for a repository."""
        cache_dir = repo_path / ".code_index.cache"
        strategy_config_mapping = {
            "json": (cache_dir / "index.json", SingleJsonFilePersistStrategy()),
            "sqlite": (cache_dir / "index.sqlite", SqlitePersistStrategy()),
        }

        match strategy:
            case "json" | "sqlite":
                # Return the specified strategy and its corresponding cache file path
                return strategy_config_mapping.get(strategy)
            case "auto":
                # Try to determine the strategy based on existing cache files
                for key, (path, strategy_instance) in strategy_config_mapping.items():
                    if path.exists():
                        return path, strategy_instance
                # If no cache files exist, default to SQLite
                return strategy_config_mapping["sqlite"]
            case _:
                raise ValueError(f"Unsupported cache strategy: {strategy}")

    def setup_repo_index(
        self,
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
        if self._indexer is not None:
            logger.warning("Indexer is already initialized, reinitializing...")
        l = language_processor_factory(language)
        assert l is not None, f"No language processor found for '{language}'"
        self._indexer = CodeIndexer(processor=l, index=CrossRefIndex())

        # try to load existing index data
        cache_path, persist_strategy = self._get_cache_config(repo_path, strategy)
        if cache_path.exists():
            logger.info(f"Loading existing index data from {cache_path}")
            try:
                self._indexer.load_index(cache_path, persist_strategy)
            except Exception as e:
                logger.error(f"Failed to load index data: {e}")
                raise RuntimeError(f"Failed to load index data from {cache_path}: {e}")
        else:
            logger.info(f"No existing index data found at {cache_path}, starting fresh.")
            try:
                self._indexer.index_project(project_path=repo_path)
            except Exception as e:
                logger.error(f"Failed to index project: {e}")
                raise RuntimeError(f"Failed to index project at {repo_path}: {e}")

            # dump the index data to cache
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                self._indexer.dump_index(cache_path, persist_strategy)
                logger.info(f"Index data persisted to {cache_path}")
            except Exception as e:
                logger.error(f"Failed to persist index data: {e}")
                raise RuntimeError(f"Failed to persist index data to {cache_path}: {e}")

        # index the repository
        logger.info(f"Indexing repository at {repo_path} with language '{language}'")

    def query_symbol(self, query: CodeQuery) -> CodeQueryResponse:
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
        if self._indexer is None:
            raise RuntimeError("Indexer is not initialized. Call setup_repo_index first.")

        logger.info(f"Querying index with: {query}")

        index = self._indexer.index
        return CodeQueryResponse(results=index.handle_query(query))
