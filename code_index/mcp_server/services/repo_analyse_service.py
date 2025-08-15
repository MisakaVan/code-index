"""Help LLM traverse codebase with todolist.

This module provides a service to help LLMs (Large Language Models) traverse a codebase
by symbol/definition, using a todolist structure to manage tasks.
"""

from __future__ import annotations

from code_index.models import Definition, FunctionLike, LLMNote, PureDefinition, SymbolDefinition
from code_index.utils.logger import logger

from .code_index_service import CodeIndexService
from .todo_list import TodoList


class RepoAnalyseService:
    """Service to help LLMs traverse a codebase by symbol/definition.

    This service uses a TodoList to manage tasks related to codebase traversal.
    It allows adding tasks, yielding tasks for processing, and submitting results.

    - iterate all definitions and let llm generate a description for each
    """

    _instance: RepoAnalyseService | None = None

    @classmethod
    def get_instance(cls) -> RepoAnalyseService:
        """Get the singleton instance of RepoAnalyseService.

        Returns:
            The singleton instance of RepoAnalyseService.
        """
        if cls._instance is None:
            cls._instance = RepoAnalyseService()
        return cls._instance

    def __init__(self):
        self._description_todo: TodoList[SymbolDefinition, LLMNote] = TodoList(
            allow_resubmit=True
        ).set_name("DescribeDefinitions")

    def ready_describe_definitions(self) -> None:
        """Prepare tasks for LLM to describe all definitions in the codebase.

        This will find those definitions that have no description yet, and create tasks
        for them in the todolist.
        """
        service = CodeIndexService.get_instance()
        try:
            service.assert_initialized()
        except RuntimeError as e:
            raise RuntimeError("Please initialize the code index first.") from e

        index = service.index

        def cb_insert_note_into_index(_task_id: SymbolDefinition, _note: LLMNote):
            _symbol: FunctionLike = _task_id.symbol
            _definition: PureDefinition = _task_id.definition
            _dummy_def_holding_llm_note = Definition.from_pure(_definition).set_note(_note)
            index.add_definition(_symbol, _dummy_def_holding_llm_note)

        for symbol in index:
            for definition in index.get_definitions(symbol):
                if definition.llm_note is not None:
                    continue
                task_id = SymbolDefinition(
                    symbol=symbol,
                    definition=definition.to_pure(),
                )
                if task_id in self._description_todo:
                    continue
                self._description_todo.add_task(
                    task_id=task_id,
                    payload=None,
                    callback=cb_insert_note_into_index,
                )
                logger.info(
                    f"Added task to describe definition: {symbol.name} at {definition.location}"
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

    def get_llm_note(self, symbol: FunctionLike, definition: PureDefinition) -> LLMNote | None:
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

    def get_full_definition(
        self, symbol: FunctionLike, definition: PureDefinition
    ) -> Definition | None:
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
