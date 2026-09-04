import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.controllers.manager import base_manager
from app.controllers.manager.base_manager import TaskQueueFullError
from app.controllers.manager.memory_manager import InMemoryTaskManager


class _DeferredThread:
    """A thread that is created but not yet scheduled by the OS.

    That window is exactly when a second request reaches ``add_task``. The real
    ``threading.Thread`` gives no control over it, so the test models it.
    """

    created = []

    def __init__(self, target=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        _DeferredThread.created.append(self)

    def start(self):
        pass

    def run_now(self):
        self._target(*self._args, **self._kwargs)


class TestConcurrencySlotReservation(unittest.TestCase):
    """`max_concurrent_tasks` must be enforced by the time add_task returns."""

    def setUp(self):
        _DeferredThread.created = []

    def test_second_task_is_queued_not_started_when_limit_is_one(self):
        manager = InMemoryTaskManager(max_concurrent_tasks=1, max_queued_tasks=10)

        with patch.object(base_manager.threading, "Thread", _DeferredThread):
            manager.add_task(lambda: None)
            # The worker has not run yet - this is the production race window.
            manager.add_task(lambda: None)

        self.assertEqual(
            len(_DeferredThread.created),
            1,
            "a second render was started past max_concurrent_tasks",
        )
        self.assertEqual(manager.queue_size(), 1)

    def test_queue_limit_is_reached_instead_of_unbounded_parallelism(self):
        manager = InMemoryTaskManager(max_concurrent_tasks=1, max_queued_tasks=2)

        with patch.object(base_manager.threading, "Thread", _DeferredThread):
            for _ in range(3):
                manager.add_task(lambda: None)

            with self.assertRaises(TaskQueueFullError):
                manager.add_task(lambda: None)

        self.assertEqual(len(_DeferredThread.created), 1)
        self.assertEqual(manager.queue_size(), 2)

    def test_slot_is_released_after_the_task_finishes(self):
        manager = InMemoryTaskManager(max_concurrent_tasks=1, max_queued_tasks=10)
        done = threading.Event()

        manager.add_task(done.set)

        self.assertTrue(done.wait(5), "task never ran")
        for _ in range(50):
            if manager.current_tasks == 0:
                break
            threading.Event().wait(0.02)
        self.assertEqual(manager.current_tasks, 0)

    def test_queued_task_runs_once_the_slot_frees_up(self):
        manager = InMemoryTaskManager(max_concurrent_tasks=1, max_queued_tasks=10)
        first_may_finish = threading.Event()
        second_ran = threading.Event()

        manager.add_task(first_may_finish.wait, 5)
        # Wait until the slot is actually held before enqueuing the second task.
        for _ in range(250):
            if manager.current_tasks == 1:
                break
            threading.Event().wait(0.02)
        self.assertEqual(manager.current_tasks, 1)

        manager.add_task(second_ran.set)
        self.assertEqual(manager.queue_size(), 1)

        first_may_finish.set()
        self.assertTrue(second_ran.wait(5), "queued task was never drained")


if __name__ == "__main__":
    unittest.main()
