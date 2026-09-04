import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import upload_post


class TestUploadVideoResponseShape(unittest.TestCase):
    """A non-dict body must not escape as AttributeError.

    AttributeError is not a RequestException, so it slips past the handler and
    propagates into the caller.
    """

    def setUp(self):
        self.original_app = dict(config.app)
        config.app.update(
            {
                "upload_post_api_key": "key",
                "upload_post_username": "user",
                "upload_post_enabled": True,
            }
        )
        self.service = upload_post.UploadPostService()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.video = os.path.join(tmp.name, "final-1.mp4")
        Path(self.video).write_bytes(b"x")

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def _upload(self, json_body):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = json_body
        with patch.object(upload_post.requests, "post", return_value=response):
            return self.service.upload_video(self.video, "title")

    def test_non_dict_response_is_reported_not_raised(self):
        for body in (["unexpected", "array"], "plain string", 42, None):
            with self.subTest(body=body):
                result = self._upload(body)

                self.assertIsInstance(result, dict)
                self.assertFalse(result["success"])
                self.assertIn("unexpected response type", result["error"])

    def test_successful_dict_response_is_passed_through(self):
        result = self._upload({"success": True, "request_id": "req-1"})

        self.assertTrue(result["success"])
        self.assertEqual(result["request_id"], "req-1")

    def test_failure_dict_response_is_passed_through(self):
        result = self._upload({"success": False, "message": "quota exceeded"})

        self.assertFalse(result["success"])


class TestCrossPostDoesNotFailTheTask(unittest.TestCase):
    """Cross-posting runs after the videos exist on disk, so nothing it does may
    stop the task reaching TASK_STATE_COMPLETE. Drives the real task.start()."""

    def setUp(self):
        from app.models import const
        from app.models.schema import VideoParams
        from app.services import task as tm

        self.tm = tm
        self.const = const
        self.params = VideoParams(video_subject="a day in Shanghai")
        self.original_app = dict(config.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def _start(self, cross_post_side_effect):
        service = MagicMock()
        service.is_configured.return_value = True
        service.auto_upload = True
        service.platforms = ["tiktok"]
        service.youtube_privacy_status = "public"

        recorded = {}

        def record(task_id, state=None, progress=0, **kwargs):
            recorded["state"] = state
            recorded["progress"] = progress
            recorded.update(kwargs)

        with patch.object(self.tm, "generate_script", return_value="a script"),              patch.object(self.tm, "generate_terms", return_value=["term"]),              patch.object(self.tm, "generate_audio", return_value=("/a.mp3", 10, object())),              patch.object(self.tm, "generate_subtitle", return_value="/s.srt"),              patch.object(self.tm, "get_video_materials", return_value=["/m.mp4"]),              patch.object(
                 self.tm, "generate_final_videos",
                 return_value=(["/tasks/t/final-1.mp4"], ["/tasks/t/combined-1.mp4"]),
             ),              patch.object(self.tm.upload_post, "upload_post_service", service),              patch.object(
                 self.tm.upload_post, "cross_post_video", side_effect=cross_post_side_effect
             ),              patch.object(self.tm.sm.state, "update_task", side_effect=record):
            result = self.tm.start("t", self.params)
        return result, recorded

    def test_task_completes_even_when_cross_post_raises(self):
        # AttributeError is not a RequestException, so it escaped upload_video
        # and killed the task after the videos were already on disk.
        result, recorded = self._start(
            AttributeError("'list' object has no attribute 'get'")
        )

        self.assertIsNotNone(result, "task returned nothing - it died mid-flight")
        self.assertEqual(result["videos"], ["/tasks/t/final-1.mp4"])
        self.assertEqual(recorded["state"], self.const.TASK_STATE_COMPLETE)
        self.assertEqual(recorded["progress"], 100)

    def test_the_cross_post_failure_is_still_reported_in_the_result(self):
        result, _ = self._start(RuntimeError("upload endpoint down"))

        failures = result["cross_post_results"]
        self.assertEqual(len(failures), 1)
        self.assertFalse(failures[0]["success"])
        self.assertIn("upload endpoint down", failures[0]["error"])

    def test_non_dict_cross_post_result_is_normalised(self):
        result, recorded = self._start(lambda **kwargs: ["oops"])

        self.assertEqual(recorded["state"], self.const.TASK_STATE_COMPLETE)
        self.assertFalse(result["cross_post_results"][0]["success"])

    def test_successful_cross_post_is_preserved(self):
        result, recorded = self._start(lambda **kwargs: {"success": True})

        self.assertEqual(recorded["state"], self.const.TASK_STATE_COMPLETE)
        self.assertTrue(result["cross_post_results"][0]["success"])


if __name__ == "__main__":
    unittest.main()
