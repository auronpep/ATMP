import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import const
from app.models.schema import VideoParams
from app.services import task as tm


class TestStartStopAtBranches(unittest.TestCase):
    """`stop_at` lets the API return partway through the pipeline.

    /api/v1/scripts, /api/v1/terms, /api/v1/audio and /api/v1/subtitle all route
    into `start()` with a different `stop_at`, so each early exit must (a) stop
    before the next stage runs and (b) still mark the task COMPLETE at 100 —
    an early return that forgets the state update leaves the caller polling a
    task that is finished but never says so.
    """

    def setUp(self):
        self.params = VideoParams(video_subject="coffee")

    def _start(self, stop_at):
        recorded = []

        def record(task_id, state=None, progress=0, **kwargs):
            recorded.append({"state": state, "progress": progress, **kwargs})

        stages = {
            "generate_script": "a script",
            "generate_terms": ["coffee shop"],
            "generate_audio": ("/a.mp3", 10, object()),
            "generate_subtitle": "/s.srt",
            "get_video_materials": ["/m.mp4"],
            "generate_final_videos": (["/final-1.mp4"], ["/combined-1.mp4"]),
        }
        patches = [patch.object(tm, name, return_value=value) for name, value in stages.items()]
        mocks = {}
        for name, p in zip(stages, patches):
            mocks[name] = p.start()
            self.addCleanup(p.stop)

        with patch.object(tm.sm.state, "update_task", side_effect=record):
            result = tm.start("task-1", self.params, stop_at=stop_at)
        return result, recorded, mocks

    def _final(self, recorded):
        return recorded[-1]

    def test_stop_at_script_returns_the_script_and_completes(self):
        result, recorded, mocks = self._start("script")

        self.assertEqual(result, {"script": "a script"})
        self.assertEqual(self._final(recorded)["state"], const.TASK_STATE_COMPLETE)
        self.assertEqual(self._final(recorded)["progress"], 100)
        mocks["generate_terms"].assert_not_called()

    def test_stop_at_terms_returns_terms_and_does_not_synthesise_audio(self):
        result, recorded, mocks = self._start("terms")

        # The terms stop also returns the script it was derived from.
        self.assertEqual(result["terms"], ["coffee shop"])
        self.assertEqual(result["script"], "a script")
        self.assertEqual(self._final(recorded)["state"], const.TASK_STATE_COMPLETE)
        mocks["generate_audio"].assert_not_called()

    def test_stop_at_audio_returns_the_audio_and_skips_subtitles(self):
        result, recorded, mocks = self._start("audio")

        self.assertEqual(result["audio_file"], "/a.mp3")
        self.assertEqual(result["audio_duration"], 10)
        self.assertEqual(self._final(recorded)["state"], const.TASK_STATE_COMPLETE)
        mocks["generate_subtitle"].assert_not_called()

    def test_stop_at_subtitle_returns_the_srt_and_downloads_no_materials(self):
        result, recorded, mocks = self._start("subtitle")

        self.assertEqual(result, {"subtitle_path": "/s.srt"})
        self.assertEqual(self._final(recorded)["state"], const.TASK_STATE_COMPLETE)
        mocks["get_video_materials"].assert_not_called()

    def test_stop_at_materials_returns_materials_and_renders_nothing(self):
        result, recorded, mocks = self._start("materials")

        self.assertEqual(result, {"materials": ["/m.mp4"]})
        self.assertEqual(self._final(recorded)["state"], const.TASK_STATE_COMPLETE)
        mocks["generate_final_videos"].assert_not_called()

    def test_default_runs_the_whole_pipeline(self):
        result, recorded, mocks = self._start("video")

        self.assertEqual(result["videos"], ["/final-1.mp4"])
        self.assertEqual(result["combined_videos"], ["/combined-1.mp4"])
        self.assertEqual(self._final(recorded)["state"], const.TASK_STATE_COMPLETE)
        mocks["generate_final_videos"].assert_called_once()

    def test_every_stop_at_reaches_progress_100(self):
        for stop_at in ("script", "terms", "audio", "subtitle", "materials", "video"):
            with self.subTest(stop_at=stop_at):
                _, recorded, _ = self._start(stop_at)
                self.assertEqual(self._final(recorded)["progress"], 100)

    def test_every_stop_at_returns_a_non_empty_result(self):
        # cli.py treats a falsy result as failure and exits 1.
        for stop_at in ("script", "terms", "audio", "subtitle", "materials", "video"):
            with self.subTest(stop_at=stop_at):
                result, _, _ = self._start(stop_at)
                self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
