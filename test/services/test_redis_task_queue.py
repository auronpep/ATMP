import json
import sys
import unittest
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.controllers.manager.redis_manager import RedisTaskManager
from app.models.schema import VideoParams
from app.services import task as tm


class _FakeRedisList:
    def __init__(self):
        self.items = []

    def rpush(self, _key, value):
        self.items.append(value)

    def lpop(self, _key):
        return self.items.pop(0) if self.items else None

    def llen(self, _key):
        return len(self.items)


def _manager():
    manager = RedisTaskManager.__new__(RedisTaskManager)
    manager.redis_client = _FakeRedisList()
    manager.queue = "task_queue"
    return manager


class TestRedisQueueSerialization(unittest.TestCase):
    """Tasks are JSON-serialised into Redis, so `VideoParams` has to survive a
    round trip and the callable has to be reconstructed by name."""

    def _task(self):
        return {
            "func": tm.start,
            "args": (),
            "kwargs": {"task_id": "t1", "params": VideoParams(video_subject="coffee")},
        }

    def test_round_trip_restores_params_and_callable(self):
        manager = _manager()
        manager.enqueue(self._task())

        restored = manager.dequeue()

        self.assertIs(restored["func"], tm.start)
        self.assertIsInstance(restored["kwargs"]["params"], VideoParams)
        self.assertEqual(restored["kwargs"]["params"].video_subject, "coffee")
        self.assertEqual(restored["kwargs"]["task_id"], "t1")

    def test_enqueue_does_not_mutate_the_callers_task(self):
        # dict.copy() is shallow: mutating ["kwargs"]["params"] on the copy also
        # replaced the caller's VideoParams instance with a plain dict.
        manager = _manager()
        task = self._task()

        manager.enqueue(task)

        self.assertIsInstance(task["kwargs"]["params"], VideoParams)
        self.assertIs(task["func"], tm.start)

    def test_enqueue_writes_plain_json(self):
        manager = _manager()
        manager.enqueue(self._task())

        payload = json.loads(manager.redis_client.items[0])

        self.assertEqual(payload["func"], "start")
        self.assertIsInstance(payload["kwargs"]["params"], dict)
        self.assertEqual(payload["kwargs"]["params"]["video_subject"], "coffee")

    def test_serialization_uses_no_deprecated_pydantic_api(self):
        # `.dict()` is deprecated in Pydantic v2 and removed in v3; the
        # controllers already use model_dump().
        manager = _manager()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            manager.enqueue(self._task())

        deprecations = [
            str(w.message) for w in caught if "`dict` method is deprecated" in str(w.message)
        ]
        self.assertEqual(deprecations, [])

    def test_dequeue_on_an_empty_queue_returns_none(self):
        self.assertIsNone(_manager().dequeue())

    def test_queue_size_and_emptiness_track_the_backing_list(self):
        manager = _manager()

        self.assertTrue(manager.is_queue_empty())
        self.assertEqual(manager.queue_size(), 0)

        manager.enqueue(self._task())

        self.assertFalse(manager.is_queue_empty())
        self.assertEqual(manager.queue_size(), 1)

    def test_queue_is_fifo(self):
        manager = _manager()
        for subject in ("first", "second"):
            task = self._task()
            task["kwargs"]["params"] = VideoParams(video_subject=subject)
            task["kwargs"]["task_id"] = subject
            manager.enqueue(task)

        self.assertEqual(manager.dequeue()["kwargs"]["task_id"], "first")
        self.assertEqual(manager.dequeue()["kwargs"]["task_id"], "second")


if __name__ == "__main__":
    unittest.main()
