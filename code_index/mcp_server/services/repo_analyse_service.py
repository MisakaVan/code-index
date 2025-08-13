"""Help LLM traverse codebase with todolist.

This module provides a service to help LLMs (Large Language Models) traverse a codebase
by symbol/definition, using a todolist structure to manage tasks.
"""

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
        """Get a string representing the progress of description tasks."""
        return f"Progress: {str(self._description_todo)}"

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

    def get_any_undescribed_definition_from_todolist(self) -> SymbolDefinition | None:
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

    def submit_note(self, symbol_definition: SymbolDefinition, note: LLMNote) -> str:
        """Submit a note for a specific symbol definition.

        This will update the index with the provided note.

        Args:
            symbol_definition: The symbol definition to update.
            note: The LLM note to submit.
        """
        self._description_todo.submit(symbol_definition, note)
        logger.info(
            f"Submitted note for {symbol_definition.symbol.name} at {symbol_definition.definition.location}"
        )
        return f"Note submitted for {symbol_definition.symbol.name} at {symbol_definition.definition.location}"
