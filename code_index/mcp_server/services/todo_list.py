"""A todolist class for managing tasks in memory for agents.

This class provides methods to initialize tasks, add new tasks,
submit completed tasks, yield a task for processing, etc.

Support a callback function to be called when a task is submitted.

TodoList subclasses from a dict (key is the id and value is some datablock,
including the callback). It is generic: each task is identified by a unique key
of type IdType (which MUST be hashable), and waits for a submission value of
type SubmitType.

Callback semantics:
    A task is only marked as submitted (and its "submitted" flag set, result stored)
    after the per‑task callback (if provided) returns successfully. If the callback
    raises an exception, the exception is propagated to the caller of `submit` and
    the task remains pending (its state is not mutated to a submitted state).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterator
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

IdType = TypeVar("IdType", bound=Hashable)
SubmitType = TypeVar("SubmitType")
CallbackType = Callable[[IdType, SubmitType], None]


@dataclass(slots=True)
class TaskData(Generic[IdType, SubmitType]):
    """Container storing per-task data and callback.

    Attributes:
        id: Identifier for the task (must be hashable).
        payload: Arbitrary payload / metadata associated with the task.
        callback: Optional callback invoked with (task_id, submitted_value) upon submission.
            The task's state is updated to submitted only if this callback returns
            without raising. Any exception is propagated and the task stays pending.
        submitted: Flag indicating whether the task has been submitted.
        result: The submitted value (when available).
    """

    id: IdType
    payload: Any | None = None
    callback: Optional[CallbackType] = None
    submitted: bool = False
    result: Optional[SubmitType] = None
    # Additional extensible metadata store
    extra: dict[str, Any] = field(default_factory=dict)


class TodoList(dict[IdType, TaskData[IdType, SubmitType]], Generic[IdType, SubmitType]):
    """In‑memory todolist mapping task ids to TaskData.

    This is a lightweight coordination structure for agents. Tasks can be
    registered (added), iterated over for processing, and later *submitted*
    with a result value. An optional callback per task is invoked exactly once
    when the task is submitted successfully.

    Type Parameters:
        IdType: Hashable type used for task identifiers (must satisfy collections.abc.Hashable).
        SubmitType: Type of the value expected upon task submission.

    Callback success semantics:
        The submission process performs these steps atomically from the user's
        perspective:
          1. Look up pending task.
          2. Execute callback (if present) with (task_id, value).
          3. If the callback returns normally, mark task as submitted and store result.
          4. If the callback raises, propagate the exception and DO NOT mark submitted.

    Typical usage example::

        todos: TodoList[str, str] = TodoList()
        todos.add_task("task-1", payload={"objective": "fetch data"})
        for task_id, data in todos.yield_pending():
            # process ... then submit
            todos.submit(task_id, "done")

    Attributes:
        (Inherited mapping) Keys are task ids, values are TaskData objects.

    Note:
        Only the public API (methods below) should be relied upon; direct
        mutation of the underlying dict entries is discouraged.
    """

    # ---------------------------------------------------------------------
    # Creation & basic inspection
    # ---------------------------------------------------------------------
    def __init__(self) -> None:  # noqa: D401 - simple initializer
        """Initialize an empty todolist."""
        super().__init__()
        # Track ids of tasks not yet submitted for O(1) size & sampling.
        self._pending_ids: set[IdType] = set()

    # ------------------------------------------------------------------
    # Task management API
    # ------------------------------------------------------------------
    def add_task(
        self,
        task_id: IdType,
        payload: Any | None = None,
        callback: CallbackType | None = None,
        **extra: Any,
    ) -> None:
        """Register a new task.

        Args:
            task_id: Unique hashable identifier for the task. Must not already exist.
            payload: Optional task metadata / payload for processing.
            callback: Optional function invoked upon successful submission.
                If it raises, the task remains pending and the exception bubbles up.
            **extra: Additional keyword metadata stored with the task.

        Raises:
            KeyError: If the task id already exists.
        """
        if task_id in self:
            raise KeyError(f"Task id already exists: {task_id!r}")
        self[task_id] = TaskData(id=task_id, payload=payload, callback=callback, extra=dict(extra))
        self._pending_ids.add(task_id)

    def submit(self, task_id: IdType, value: SubmitType) -> None:
        """Submit a completed task with its result value.

        Invokes the registered callback (if any) exactly once. The task is only
        marked submitted (and its result stored) if the callback returns
        successfully. If the callback raises, the task remains pending and the
        exception is propagated.

        Args:
            task_id: Identifier of the task to submit.
            value: The submission value / result.

        Raises:
            KeyError: If the task id does not exist.
            ValueError: If the task was already submitted.
            Exception: Any exception raised by the callback is passed through.
        """
        if task_id not in self:
            raise KeyError(f"Task id not found: {task_id!r}")
        data = self[task_id]
        if data.submitted:
            raise ValueError(f"Task already submitted: {task_id!r}")

        # Run callback first; only mutate state on success
        if data.callback is not None:
            data.callback(task_id, value)  # may raise

        # Mark submitted
        data.result = value
        data.submitted = True
        # remove from pending set
        self._pending_ids.discard(task_id)

    def yield_pending(self) -> Iterator[tuple[IdType, TaskData[IdType, SubmitType]]]:
        """Iterate over tasks that have not yet been submitted.

        Yields:
            Tuples of (task_id, TaskData) for each pending (unsubmitted) task.
        """
        for tid in list(self._pending_ids):  # list() to avoid modification issues
            data = self[tid]
            if not data.submitted:  # sanity check
                yield tid, data
            else:
                self._pending_ids.discard(tid)

    def is_pending(self, task_id: IdType) -> bool:
        """Return whether a task is still pending (not yet submitted).

        Args:
            task_id: Identifier of the task to check.

        Returns:
            True if the task exists and has not been submitted.

        Raises:
            KeyError: If the task id does not exist.
        """
        if task_id not in self:
            raise KeyError(f"Task id not found: {task_id!r}")
        return task_id in self._pending_ids and not self[task_id].submitted

    def pending_count(self) -> int:
        """Return the number of pending (unsubmitted) tasks.

        Returns:
            Number of tasks not yet submitted.
        """
        # kept for backward compatibility; delegates to pending_size (O(1))
        return self.pending_size()

    def pending_size(self) -> int:
        """O(1) number of unsubmitted tasks.

        Returns:
            Count of tasks that have not been submitted.
        """
        return len(self._pending_ids)

    def get_any_pending(self) -> tuple[IdType, TaskData[IdType, SubmitType]] | None:
        """Return an arbitrary pending task without removing it.

        Returns:
            (task_id, TaskData) if any task pending, else None.
        """
        if not self._pending_ids:
            return None
        tid = next(iter(self._pending_ids))
        # Clean up if somehow already marked submitted (stale)
        data = self.get(tid)
        if data is None:
            self._pending_ids.discard(tid)
            return self.get_any_pending()
        if data.submitted:
            self._pending_ids.discard(tid)
            return self.get_any_pending()
        return tid, data

    def clear_submitted(self) -> int:
        """Remove submitted tasks from the list.

        Returns:
            The number of tasks removed.
        """
        to_remove = [tid for tid, data in self.items() if data.submitted]
        for tid in to_remove:
            del self[tid]
            self._pending_ids.discard(tid)
        return len(to_remove)

    # ------------------------------------------------------------------
    # Optional convenience helpers
    # ------------------------------------------------------------------
    def get_result(self, task_id: IdType) -> Optional[SubmitType]:
        """Return the submitted result for a task, if available.

        Args:
            task_id: Identifier of the task.

        Returns:
            The submission value if the task has been submitted, else None.

        Raises:
            KeyError: If the task id does not exist.
        """
        if task_id not in self:
            raise KeyError(f"Task id not found: {task_id!r}")
        data = self[task_id]
        return data.result if data.submitted else None


__all__ = [
    "TaskData",
    "TodoList",
    "IdType",
    "SubmitType",
    "CallbackType",
]
