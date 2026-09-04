import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import upload_post


def _service(**overrides):
    settings = {
        "upload_post_api_key": "key",
        "upload_post_username": "user",
        "upload_post_enabled": True,
    }
    settings.update(overrides)
    config.app.update(settings)
    return upload_post.UploadPostService()


class TestIsConfigured(unittest.TestCase):
    """Cross-posting publishes to a user's real social accounts, so it must be
    off unless a key, a username AND the enable flag are all present."""

    def setUp(self):
        self.original_app = dict(config.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def test_all_three_present_enables_it(self):
        self.assertTrue(_service().is_configured())

    def test_each_missing_setting_disables_it(self):
        for missing in (
            {"upload_post_api_key": ""},
            {"upload_post_username": ""},
            {"upload_post_enabled": False},
        ):
            with self.subTest(missing=missing):
                self.assertFalse(_service(**missing).is_configured())

    def test_defaults_are_off(self):
        for key in (
            "upload_post_api_key",
            "upload_post_username",
            "upload_post_enabled",
            "upload_post_auto_upload",
        ):
            config.app.pop(key, None)
        service = upload_post.UploadPostService()

        self.assertFalse(service.is_configured())
        self.assertFalse(service.auto_upload)


class TestUploadVideoGuards(unittest.TestCase):
    """Both guards must fail closed and return the module's result shape."""

    def setUp(self):
        self.original_app = dict(config.app)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.video = os.path.join(self._tmp.name, "final-1.mp4")
        Path(self.video).write_bytes(b"x")

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def test_unconfigured_service_never_calls_the_api(self):
        service = _service(upload_post_enabled=False)

        with patch.object(upload_post.requests, "post") as post:
            result = service.upload_video(self.video, "title")

        post.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("not configured", result["error"])

    def test_missing_video_file_never_calls_the_api(self):
        service = _service()

        with patch.object(upload_post.requests, "post") as post:
            result = service.upload_video("/does/not/exist.mp4", "title")

        post.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_network_failure_returns_the_error_shape(self):
        import requests as _requests

        service = _service()
        with patch.object(
            upload_post.requests,
            "post",
            side_effect=_requests.exceptions.ConnectionError("down"),
        ):
            result = service.upload_video(self.video, "title")

        self.assertFalse(result["success"])
        self.assertIn("down", result["error"])

    def test_title_is_capped_for_the_api(self):
        service = _service()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": True}

        with patch.object(upload_post.requests, "post", return_value=response) as post:
            service.upload_video(self.video, "T" * 5000)

        data = dict(post.call_args.kwargs["data"])
        self.assertLessEqual(len(data["title"]), 2200)


class TestCheckStatus(unittest.TestCase):
    def setUp(self):
        self.original_app = dict(config.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def test_status_payload_is_returned(self):
        service = _service()
        response = SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"status": "done"}
        )

        with patch.object(upload_post.requests, "get", return_value=response) as get:
            result = service.check_status("req-1")

        self.assertEqual(result, {"status": "done"})
        self.assertEqual(get.call_args.kwargs["params"], {"request_id": "req-1"})
        self.assertTrue(get.call_args.kwargs["timeout"])

    def test_failure_returns_the_error_shape(self):
        import requests as _requests

        service = _service()
        with patch.object(
            upload_post.requests,
            "get",
            side_effect=_requests.exceptions.Timeout("slow"),
        ):
            result = service.check_status("req-1")

        self.assertFalse(result["success"])


class TestCrossPostVideoDelegation(unittest.TestCase):
    def test_arguments_reach_upload_video_intact(self):
        captured = {}

        def fake_upload(video_path, title, platforms=None, **kwargs):
            captured.update(
                video_path=video_path, title=title, platforms=platforms, **kwargs
            )
            return {"success": True}

        with patch.object(
            upload_post.upload_post_service, "upload_video", side_effect=fake_upload
        ):
            upload_post.cross_post_video(
                "/v.mp4", "My title", ["tiktok"], youtube_extra={"tags": ["a"]}
            )

        self.assertEqual(captured["video_path"], "/v.mp4")
        self.assertEqual(captured["title"], "My title")
        self.assertEqual(captured["platforms"], ["tiktok"])
        self.assertEqual(captured["youtube_extra"], {"tags": ["a"]})


if __name__ == "__main__":
    unittest.main()
