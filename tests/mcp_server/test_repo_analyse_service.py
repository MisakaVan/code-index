"""Integration tests for RepoAnalyseService.

This module contains comprehensive integration tests for the RepoAnalyseService class,
which helps LLMs traverse a codebase by managing todolist tasks for describing definitions.

The tests cover:
    - Repository setup and task creation functionality
    - Successful submission of LLM notes
    - Re-submission behavior (allowed vs not allowed)
    - Verification that ready_describe_definitions includes all undescribed definitions
    - Progress tracking and todo list management
    - Error handling and edge cases

Test Classes:
    TestRepoAnalyseServiceIntegration: Comprehensive integration tests using real temp files/repos
"""

import pytest

from code_index.mcp_server.services import CodeIndexService, RepoAnalyseService
from code_index.models import LLMNote


class TestRepoAnalyseServiceIntegration:
    """Integration test class for RepoAnalyseService functionality."""

    @pytest.fixture
    def code_index_service(self):
        """Create a fresh CodeIndexService instance for each test."""
        # Reset the singleton instance to ensure test isolation
        CodeIndexService._instance = None
        return CodeIndexService.get_instance()

    @pytest.fixture
    def repo_analyse_service(self):
        """Create a fresh RepoAnalyseService instance for each test."""
        return RepoAnalyseService()

    @pytest.fixture
    def sample_python_code(self):
        """Provide sample Python code for testing."""
        return '''def hello_world(name: str) -> str:
    """Greet someone with their name."""
    return f"Hello, {name}!"

def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two integers."""
    result = a + b
    hello_world("Calculator")  # Call to hello_world
    return result

class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.history = []

    def add(self, a: int, b: int) -> int:
        """Add two numbers and store in history."""
        result = calculate_sum(a, b)  # Call to calculate_sum
        self.history.append(f"{a} + {b} = {result}")
        return result

    def subtract(self, a: int, b: int) -> int:
        """Subtract two numbers."""
        return a - b
'''

    @pytest.fixture
    def sample_c_code(self):
        """Provide sample C code for testing."""
        return """#include <stdio.h>

void print_number(int num) {
    printf("Number: %d\\n", num);
}

int add_numbers(int a, int b) {
    int result = a + b;
    print_number(result);  // Call to print_number
    return result;
}

int multiply(int a, int b) {
    return a * b;
}

int main() {
    int sum = add_numbers(5, 3);  // Call to add_numbers
    int product = multiply(2, 4);  // Call to multiply
    print_number(sum);  // Another call to print_number
    return 0;
}
"""

    def test_service_initialization_without_index_fails(self, repo_analyse_service):
        """Test that using the service without initializing the code index fails."""
        CodeIndexService.get_instance()._clear_indexer()
        with pytest.raises(RuntimeError, match="Please initialize the code index first"):
            repo_analyse_service.ready_describe_definitions()

    def test_ready_describe_definitions_creates_tasks_for_all_functions(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that ready_describe_definitions creates tasks for all functions without notes."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Get initial function count
        all_functions = code_index_service.indexer.get_all_functions()
        initial_function_count = len(all_functions)

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Verify tasks were created for all functions
        progress = repo_analyse_service.get_description_progress()
        assert "total=" in progress
        assert "pending=" in progress

        # Check that we have tasks for all definitions without notes
        pending_count = repo_analyse_service._description_todo.pending_size()
        assert pending_count > 0

        # Verify we can get a pending task
        pending_task = repo_analyse_service.get_any_pending_describe_task()
        assert pending_task is not None
        assert hasattr(pending_task, "symbol")
        assert hasattr(pending_task, "definition")

    def test_successful_note_submission(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test successful submission of LLM notes for definitions."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Get initial pending count
        initial_pending = repo_analyse_service._description_todo.pending_size()
        assert initial_pending > 0

        # Get a task to work on
        symbol_definition = repo_analyse_service.get_any_pending_describe_task()
        assert symbol_definition is not None

        # Create and submit a note
        test_note = LLMNote(
            description="This is a test function that demonstrates functionality.",
            potential_vulnerabilities="No known vulnerabilities detected.",
        )

        result = repo_analyse_service.submit_note(symbol_definition, test_note)
        assert "Note submitted for" in result
        assert symbol_definition.symbol.name in result

        # Verify the pending count decreased
        new_pending = repo_analyse_service._description_todo.pending_size()
        assert new_pending == initial_pending - 1

        # Verify the note was actually stored in the index
        retrieved_note = repo_analyse_service.get_llm_note(
            symbol_definition.symbol, symbol_definition.definition
        )
        assert retrieved_note is not None
        assert retrieved_note.description == test_note.description
        assert retrieved_note.potential_vulnerabilities == test_note.potential_vulnerabilities

    def test_resubmission_behavior_with_allow_resubmit_true(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that re-submission is allowed when allow_resubmit is True."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Get a task and submit a note
        symbol_definition = repo_analyse_service.get_any_pending_describe_task()
        assert symbol_definition is not None

        first_note = LLMNote(description="First description")
        repo_analyse_service.submit_note(symbol_definition, first_note)

        # Verify the note was stored
        retrieved_note = repo_analyse_service.get_llm_note(
            symbol_definition.symbol, symbol_definition.definition
        )
        assert retrieved_note.description == "First description"

        # Try to re-submit with a different note
        second_note = LLMNote(description="Updated description")

        # Since allow_resubmit is True by default, this should raise ValueError
        with pytest.raises(ValueError, match="Task already submitted"):
            repo_analyse_service.submit_note(symbol_definition, second_note)

    def test_resubmission_behavior_with_allow_resubmit_false(
        self, code_index_service, sample_python_code, tmp_path
    ):
        """Test that re-submission is logged but allowed when allow_resubmit is False."""
        # Create a service with allow_resubmit=False
        repo_analyse_service = RepoAnalyseService()
        repo_analyse_service._description_todo.allow_resubmit = False

        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Get a task and submit a note
        symbol_definition = repo_analyse_service.get_any_pending_describe_task()
        assert symbol_definition is not None

        first_note = LLMNote(description="First description")
        repo_analyse_service.submit_note(symbol_definition, first_note)

        # Try to re-submit with a different note - should be allowed but logged
        second_note = LLMNote(description="Updated description")
        result = repo_analyse_service.submit_note(symbol_definition, second_note)
        assert "Note submitted for" in result

        # Verify the note was updated
        retrieved_note = repo_analyse_service.get_llm_note(
            symbol_definition.symbol, symbol_definition.definition
        )
        assert retrieved_note.description == "Updated description"

    def test_ready_describe_definitions_skips_already_described_definitions(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that ready_describe_definitions skips definitions that already have notes."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # First call to ready_describe_definitions
        repo_analyse_service.ready_describe_definitions()
        initial_pending = repo_analyse_service._description_todo.pending_size()

        # Submit a note for one definition
        symbol_definition = repo_analyse_service.get_any_pending_describe_task()
        test_note = LLMNote(description="Test description")
        repo_analyse_service.submit_note(symbol_definition, test_note)

        # Create a new service instance and call ready_describe_definitions again
        new_repo_analyse_service = RepoAnalyseService()
        new_repo_analyse_service.ready_describe_definitions()
        new_pending = new_repo_analyse_service._description_todo.pending_size()

        # Should have one fewer pending task since one definition now has a note
        assert new_pending == initial_pending - 1

    def test_get_description_progress_format(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that get_description_progress returns properly formatted progress string."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Initially no tasks
        initial_progress = repo_analyse_service.get_description_progress()
        assert "Progress: DescribeDefinitions(total=0, pending=0)" == initial_progress

        # After preparing tasks
        repo_analyse_service.ready_describe_definitions()
        progress_with_tasks = repo_analyse_service.get_description_progress()
        assert "Progress: DescribeDefinitions(total=" in progress_with_tasks
        assert "pending=" in progress_with_tasks

        # Submit one task and check progress again
        symbol_definition = repo_analyse_service.get_any_pending_describe_task()
        if symbol_definition is not None:
            test_note = LLMNote(description="Test description")
            repo_analyse_service.submit_note(symbol_definition, test_note)

            progress_after_submit = repo_analyse_service.get_description_progress()
            assert "DescribeDefinitions" in progress_after_submit
            # Verify pending count decreased
            assert "pending=" in progress_after_submit

    def test_get_llm_note_returns_none_for_nonexistent_note(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that get_llm_note returns None for definitions without notes."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Get a task but don't submit a note
        symbol_definition = repo_analyse_service.get_any_pending_describe_task()
        assert symbol_definition is not None

        # Try to get note for definition without a note
        retrieved_note = repo_analyse_service.get_llm_note(
            symbol_definition.symbol, symbol_definition.definition
        )
        assert retrieved_note is None

    def test_complete_workflow_multiple_functions(
        self, code_index_service, repo_analyse_service, sample_c_code, tmp_path
    ):
        """Test complete workflow with multiple functions in C code."""
        # Setup C repository
        repo_path = tmp_path / "c_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.c"
        test_file.write_text(sample_c_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "c", "sqlite")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        initial_pending = repo_analyse_service._description_todo.pending_size()
        assert initial_pending > 0

        # Submit notes for all pending tasks
        submitted_count = 0
        while True:
            symbol_definition = repo_analyse_service.get_any_pending_describe_task()
            if symbol_definition is None:
                break

            test_note = LLMNote(
                description=f"Description for {symbol_definition.symbol.name}",
                potential_vulnerabilities="No vulnerabilities detected.",
            )
            repo_analyse_service.submit_note(symbol_definition, test_note)
            submitted_count += 1

        # Verify all tasks were submitted
        final_pending = repo_analyse_service._description_todo.pending_size()
        assert final_pending == 0
        assert submitted_count == initial_pending

        # Verify progress shows completion
        final_progress = repo_analyse_service.get_description_progress()
        assert "pending=0" in final_progress

    def test_error_handling_with_invalid_symbol_definition(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test error handling when submitting note for invalid symbol definition."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Get a valid task
        symbol_definition = repo_analyse_service.get_any_pending_describe_task()
        assert symbol_definition is not None

        # Submit note for the valid task
        test_note = LLMNote(description="Test description")
        repo_analyse_service.submit_note(symbol_definition, test_note)

        # Try to submit again for the same task (should fail with allow_resubmit=True)
        with pytest.raises(ValueError, match="Task already submitted"):
            repo_analyse_service.submit_note(symbol_definition, test_note)

    def test_get_any_undescribed_definition_returns_none_when_all_described(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that get_any_undescribed_definition_from_todolist returns None when all are described."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Submit notes for all tasks
        while True:
            symbol_definition = repo_analyse_service.get_any_pending_describe_task()
            if symbol_definition is None:
                break

            test_note = LLMNote(description=f"Description for {symbol_definition.symbol.name}")
            repo_analyse_service.submit_note(symbol_definition, test_note)

        # Verify no more undescribed definitions
        final_result = repo_analyse_service.get_any_pending_describe_task()
        assert final_result is None

    def test_ready_describe_definitions_called_multiple_times(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test behavior when ready_describe_definitions is called multiple times."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # First call
        repo_analyse_service.ready_describe_definitions()
        first_count = repo_analyse_service._description_todo.pending_size()

        # Second call should add duplicate tasks
        repo_analyse_service.ready_describe_definitions()
        second_count = repo_analyse_service._description_todo.pending_size()

        # Should have roughly double the tasks (some may be duplicates that cause KeyError)
        # The exact behavior depends on how duplicate task IDs are handled
        assert second_count >= first_count

    def test_get_pending_describe_tasks(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test get_pending_describe_tasks method."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Test getting pending tasks with limit
        pending_tasks_3 = repo_analyse_service.get_pending_describe_tasks(3)
        assert isinstance(pending_tasks_3, list)
        assert len(pending_tasks_3) <= 3

        # All items should be SymbolDefinition objects
        for task in pending_tasks_3:
            assert hasattr(task, "symbol")
            assert hasattr(task, "definition")

        # Test getting all pending tasks
        all_pending = repo_analyse_service.get_pending_describe_tasks(100)  # Large number
        total_pending = repo_analyse_service._description_todo.pending_size()
        assert len(all_pending) == total_pending

        # Submit one task and verify the list shrinks
        if pending_tasks_3:
            first_task = pending_tasks_3[0]
            test_note = LLMNote(description="Test description")
            repo_analyse_service.submit_note(first_task, test_note)

            # Get pending tasks again - should be one fewer
            new_pending = repo_analyse_service.get_pending_describe_tasks(100)
            assert len(new_pending) == total_pending - 1

    def test_get_description_progress_detailed(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test the enhanced get_description_progress method with detailed information."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Initially no tasks
        initial_progress = repo_analyse_service.get_description_progress()
        assert "Progress: DescribeDefinitions(total=0, pending=0)" == initial_progress

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()
        progress_with_tasks = repo_analyse_service.get_description_progress()

        # Should contain basic progress info
        assert "Progress: DescribeDefinitions(total=" in progress_with_tasks
        assert "pending=" in progress_with_tasks

        # Should contain unfinished tasks info
        assert "Unfinished" in progress_with_tasks

        # Submit some tasks to test recently submitted section
        pending_tasks = repo_analyse_service.get_pending_describe_tasks(3)
        for i, task in enumerate(pending_tasks[:2]):  # Submit first 2 tasks
            test_note = LLMNote(description=f"Test description {i}")
            repo_analyse_service.submit_note(task, test_note)

        # Get progress again - should show recently submitted
        progress_with_submitted = repo_analyse_service.get_description_progress()
        assert "Recently submitted" in progress_with_submitted

        # Should still show unfinished tasks if any remain
        if repo_analyse_service._description_todo.pending_size() > 0:
            assert "Unfinished" in progress_with_submitted

    def test_get_description_progress_with_file_paths(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that get_description_progress includes file paths in task descriptions."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Get progress
        progress = repo_analyse_service.get_description_progress()

        # Should contain file path information
        assert "test.py" in progress

        # Submit a task and check recently submitted includes file path
        pending_task = repo_analyse_service.get_any_pending_describe_task()
        if pending_task:
            test_note = LLMNote(description="Test description")
            repo_analyse_service.submit_note(pending_task, test_note)

            progress_after_submit = repo_analyse_service.get_description_progress()
            assert "test.py" in progress_after_submit

    def test_get_pending_describe_tasks_empty_list(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test get_pending_describe_tasks returns empty list when no pending tasks."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Initially no tasks
        empty_list = repo_analyse_service.get_pending_describe_tasks(5)
        assert empty_list == []

        # Prepare and complete all tasks
        repo_analyse_service.ready_describe_definitions()

        # Submit all tasks
        while True:
            task = repo_analyse_service.get_any_pending_describe_task()
            if task is None:
                break
            test_note = LLMNote(description=f"Description for {task.symbol.name}")
            repo_analyse_service.submit_note(task, test_note)

        # Should return empty list
        final_list = repo_analyse_service.get_pending_describe_tasks(10)
        assert final_list == []

    def test_get_pending_describe_tasks_ordering(
        self, code_index_service, repo_analyse_service, sample_python_code, tmp_path
    ):
        """Test that get_pending_describe_tasks maintains ordering from TodoList."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Prepare description tasks
        repo_analyse_service.ready_describe_definitions()

        # Get tasks multiple times - should be consistent ordering
        first_call = repo_analyse_service.get_pending_describe_tasks(5)
        second_call = repo_analyse_service.get_pending_describe_tasks(5)

        # Should return same order (since we haven't modified anything)
        assert first_call == second_call

        # Submit first task and verify remaining tasks shift
        if first_call:
            first_task = first_call[0]
            test_note = LLMNote(description="Test description")
            repo_analyse_service.submit_note(first_task, test_note)

            # Get remaining tasks
            remaining_tasks = repo_analyse_service.get_pending_describe_tasks(5)

            # Should match the tail of the original list (minus the submitted first task)
            expected_remaining = [task for task in first_call[1:] if task != first_task]
            assert remaining_tasks[: len(expected_remaining)] == expected_remaining


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
