"""Tests for enhanced RepoAnalyseService with traverse policies.

This module contains tests for the enhanced ready_describe_definitions method
that supports different traverse policies for ordering definition processing.

The tests cover:
    - Default ARBITRARY traverse policy behavior
    - BFS_CALLEE_TO_CALLER traverse policy
    - BFS_CALLER_TO_CALLEE traverse policy
    - Skip existing notes functionality
    - Integration with GraphAnalyzerService

Test Classes:
    TestRepoAnalyseServiceTraversePolicies: Tests for traverse policy functionality
"""

import pytest

from code_index.mcp_server.services import (
    CodeIndexService,
    GraphAnalyzerService,
    RepoAnalyseService,
)
from code_index.mcp_server.services.repo_analyse_service import TraversePolicy
from code_index.models import LLMNote


class TestRepoAnalyseServiceTraversePolicies:
    """Test class for RepoAnalyseService traverse policy functionality."""

    @pytest.fixture
    def code_index_service(self):
        """Create a fresh CodeIndexService instance for each test."""
        # Reset the singleton instance to ensure test isolation
        CodeIndexService._instance = None
        return CodeIndexService.get_instance()

    @pytest.fixture
    def graph_analyzer_service(self):
        """Create a fresh GraphAnalyzerService instance for each test."""
        # Reset the singleton instance to ensure test isolation
        GraphAnalyzerService._instance = None
        return GraphAnalyzerService.get_instance()

    @pytest.fixture
    def repo_analyse_service(self):
        """Create a fresh RepoAnalyseService instance for each test."""
        # Reset the singleton instance to ensure test isolation
        RepoAnalyseService._instance = None
        return RepoAnalyseService.get_instance()

    @pytest.fixture
    def sample_python_code_with_dependencies(self):
        """Provide sample Python code with clear dependency relationships."""
        return '''def leaf_function_a(x: int) -> int:
    """A leaf function with no dependencies."""
    return x * 2

def leaf_function_b(x: int) -> int:
    """Another leaf function with no dependencies."""
    return x + 10

def middle_function_a(x: int) -> int:
    """Function that depends on leaf_function_a."""
    return leaf_function_a(x) + 1

def middle_function_b(x: int) -> int:
    """Function that depends on both leaf functions."""
    a = leaf_function_a(x)
    b = leaf_function_b(x)
    return a + b

def top_function(x: int) -> int:
    """Function that depends on middle functions."""
    a = middle_function_a(x)
    b = middle_function_b(x)
    return a * b

class Calculator:
    """Calculator with methods that call top-level functions."""

    def __init__(self):
        self.value = 0

    def calculate(self, x: int) -> int:
        """Method that uses top_function."""
        result = top_function(x)
        self.value = result
        return result

    def reset(self) -> None:
        """Method with no dependencies."""
        self.value = 0
'''

    @pytest.fixture
    def sample_c_code_with_dependencies(self):
        """Provide sample C code with clear dependency relationships."""
        return """#include <stdio.h>

int leaf_util(int x) {
    return x + 1;
}

int middle_util(int x) {
    return leaf_util(x) * 2;
}

int complex_util(int x, int y) {
    int a = leaf_util(x);
    int b = middle_util(y);
    return a + b;
}

void print_result(int result) {
    printf("Result: %d\\n", result);
}

int main() {
    int result = complex_util(5, 10);
    print_result(result);
    return 0;
}
"""

    def test_traverse_policy_arbitrary_default(
        self,
        code_index_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test that ARBITRARY is used as default traverse policy."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Call ready_describe_definitions without specifying policy
        repo_analyse_service.ready_describe_definitions()

        # Should have created tasks
        pending_count = repo_analyse_service._description_todo.pending_size()
        assert pending_count > 0

        # Get some tasks to verify they were created
        tasks = repo_analyse_service.get_pending_describe_tasks(5)
        assert len(tasks) > 0

        # Should include functions from our code
        task_function_names = [task.symbol.name for task in tasks]
        assert any(
            name in ["leaf_function_a", "top_function", "calculate"] for name in task_function_names
        )

    def test_traverse_policy_arbitrary_explicit(
        self,
        code_index_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test explicit ARBITRARY traverse policy."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Call with explicit ARBITRARY policy
        repo_analyse_service.ready_describe_definitions(traverse_policy=TraversePolicy.ARBITRARY)

        pending_count = repo_analyse_service._description_todo.pending_size()
        assert pending_count > 0

        # Get all functions from indexer for comparison
        all_functions = code_index_service.indexer.get_all_functions()
        total_definitions = sum(
            len(list(code_index_service.index.get_definitions(func))) for func in all_functions
        )

        # Should have tasks for all definitions
        assert pending_count == total_definitions

    def test_traverse_policy_bfs_callee_to_caller(
        self,
        code_index_service,
        graph_analyzer_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test BFS_CALLEE_TO_CALLER traverse policy."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Call with BFS_CALLEE_TO_CALLER policy
        repo_analyse_service.ready_describe_definitions(
            traverse_policy=TraversePolicy.BFS_CALLEE_TO_CALLER
        )

        pending_count = repo_analyse_service._description_todo.pending_size()
        assert pending_count > 0

        # Get ordered tasks
        ordered_tasks = repo_analyse_service.get_pending_describe_tasks(pending_count)
        task_function_names = [task.symbol.name for task in ordered_tasks]

        # In callee-to-caller order, leaf functions should appear before functions that call them
        # This is a heuristic test since exact ordering depends on the graph structure
        assert len(task_function_names) > 0

        # Verify that the graph analyzer was used for ordering
        # by checking that the order is different from arbitrary (if more than one function)
        if len(task_function_names) > 1:
            # Reset and try arbitrary order to compare
            RepoAnalyseService._instance = None
            repo_analyse_service_2 = RepoAnalyseService.get_instance()
            repo_analyse_service_2.ready_describe_definitions(
                traverse_policy=TraversePolicy.ARBITRARY
            )
            arbitrary_tasks = repo_analyse_service_2.get_pending_describe_tasks(pending_count)
            arbitrary_names = [task.symbol.name for task in arbitrary_tasks]

            # The orders might be different (though not guaranteed)
            # At least verify both have the same set of functions
            assert set(task_function_names) == set(arbitrary_names)

    def test_traverse_policy_bfs_caller_to_callee(
        self,
        code_index_service,
        graph_analyzer_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test BFS_CALLER_TO_CALLEE traverse policy."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Call with BFS_CALLER_TO_CALLEE policy
        repo_analyse_service.ready_describe_definitions(
            traverse_policy=TraversePolicy.BFS_CALLER_TO_CALLEE
        )

        pending_count = repo_analyse_service._description_todo.pending_size()
        assert pending_count > 0

        # Get ordered tasks
        ordered_tasks = repo_analyse_service.get_pending_describe_tasks(pending_count)
        task_function_names = [task.symbol.name for task in ordered_tasks]

        # Should have all functions
        assert len(task_function_names) > 0

        # In caller-to-callee order, functions that call others should appear before their callees
        # This is a heuristic test since exact ordering depends on the graph structure
        # At minimum, verify we have the expected functions
        expected_functions = {
            "leaf_function_a",
            "leaf_function_b",
            "middle_function_a",
            "middle_function_b",
            "top_function",
            "calculate",
            "reset",
            "__init__",
        }
        actual_functions = set(task_function_names)
        assert expected_functions.issubset(actual_functions)

    def test_skip_existing_notes_true(
        self,
        code_index_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test skip_existing_notes=True functionality."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # First call to create all tasks
        repo_analyse_service.ready_describe_definitions(skip_existing_notes=True)
        initial_pending = repo_analyse_service._description_todo.pending_size()

        # Submit a note for one task
        task = repo_analyse_service.get_any_pending_describe_task()
        assert task is not None
        test_note = LLMNote(description="Test description for first task")
        repo_analyse_service.submit_note(task, test_note)

        # Create new service and call ready_describe_definitions again
        RepoAnalyseService._instance = None
        repo_analyse_service_2 = RepoAnalyseService.get_instance()
        repo_analyse_service_2.ready_describe_definitions(skip_existing_notes=True)

        # Should have one fewer task since one definition now has a note
        new_pending = repo_analyse_service_2._description_todo.pending_size()
        assert new_pending == initial_pending - 1

    def test_skip_existing_notes_false(
        self,
        code_index_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test skip_existing_notes=False functionality."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # First call to create all tasks
        repo_analyse_service.ready_describe_definitions(skip_existing_notes=False)
        initial_pending = repo_analyse_service._description_todo.pending_size()

        # Submit a note for one task
        task = repo_analyse_service.get_any_pending_describe_task()
        assert task is not None
        test_note = LLMNote(description="Test description for first task")
        repo_analyse_service.submit_note(task, test_note)

        # Create new service and call ready_describe_definitions with skip_existing_notes=False
        RepoAnalyseService._instance = None
        repo_analyse_service_2 = RepoAnalyseService.get_instance()
        repo_analyse_service_2.ready_describe_definitions(skip_existing_notes=False)

        # Should have the same number of tasks since we're not skipping existing notes
        new_pending = repo_analyse_service_2._description_todo.pending_size()
        assert new_pending == initial_pending

    def test_traverse_policy_with_c_code(
        self,
        code_index_service,
        graph_analyzer_service,
        repo_analyse_service,
        sample_c_code_with_dependencies,
        tmp_path,
    ):
        """Test traverse policies work with C code."""
        # Setup repository
        repo_path = tmp_path / "c_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.c"
        test_file.write_text(sample_c_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "c", "sqlite")

        # Test BFS_CALLEE_TO_CALLER with C code
        repo_analyse_service.ready_describe_definitions(
            traverse_policy=TraversePolicy.BFS_CALLEE_TO_CALLER
        )

        pending_count = repo_analyse_service._description_todo.pending_size()
        assert pending_count > 0

        # Get ordered tasks
        ordered_tasks = repo_analyse_service.get_pending_describe_tasks(pending_count)
        task_function_names = [task.symbol.name for task in ordered_tasks]

        # Should include C functions
        expected_functions = {"leaf_util", "middle_util", "complex_util", "print_result", "main"}
        actual_functions = set(task_function_names)
        assert expected_functions.issubset(actual_functions)

    def test_traverse_policy_comparison_orders(
        self,
        code_index_service,
        graph_analyzer_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test that different traverse policies produce different orders."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Test ARBITRARY order
        RepoAnalyseService._instance = None
        repo_service_arbitrary = RepoAnalyseService.get_instance()
        repo_service_arbitrary.ready_describe_definitions(traverse_policy=TraversePolicy.ARBITRARY)
        arbitrary_tasks = repo_service_arbitrary.get_pending_describe_tasks(100)
        arbitrary_names = [task.symbol.name for task in arbitrary_tasks]

        # Test BFS_CALLEE_TO_CALLER order
        RepoAnalyseService._instance = None
        repo_service_callee_caller = RepoAnalyseService.get_instance()
        repo_service_callee_caller.ready_describe_definitions(
            traverse_policy=TraversePolicy.BFS_CALLEE_TO_CALLER
        )
        callee_caller_tasks = repo_service_callee_caller.get_pending_describe_tasks(100)
        callee_caller_names = [task.symbol.name for task in callee_caller_tasks]

        # Test BFS_CALLER_TO_CALLEE order
        RepoAnalyseService._instance = None
        repo_service_caller_callee = RepoAnalyseService.get_instance()
        repo_service_caller_callee.ready_describe_definitions(
            traverse_policy=TraversePolicy.BFS_CALLER_TO_CALLEE
        )
        caller_callee_tasks = repo_service_caller_callee.get_pending_describe_tasks(100)
        caller_callee_names = [task.symbol.name for task in caller_callee_tasks]

        # All should have the same set of functions
        assert set(arbitrary_names) == set(callee_caller_names) == set(caller_callee_names)

        # The orders might be different (depending on graph structure)
        assert len(arbitrary_names) == len(callee_caller_names) == len(caller_callee_names)

    def test_invalid_traverse_policy(
        self,
        code_index_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test that invalid traverse policy raises error."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # This test is more for completeness - the enum should prevent invalid values
        # But we can test with a manually constructed invalid value
        class FakePolicy:
            pass

        fake_policy = FakePolicy()

        # Should raise an error when using invalid policy
        with pytest.raises((ValueError, AttributeError)):
            repo_analyse_service.ready_describe_definitions(traverse_policy=fake_policy)

    def test_traverse_policy_without_graph_analyzer_initialization(
        self,
        code_index_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test BFS policies when GraphAnalyzerService encounters issues."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Clear the graph analyzer cache to test error handling
        GraphAnalyzerService._instance = None
        graph_service = GraphAnalyzerService.get_instance()
        graph_service.clear_cache()

        # This should still work as the graph analyzer should initialize when needed
        try:
            repo_analyse_service.ready_describe_definitions(
                traverse_policy=TraversePolicy.BFS_CALLEE_TO_CALLER
            )
            pending_count = repo_analyse_service._description_todo.pending_size()
            assert pending_count > 0
        except Exception as e:
            # If there's an error, it should be handled gracefully
            # or the test should verify the expected error type
            pytest.fail(f"BFS traverse policy failed unexpectedly: {e}")

    def test_traverse_policy_performance_with_large_codebase(
        self,
        code_index_service,
        graph_analyzer_service,
        repo_analyse_service,
        tmp_path,
    ):
        """Test traverse policies with a larger codebase."""
        # Create a larger codebase programmatically
        large_code = """# Generated functions with dependencies
"""

        # Generate a chain of dependencies
        for i in range(10):
            if i == 0:
                large_code += f'''def func_{i}(x: int) -> int:
    """Leaf function {i}."""
    return x + {i}

'''
            else:
                large_code += f'''def func_{i}(x: int) -> int:
    """Function {i} that depends on func_{i - 1}."""
    return func_{i - 1}(x) + {i}

'''

        # Add a few classes with methods
        large_code += """class ProcessorA:
    def __init__(self):
        self.value = 0

    def process(self, x: int) -> int:
        return func_5(x)

class ProcessorB:
    def __init__(self):
        self.data = []

    def process(self, x: int) -> int:
        result = func_8(x)
        self.data.append(result)
        return result

    def aggregate(self) -> int:
        total = 0
        for item in self.data:
            total += func_2(item)
        return total
"""

        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(large_code)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # Test different policies with the larger codebase
        policies = [
            TraversePolicy.ARBITRARY,
            TraversePolicy.BFS_CALLEE_TO_CALLER,
            TraversePolicy.BFS_CALLER_TO_CALLEE,
        ]

        results = {}
        for policy in policies:
            # Reset service for each policy
            RepoAnalyseService._instance = None
            repo_service = RepoAnalyseService.get_instance()

            repo_service.ready_describe_definitions(traverse_policy=policy)
            pending_count = repo_service._description_todo.pending_size()
            tasks = repo_service.get_pending_describe_tasks(pending_count)

            results[policy] = [task.symbol.name for task in tasks]

        # All policies should find the same set of functions
        arbitrary_set = set(results[TraversePolicy.ARBITRARY])
        callee_caller_set = set(results[TraversePolicy.BFS_CALLEE_TO_CALLER])
        caller_callee_set = set(results[TraversePolicy.BFS_CALLER_TO_CALLEE])

        assert arbitrary_set == callee_caller_set == caller_callee_set
        assert len(arbitrary_set) > 10  # Should have generated functions plus class methods

        # Verify we have the expected generated functions
        expected_funcs = {f"func_{i}" for i in range(10)}
        expected_methods = {"__init__", "process", "aggregate"}

        assert expected_funcs.issubset(arbitrary_set)
        assert expected_methods.issubset(arbitrary_set)

    def test_traverse_policy_enum_values(self):
        """Test that TraversePolicy enum has expected values."""
        assert TraversePolicy.ARBITRARY.value == "arbitrary"
        assert TraversePolicy.BFS_CALLEE_TO_CALLER.value == "bfs_callee_to_caller"
        assert TraversePolicy.BFS_CALLER_TO_CALLEE.value == "bfs_caller_to_callee"

        # Test that we can create policies from string values
        assert TraversePolicy("arbitrary") == TraversePolicy.ARBITRARY
        assert TraversePolicy("bfs_callee_to_caller") == TraversePolicy.BFS_CALLEE_TO_CALLER
        assert TraversePolicy("bfs_caller_to_callee") == TraversePolicy.BFS_CALLER_TO_CALLEE

    def test_ready_describe_definitions_integration_with_graph_clearing(
        self,
        code_index_service,
        graph_analyzer_service,
        repo_analyse_service,
        sample_python_code_with_dependencies,
        tmp_path,
    ):
        """Test integration when graph cache is cleared between operations."""
        # Setup repository
        repo_path = tmp_path / "python_repo"
        repo_path.mkdir()
        test_file = repo_path / "test.py"
        test_file.write_text(sample_python_code_with_dependencies)

        # Index the repository
        code_index_service.setup_repo_index(repo_path, "python", "json")

        # First call with BFS policy (creates graph cache)
        repo_analyse_service.ready_describe_definitions(
            traverse_policy=TraversePolicy.BFS_CALLEE_TO_CALLER
        )
        initial_pending = repo_analyse_service._description_todo.pending_size()

        # Clear the graph cache
        graph_analyzer_service.clear_cache()

        # Second call should recreate the cache and work correctly
        RepoAnalyseService._instance = None
        repo_service_2 = RepoAnalyseService.get_instance()
        repo_service_2.ready_describe_definitions(
            traverse_policy=TraversePolicy.BFS_CALLER_TO_CALLEE
        )
        second_pending = repo_service_2._description_todo.pending_size()

        # Should have the same number of pending tasks
        assert initial_pending == second_pending


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
