"""Tests for the in-memory TodoList helper.

Covers:
    - Adding tasks and duplicate protection
    - Submitting tasks (with and without callbacks)
    - Callback success semantics (state mutated only after callback success)
    - Callback failure semantics (state NOT mutated, exception propagated)
    - Pending iteration & counting
    - Result retrieval
    - Clearing submitted tasks
"""

from __future__ import annotations

import pytest

from code_index.mcp_server.services.todo_list import TodoList


def test_add_and_duplicate():
    todos: TodoList[str, str] = TodoList()
    todos.add_task("t1", payload={"a": 1})
    assert "t1" in todos
    # duplicate
    with pytest.raises(KeyError):
        todos.add_task("t1")


def test_yield_pending_and_pending_count():
    todos: TodoList[int, int] = TodoList()
    for i in range(3):
        todos.add_task(i)
    pending_ids = {tid for tid, _ in todos.yield_pending()}  # type: ignore
    assert pending_ids == {0, 1, 2}
    assert todos.pending_count() == 3

    # submit one
    todos.submit(1, 42)
    pending_ids_after = {tid for tid, _ in todos.yield_pending()}  # type: ignore
    assert pending_ids_after == {0, 2}
    assert todos.pending_count() == 2


def test_submit_basic_and_get_result():
    todos: TodoList[str, int] = TodoList(allow_resubmit=False)
    todos.add_task("job")
    assert todos.get_result("job") is None
    assert todos.is_pending("job") is True

    todos.submit("job", 99)
    assert todos.is_pending("job") is False
    assert todos.get_result("job") == 99

    # double submit => error
    with pytest.raises(ValueError):
        todos.submit("job", 100)


def test_submit_with_resubmit_allowed():
    """Test that resubmission works when allow_resubmit=True (default)."""
    todos: TodoList[str, int] = TodoList()  # default allow_resubmit=True
    todos.add_task("job")

    # First submission
    todos.submit("job", 99)
    assert todos.get_result("job") == 99
    assert todos.is_pending("job") is False

    # Resubmission should work and update the result
    todos.submit("job", 100)
    assert todos.get_result("job") == 100
    assert todos.is_pending("job") is False


def test_get_result_unknown_and_is_pending_unknown():
    todos: TodoList[str, int] = TodoList()
    with pytest.raises(KeyError):
        todos.get_result("missing")
    with pytest.raises(KeyError):
        todos.is_pending("missing")


def test_submit_with_success_callback():
    collected: list[tuple[str, int]] = []

    def cb(tid: str, value: int):  # CallbackType
        collected.append((tid, value))

    todos: TodoList[str, int] = TodoList()
    todos.add_task("task", callback=cb)

    todos.submit("task", 7)
    assert collected == [("task", 7)]
    assert todos.get_result("task") == 7
    assert todos.is_pending("task") is False


def test_submit_with_failing_callback_state_not_mutated():
    collected: list[tuple[str, int]] = []

    def failing_cb(tid: str, value: int):  # CallbackType
        # Intentionally raise BEFORE mutating external side-effects list
        raise RuntimeError("boom")

    todos: TodoList[str, int] = TodoList()
    todos.add_task("task", callback=failing_cb)

    with pytest.raises(RuntimeError, match="boom"):
        todos.submit("task", 10)

    # State NOT mutated
    assert collected == []  # callback didn't run its side-effect
    assert todos.is_pending("task") is True
    assert todos.get_result("task") is None


def test_submit_with_callback_partial_side_effect_then_raise():
    # Demonstrate that if user callback has side-effect *before* raising,
    # the TodoList still does NOT mark the task submitted.
    side_effects: list[int] = []

    def cb(tid: str, value: int):
        side_effects.append(value)
        raise ValueError("fail after side-effect")

    todos: TodoList[str, int] = TodoList()
    todos.add_task("T", callback=cb)
    with pytest.raises(ValueError):
        todos.submit("T", 5)

    # Side-effect present, but task not submitted
    assert side_effects == [5]
    assert todos.is_pending("T") is True
    assert todos.get_result("T") is None


def test_clear_submitted():
    todos: TodoList[str, str] = TodoList()
    todos.add_task("a")
    todos.add_task("b")
    todos.add_task("c")
    todos.submit("b", "done-b")
    todos.submit("c", "done-c")

    removed = todos.clear_submitted()
    assert removed == 2
    assert set(todos.keys()) == {"a"}
    assert todos.pending_count() == 1


def test_multiple_callbacks_and_mixed_operations():
    sink: list[str] = []

    def cb1(tid: str, value: str):  # CallbackType
        sink.append(f"{tid}:{value}")

    def cb2(tid: str, value: str):  # CallbackType
        sink.append(f"2-{tid}:{value}")

    todos: TodoList[str, str] = TodoList()
    todos.add_task("t1", callback=cb1)
    todos.add_task("t2", callback=cb2)
    todos.add_task("t3")

    todos.submit("t2", "v2")
    todos.submit("t1", "v1")

    # t3 still pending
    assert todos.is_pending("t3") is True
    assert set(t for t, _ in todos.yield_pending()) == {"t3"}

    assert sink == ["2-t2:v2", "t1:v1"]


def test_get_any_pending_and_pending_size_basic():
    todos: TodoList[str, int] = TodoList()
    assert todos.get_any_pending() is None
    assert todos.pending_size() == 0
    for i in range(5):
        todos.add_task(f"t{i}")
    assert todos.pending_size() == 5
    any_task = todos.get_any_pending()
    assert any_task is not None
    tid, data = any_task
    assert tid in {f"t{i}" for i in range(5)}
    assert data.id == tid


def test_get_any_pending_skips_submitted():
    todos: TodoList[int, int] = TodoList()
    for i in range(3):
        todos.add_task(i)
    todos.submit(1, 10)
    for _ in range(5):
        tid_data = todos.get_any_pending()
        assert tid_data is not None
        tid, _ = tid_data
        assert tid in {0, 2}


def test_pending_size_matches_pending_count():
    todos: TodoList[str, str] = TodoList()
    for name in ["a", "b", "c"]:
        todos.add_task(name)
    assert todos.pending_size() == 3
    assert todos.pending_count() == 3
    todos.submit("b", "x")
    assert todos.pending_size() == 2
    assert todos.pending_count() == 2


def test_get_any_pending_after_clear_submitted():
    todos: TodoList[str, str] = TodoList()
    todos.add_task("a")
    todos.add_task("b")
    todos.submit("a", "done")
    todos.clear_submitted()
    tid, _ = todos.get_any_pending()  # type: ignore
    assert tid == "b"
    todos.submit("b", "done")
    assert todos.get_any_pending() is None


def test_get_any_pending_recovers_from_stale_state():
    todos: TodoList[str, int] = TodoList()
    todos.add_task("x")
    stale_id = next(iter(todos._pending_ids))  # type: ignore[attr-defined]
    del todos[stale_id]
    assert todos.get_any_pending() is None
    assert todos.pending_size() == 0


def test_ordereddict_behavior():
    """Test that TodoList maintains insertion order like OrderedDict."""
    todos: TodoList[str, str] = TodoList()
    for i in range(5):
        todos.add_task(f"task_{i}")

    # Keys should be in insertion order
    keys_list = list(todos.keys())
    assert keys_list == [f"task_{i}" for i in range(5)]


def test_get_pending_tasks_basic():
    """Test get_pending_tasks method with basic functionality."""
    todos: TodoList[str, str] = TodoList()
    # Add tasks in order
    for i in range(5):
        todos.add_task(f"task_{i}")

    # All pending tasks should be returned in insertion order
    pending = todos.get_pending_tasks()
    assert pending == [f"task_{i}" for i in range(5)]

    # Submit some tasks
    todos.submit("task_1", "done")
    todos.submit("task_3", "done")

    # Only pending tasks should be returned
    pending_after = todos.get_pending_tasks()
    assert pending_after == ["task_0", "task_2", "task_4"]


def test_get_pending_tasks_with_limit_and_offset():
    """Test get_pending_tasks with limit and offset parameters."""
    todos: TodoList[str, str] = TodoList()
    for i in range(10):
        todos.add_task(f"task_{i}")

    # Test with limit only
    limited = todos.get_pending_tasks(limit=3)
    assert limited == ["task_0", "task_1", "task_2"]

    # Test with offset only
    offset_only = todos.get_pending_tasks(offset=5)
    assert offset_only == ["task_5", "task_6", "task_7", "task_8", "task_9"]

    # Test with both limit and offset
    limited_offset = todos.get_pending_tasks(limit=3, offset=2)
    assert limited_offset == ["task_2", "task_3", "task_4"]

    # Test edge cases
    empty_result = todos.get_pending_tasks(limit=5, offset=20)
    assert empty_result == []

    # Submit some tasks and test again
    todos.submit("task_1", "done")
    todos.submit("task_3", "done")

    # Should skip submitted tasks
    pending_with_offset = todos.get_pending_tasks(limit=3, offset=1)
    assert pending_with_offset == ["task_2", "task_4", "task_5"]


def test_recently_submitted_property():
    """Test recently_submitted read-only property."""
    todos: TodoList[str, str] = TodoList()

    # Initially empty
    assert todos.recently_submitted == []

    # Add and submit some tasks
    todos.add_task("task_1")
    todos.add_task("task_2")
    todos.add_task("task_3")

    todos.submit("task_1", "result_1")
    assert todos.recently_submitted == ["task_1"]

    todos.submit("task_3", "result_3")
    assert todos.recently_submitted == ["task_1", "task_3"]

    # Property should return a copy (read-only)
    submitted_copy = todos.recently_submitted
    submitted_copy.append("should_not_affect_original")
    assert todos.recently_submitted == ["task_1", "task_3"]


def test_get_recently_submitted_tasks():
    """Test get_recently_submitted_tasks method."""
    todos: TodoList[str, str] = TodoList()

    # Empty case
    assert todos.get_recently_submitted_tasks() == []
    assert todos.get_recently_submitted_tasks(n=10) == []

    # Add and submit tasks
    for i in range(10):
        todos.add_task(f"task_{i}")

    # Submit tasks in a specific order
    submit_order = [2, 5, 1, 7, 9, 0, 4]
    for task_idx in submit_order:
        todos.submit(f"task_{task_idx}", f"result_{task_idx}")

    # Test default n=5 (should return last 5 submitted)
    recent_5 = todos.get_recently_submitted_tasks()
    expected_last_5 = [f"task_{i}" for i in submit_order[-5:]]  # Last 5 from submit_order
    assert recent_5 == expected_last_5

    # Test with specific n=3 (should return last 3 submitted)
    recent_3 = todos.get_recently_submitted_tasks(n=3)
    expected_last_3 = [f"task_{i}" for i in submit_order[-3:]]  # Last 3 from submit_order
    assert recent_3 == expected_last_3

    # Test with n larger than available
    recent_10 = todos.get_recently_submitted_tasks(n=10)
    expected_all = [f"task_{i}" for i in submit_order]
    assert recent_10 == expected_all

    # Test with n=1
    recent_1 = todos.get_recently_submitted_tasks(n=1)
    assert recent_1 == [f"task_{submit_order[-1]}"]  # Last submitted task


def test_clear_submitted_updates_recently_submitted():
    """Test that clear_submitted also cleans up recently_submitted list."""
    todos: TodoList[str, str] = TodoList()

    # Add and submit some tasks
    for i in range(5):
        todos.add_task(f"task_{i}")

    todos.submit("task_1", "done")
    todos.submit("task_3", "done")

    assert todos.recently_submitted == ["task_1", "task_3"]

    # Clear submitted tasks
    removed = todos.clear_submitted()
    assert removed == 2

    # Recently submitted should be cleaned up
    assert todos.recently_submitted == []

    # Remaining tasks should still be there
    assert list(todos.keys()) == ["task_0", "task_2", "task_4"]


def test_recently_submitted_with_failed_callback():
    """Test that recently_submitted is not updated when callback fails."""
    todos: TodoList[str, str] = TodoList()

    def failing_callback(task_id: str, value: str):
        raise RuntimeError("callback failed")

    todos.add_task("task_1")
    todos.add_task("task_2", callback=failing_callback)

    # Normal submission should work
    todos.submit("task_1", "done")
    assert todos.recently_submitted == ["task_1"]

    # Failed callback should not update recently_submitted
    with pytest.raises(RuntimeError):
        todos.submit("task_2", "done")

    assert todos.recently_submitted == ["task_1"]  # Should not include task_2


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])  # manual debug
