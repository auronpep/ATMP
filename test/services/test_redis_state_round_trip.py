import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import const
from app.services.state import RedisState


class _RoundTripRedis:
    """Minimal hash store that behaves like redis-py: bytes in, bytes out."""

    def __init__(self):
        self.hashes = {}

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field.encode("utf-8")] = str(value).encode("utf-8")

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def delete(self, key):
        self.hashes.pop(key, None)


def _state():
    state = RedisState.__new__(RedisState)
    state._redis = _RoundTripRedis()
    return state


class TestRedisStateRoundTrip(unittest.TestCase):
    """Task state is written as strings and parsed back on read. The parse has
    to restore the types the API response model declares."""

    def test_state_and_progress_come_back_as_integers(self):
        state = _state()
        state.update_task("t1", state=const.TASK_STATE_COMPLETE, progress=100)

        task = state.get_task("t1")

        self.assertEqual(task["task_id"], "t1")
        self.assertEqual(task["state"], const.TASK_STATE_COMPLETE)
        self.assertEqual(task["progress"], 100)
        self.assertIsInstance(task["progress"], int)

    def test_progress_is_clamped_to_100(self):
        state = _state()
        state.update_task("t1", progress=250)

        self.assertEqual(state.get_task("t1")["progress"], 100)

    def test_failed_state_round_trips_as_a_negative_int(self):
        state = _state()
        state.update_task("t1", state=const.TASK_STATE_FAILED)

        self.assertEqual(state.get_task("t1")["state"], const.TASK_STATE_FAILED)

    def test_list_results_survive_the_round_trip(self):
        state = _state()
        videos = ["/tasks/t1/final-1.mp4", "/tasks/t1/final-2.mp4"]
        state.update_task("t1", videos=videos, terms=["cat", "dog"])

        task = state.get_task("t1")

        self.assertEqual(task["videos"], videos)
        self.assertEqual(task["terms"], ["cat", "dog"])

    def test_float_duration_survives_the_round_trip(self):
        state = _state()
        state.update_task("t1", audio_duration=12.5)

        self.assertEqual(state.get_task("t1")["audio_duration"], 12.5)

    def test_ordinary_text_is_returned_unchanged(self):
        state = _state()
        for text in ("a day in Shanghai", "Coffee & Tea", "2024-01-02", "1-2"):
            with self.subTest(text=text):
                state.update_task("t1", script=text)
                self.assertEqual(state.get_task("t1")["script"], text)

    def test_uuid_task_ids_are_not_reinterpreted(self):
        state = _state()
        task_id = "8f14e45f-ceea-467a-9a34-1c2b3d4e5f60"
        state.update_task(task_id)

        self.assertEqual(state.get_task(task_id)["task_id"], task_id)

    def test_missing_task_returns_none(self):
        self.assertIsNone(_state().get_task("nope"))

    def test_delete_removes_the_task(self):
        state = _state()
        state.update_task("t1")
        state.delete_task("t1")

        self.assertIsNone(state.get_task("t1"))

    def test_later_updates_merge_rather_than_replace(self):
        state = _state()
        state.update_task("t1", videos=["/a.mp4"])
        state.update_task("t1", progress=60)

        task = state.get_task("t1")

        self.assertEqual(task["progress"], 60)
        self.assertEqual(task["videos"], ["/a.mp4"])

    def test_literal_looking_text_is_reinterpreted(self):
        """Documents a sharp edge rather than asserting it is desirable.

        Values are restored with ast.literal_eval, so a stored string that
        happens to look like a Python literal does NOT come back as a string.
        Harmless for the fields the pipeline actually writes (paths, lists,
        numbers), but worth knowing before storing free text here.
        """
        state = _state()
        for text, restored in (("None", None), ("True", True), ("007", 7)):
            with self.subTest(text=text):
                state.update_task("t1", script=text)
                self.assertEqual(state.get_task("t1")["script"], restored)


if __name__ == "__main__":
    unittest.main()
