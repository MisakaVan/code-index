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
    todos: TodoList[str, int] = TodoList()
    todos.add_task("job")
    assert todos.get_result("job") is None
    assert todos.is_pending("job") is True

    todos.submit("job", 99)
    assert todos.is_pending("job") is False
    assert todos.get_result("job") == 99

    # double submit => error
    with pytest.raises(ValueError):
        todos.submit("job", 100)


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


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])  # manual debug
