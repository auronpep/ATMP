import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import const
from app.services.state import MemoryState


class TestMemoryStateBasics(unittest.TestCase):
    """Default backend when `enable_redis` is off, which is the shipped config.
    It is what `GET /api/v1/tasks/{id}` reads."""

    def setUp(self):
        self.state = MemoryState()

    def test_defaults_to_processing_at_zero(self):
        self.state.update_task("t1")

        task = self.state.get_task("t1")
        self.assertEqual(task["task_id"], "t1")
        self.assertEqual(task["state"], const.TASK_STATE_PROCESSING)
        self.assertEqual(task["progress"], 0)

    def test_progress_is_clamped_to_100(self):
        self.state.update_task("t1", progress=250)

        self.assertEqual(self.state.get_task("t1")["progress"], 100)

    def test_progress_is_coerced_to_int(self):
        self.state.update_task("t1", progress=42.9)

        progress = self.state.get_task("t1")["progress"]
        self.assertIsInstance(progress, int)
        self.assertEqual(progress, 42)

    def test_extra_fields_are_stored(self):
        self.state.update_task("t1", videos=["/a.mp4"], audio_duration=12.5)

        task = self.state.get_task("t1")
        self.assertEqual(task["videos"], ["/a.mp4"])
        self.assertEqual(task["audio_duration"], 12.5)

    def test_missing_task_returns_none(self):
        self.assertIsNone(self.state.get_task("nope"))

    def test_delete_removes_the_task(self):
        self.state.update_task("t1")
        self.state.delete_task("t1")

        self.assertIsNone(self.state.get_task("t1"))

    def test_deleting_an_unknown_task_is_a_no_op(self):
        self.state.delete_task("never-existed")  # must not raise

    def test_failed_state_round_trips(self):
        self.state.update_task("t1", state=const.TASK_STATE_FAILED)

        self.assertEqual(self.state.get_task("t1")["state"], const.TASK_STATE_FAILED)


class TestMemoryStatePagination(unittest.TestCase):
    def setUp(self):
        self.state = MemoryState()
        for i in range(5):
            self.state.update_task(f"t{i}", progress=i)

    def test_total_is_the_full_count_not_the_page_size(self):
        _, total = self.state.get_all_tasks(page=1, page_size=2)

        self.assertEqual(total, 5)

    def test_pages_partition_the_tasks(self):
        seen = []
        for page in (1, 2, 3):
            tasks, _ = self.state.get_all_tasks(page=page, page_size=2)
            seen.extend(t["task_id"] for t in tasks)

        self.assertEqual(sorted(seen), [f"t{i}" for i in range(5)])
        self.assertEqual(len(seen), len(set(seen)))

    def test_a_page_beyond_the_end_is_empty(self):
        tasks, total = self.state.get_all_tasks(page=99, page_size=2)

        self.assertEqual(tasks, [])
        self.assertEqual(total, 5)

    def test_returned_tasks_are_snapshots_not_live_references(self):
        tasks, _ = self.state.get_all_tasks(page=1, page_size=5)
        tasks[0]["progress"] = 999

        self.assertNotEqual(self.state.get_task(tasks[0]["task_id"])["progress"], 999)


class TestMemoryStateReplacesRatherThanMerges(unittest.TestCase):
    """Documents a real difference between the two backends.

    `MemoryState.update_task` assigns a whole new dict, so a later partial
    update drops earlier extra fields. `RedisState.update_task` writes
    field-by-field with `hset`, so it merges and keeps them.

    No current caller depends on the merge: `task.start()` sends every result
    field in its final COMPLETE update, and the intermediate progress ticks
    carry nothing else. Pinned here so the divergence is visible rather than
    discovered by switching `enable_redis` and seeing different API output.
    """

    def test_a_later_partial_update_drops_earlier_fields(self):
        state = MemoryState()
        state.update_task("t1", videos=["/a.mp4"])
        state.update_task("t1", progress=50)

        task = state.get_task("t1")
        self.assertEqual(task["progress"], 50)
        self.assertNotIn("videos", task)

    def test_a_single_update_carrying_everything_is_retained(self):
        # The pattern task.start() actually uses.
        state = MemoryState()
        state.update_task(
            "t1",
            state=const.TASK_STATE_COMPLETE,
            progress=100,
            videos=["/a.mp4"],
            audio_duration=12.5,
        )

        task = state.get_task("t1")
        self.assertEqual(task["videos"], ["/a.mp4"])
        self.assertEqual(task["audio_duration"], 12.5)
        self.assertEqual(task["state"], const.TASK_STATE_COMPLETE)


if __name__ == "__main__":
    unittest.main()
