import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.controllers.v1.video import _sanitize_upload_filename, _task_file_to_uri
from app.models.exception import HttpException
from app.utils import utils


class TestSanitizeUploadFilename(unittest.TestCase):
    """Browsers and API clients control this string entirely, and the result is
    joined onto a server directory. Only a bare filename may survive."""

    def _sanitize(self, name):
        return _sanitize_upload_filename(name, "request-1")

    def test_plain_filename_passes_through(self):
        self.assertEqual(self._sanitize("track.mp3"), "track.mp3")

    def test_posix_directory_components_are_dropped(self):
        self.assertEqual(self._sanitize("dir/sub/track.mp3"), "track.mp3")

    def test_windows_directory_components_are_dropped(self):
        self.assertEqual(self._sanitize(r"C:\Windows\System32\evil.mp3"), "evil.mp3")

    def test_traversal_segments_are_dropped(self):
        self.assertEqual(self._sanitize("../../etc/passwd"), "passwd")

    def test_absolute_paths_are_reduced_to_the_basename(self):
        self.assertEqual(self._sanitize("/var/www/x.mp3"), "x.mp3")

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(self._sanitize("  spaced.mp3  "), "spaced.mp3")

    def test_dot_segments_and_empty_names_are_rejected(self):
        for name in ("", ".", "..", "   ", "dir/", None):
            with self.subTest(name=name):
                with self.assertRaises(HttpException) as ctx:
                    self._sanitize(name)
                self.assertEqual(ctx.exception.status_code, 400)

    def test_result_never_contains_a_separator(self):
        for name in ("a/b/c.mp3", r"a\b\c.mp3", "../x.mp3"):
            with self.subTest(name=name):
                result = self._sanitize(name)
                self.assertNotIn("/", result)
                self.assertNotIn("\\", result)


class TestTaskFileToUri(unittest.TestCase):
    """Turns a stored task output path into a client-facing URL."""

    @classmethod
    def setUpClass(cls):
        cls.tasks_dir = utils.task_dir()
        cls.task_id = "test-uri-helper"
        cls.task_path = utils.task_dir(cls.task_id)
        cls.video = os.path.join(cls.task_path, "final-1.mp4")
        Path(cls.video).write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.task_path, ignore_errors=True)

    def _uri(self, value, endpoint="https://host"):
        return _task_file_to_uri(value, endpoint, self.tasks_dir, "request-1")

    def test_task_output_becomes_an_absolute_url(self):
        self.assertEqual(
            self._uri(self.video), f"https://host/tasks/{self.task_id}/final-1.mp4"
        )

    def test_backslashes_are_normalised_to_forward_slashes(self):
        self.assertNotIn("\\", self._uri(self.video))

    def test_empty_endpoint_yields_a_relative_path(self):
        self.assertEqual(
            self._uri(self.video, endpoint=""), f"/tasks/{self.task_id}/final-1.mp4"
        )

    def test_existing_urls_are_passed_through_untouched(self):
        for url in ("https://cdn.example/x.mp4", "http://a/b.mp4"):
            with self.subTest(url=url):
                self.assertEqual(self._uri(url), url)

    def test_paths_outside_the_task_directory_are_not_turned_into_urls(self):
        # Stale/hostile state must not be dressed up as a fetchable link.
        escaping = os.path.join(self.tasks_dir, "..", "escape.mp4")

        result = self._uri(escaping)

        self.assertEqual(result, escaping)
        self.assertFalse(result.startswith("https://host/tasks/"))

    def test_non_string_values_are_returned_unchanged(self):
        self.assertEqual(self._uri(123), 123)


if __name__ == "__main__":
    unittest.main()
