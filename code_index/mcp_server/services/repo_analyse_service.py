"""Help LLM traverse codebase with todolist.

This module provides a service to help LLMs (Large Language Models) traverse a codebase
by symbol/definition, using a todolist structure to manage tasks.
"""

from __future__ import annotations

from enum import Enum
from threading import RLock

from code_index.analyzer.models import Direction
from code_index.models import Definition, LLMNote, PureDefinition, Symbol, SymbolDefinition
from code_index.utils.logger import logger

from .code_index_service import CodeIndexService
from .graph_analyzer_service import GraphAnalyzerService
from .todo_list import TodoList


class TraversePolicy(Enum):
    """Policy for traversing definitions when setting up todo list."""

    ARBITRARY = "arbitrary"
    """Traverse in arbitrary order (original behavior)."""

    BFS_CALLEE_TO_CALLER = "bfs_callee_to_caller"
    """BFS traversal from deepest dependencies to entry points."""

    BFS_CALLER_TO_CALLEE = "bfs_caller_to_callee"
    """BFS traversal from entry points to deepest dependencies."""


class RepoAnalyseService:
    """Service to help LLMs traverse a codebase by symbol/definition.

    This service uses a TodoList to manage tasks related to codebase traversal.
    It allows adding tasks, yielding tasks for processing, and submitting results.

    - iterate all definitions and let llm generate a description for each
    """

    _instance: RepoAnalyseService | None = None
    _instance_lock = RLock()  # Class-level lock for singleton creation

    @classmethod
    def get_instance(cls) -> RepoAnalyseService:
        """Get the singleton instance of RepoAnalyseService.

        Returns:
            The singleton instance of RepoAnalyseService.
        """
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = RepoAnalyseService()
        return cls._instance

    def __init__(self):
        self._description_todo: TodoList[SymbolDefinition, LLMNote] = TodoList(
            allow_resubmit=True
        ).set_name("DescribeDefinitions")
        # Instance lock for coordinating todolist and index operations
        self._operation_lock = RLock()

    def ready_describe_definitions(
        self,
        traverse_policy: TraversePolicy | None = None,
        skip_existing_notes: bool = True,
    ) -> None:
        """Prepare tasks for LLM to describe all definitions in the codebase.

        Args:
            traverse_policy: Policy for traversing definitions. If None, defaults to ARBITRARY.
            skip_existing_notes: If True, skip definitions that already have LLM notes.

        This will find definitions and create tasks for them in the todolist according to the specified policy.
        """
        # Use operation lock to prevent interference with concurrent submit_note calls
        with self._operation_lock:
            if traverse_policy is None:
                traverse_policy = TraversePolicy.ARBITRARY

            service = CodeIndexService.get_instance()
            try:
                service.assert_initialized()
            except RuntimeError as e:
                raise RuntimeError("Please initialize the code index first.") from e

            index = service.index

            def cb_insert_note_into_index(_task_id: SymbolDefinition, _note: LLMNote):
                _symbol: Symbol = _task_id.symbol
                _definition: PureDefinition = _task_id.definition
                _dummy_def_holding_llm_note = Definition.from_pure(_definition).set_note(_note)
                index.add_definition(_symbol, _dummy_def_holding_llm_note)

        # Get definitions according to the specified traverse policy
        if traverse_policy == TraversePolicy.ARBITRARY:
            # Original behavior: iterate through all symbols and definitions arbitrarily
            definitions_to_process = []
            for symbol in index:
                for definition in index.get_definitions(symbol):
                    definitions_to_process.append((symbol, definition.to_pure()))
        else:
            # Use graph analyzer for BFS traversal
            graph_analyzer = GraphAnalyzerService.get_instance()

            if traverse_policy == TraversePolicy.BFS_CALLEE_TO_CALLER:
                direction = Direction.BACKWARD
            elif traverse_policy == TraversePolicy.BFS_CALLER_TO_CALLEE:
                direction = Direction.FORWARD
            else:
                raise ValueError(f"Unsupported traverse policy: {traverse_policy}")

            topological_order = graph_analyzer.get_topological_order(direction)

            # Create a map from PureDefinition to its owning Symbol for quick lookup
            definition_to_symbol_map: dict[PureDefinition, Symbol] = {}
            for symbol in index:
                for definition in index.get_definitions(symbol):
                    definition_to_symbol_map[definition.to_pure()] = symbol

            definitions_to_process = []
            for definition in topological_order:
                symbol = definition_to_symbol_map.get(definition)
                if symbol:
                    definitions_to_process.append((symbol, definition))
                else:
                    logger.warning(f"Could not find symbol for definition: {definition}")

        # Process the definitions according to the order determined by the policy
        for symbol, pure_definition in definitions_to_process:
            # Check if we should skip existing notes
            if skip_existing_notes:
                full_definition = self.get_full_definition(symbol, pure_definition)
                if full_definition and full_definition.llm_note is not None:
                    continue

            task_id = SymbolDefinition(
                symbol=symbol,
                definition=pure_definition,
            )
            if task_id in self._description_todo:
                continue

            self._description_todo.add_task(
                task_id=task_id,
                payload=None,
                callback=cb_insert_note_into_index,
            )
            logger.info(
                f"Added task to describe definition: {symbol.name} at {pure_definition.location}"
            )

    def get_description_progress(self) -> str:
        """Get a detailed string representing the progress of description tasks.

        Returns:
            A detailed progress string including total/pending counts,
            sample unfinished tasks, and recently submitted tasks.
        """
        base_progress = f"Progress: {str(self._description_todo)}"

        # Get up to 5 unfinished tasks
        unfinished_tasks = self.get_pending_describe_tasks(5)
        unfinished_info = []
        for task in unfinished_tasks:
            unfinished_info.append(f"{task.symbol.name} at {task.definition.location.file_path}")

        # Get up to 5 recently submitted tasks
        recently_submitted = self._description_todo.get_recently_submitted_tasks(5)
        submitted_info = []
        for task in recently_submitted:
            submitted_info.append(f"{task.symbol.name} at {task.definition.location.file_path}")

        # Build detailed progress string
        details = []
        if unfinished_info:
            details.append(f"Unfinished ({len(unfinished_info)}): {', '.join(unfinished_info)}")
        if submitted_info:
            details.append(
                f"Recently submitted ({len(submitted_info)}): {', '.join(submitted_info)}"
            )

        if details:
            return f"{base_progress}\n" + "\n".join(details)
        else:
            return base_progress

    def get_llm_note(self, symbol: Symbol, definition: PureDefinition) -> LLMNote | None:
        """Get the LLM note for a specific symbol and definition.



        Args:
            symbol: The function-like symbol.
            definition: The pure definition of the symbol.

        Returns:
            The LLM note if it exists, otherwise None.

        """
        index = CodeIndexService.get_instance().index
        definitions = index.get_definitions(symbol)

        # todo: performance can be improved using the dict inside CrossRefIndex.
        for defn in definitions:
            if defn.to_pure() == definition:
                return defn.llm_note
        return None

    def get_full_definition(self, symbol: Symbol, definition: PureDefinition) -> Definition | None:
        """Get the full definition info for a specific symbol and definition.

        Args:
            symbol: The function-like symbol.
            definition: The pure definition of the symbol.

        Returns:
            The full Definition if it exists, otherwise None.
        """
        index = CodeIndexService.get_instance().index
        definitions = index.get_definitions(symbol)
        for defn in definitions:
            if defn.to_pure() == definition:
                return defn
        return None

    def get_any_pending_describe_task(self) -> SymbolDefinition | None:
        """Get any definition that has not been described yet from the todolist.

        Returns:
            A SymbolDefinition that has no LLM note, or None if all definitions are described.
        """
        match self._description_todo.get_any_pending():
            case None:
                return None
            case SymbolDefinition() as symbol_definition, _:
                return symbol_definition
        return None

    def get_pending_describe_tasks(self, n: int) -> list[SymbolDefinition]:
        """Get a list of pending description tasks from the todolist.

        Args:
            n: Maximum number of pending tasks to return.

        Returns:
            List of SymbolDefinition objects that are pending description, limited to n items.
        """
        pending_task_ids = self._description_todo.get_pending_tasks(limit=n)
        return pending_task_ids

    def submit_note(self, symbol_definition: SymbolDefinition, note: LLMNote) -> str:
        """Submit a note for a specific symbol definition.

        This will update the index with the provided note. If the symbol definition is in
        the todolist, it will be marked as completed. If not, still try to update the index.

        Args:
            symbol_definition: The symbol definition to update.
            note: The LLM note to submit.
        """
        # Use operation lock to ensure atomic update of todolist and index
        with self._operation_lock:
            if symbol_definition in self._description_todo:
                logger.info(
                    f"Symbol definition {symbol_definition.symbol.name} at {symbol_definition.definition.location} in todolist, marking as completed."
                )
                self._description_todo.submit(symbol_definition, note)
            else:
                logger.info(
                    f"Symbol definition {symbol_definition.symbol.name} at {symbol_definition.definition.location} not in todolist, updating index directly."
                )
                index = CodeIndexService.get_instance().index
                _dummy_def_holding_llm_note = Definition.from_pure(
                    symbol_definition.definition
                ).set_note(note)
                index.add_definition(symbol_definition.symbol, _dummy_def_holding_llm_note)
            logger.info(
                f"Submitted note for {symbol_definition.symbol.name} at {symbol_definition.definition.location}"
            )
            # notify the index to persist
            msg = CodeIndexService.get_instance().persist()
            logger.info(f"Index persistence result: {msg}")
            return f"Note submitted for {symbol_definition.symbol.name} at {symbol_definition.definition.location}"
