import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils


class TestUploadWriteSafety(unittest.TestCase):
    """Uploads stream to a temp file and land atomically.

    Reading the whole upload with `file.read()` turns a large material into an
    equally large memory spike, and opening the destination with "wb+" truncates
    an existing good file before the new bytes exist.
    """

    @classmethod
    def setUpClass(cls):
        from starlette.testclient import TestClient

        from app.asgi import app

        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.song_dir = utils.song_dir()

    def _post(self, filename, payload):
        return self.client.post(
            "/api/v1/musics",
            files={"file": (filename, io.BytesIO(payload), "audio/mpeg")},
        )

    def _track(self, filename):
        path = os.path.join(self.song_dir, filename)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_upload_content_is_written_verbatim(self):
        path = self._track("pr-test-write.mp3")
        payload = bytes(range(256)) * 32

        self.assertEqual(self._post("pr-test-write.mp3", payload).status_code, 200)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), payload)

    def test_upload_larger_than_one_chunk_is_written_completely(self):
        path = self._track("pr-test-big.mp3")
        payload = b"Z" * (3 * 1024 * 1024 + 7)  # spans several copy chunks

        self.assertEqual(self._post("pr-test-big.mp3", payload).status_code, 200)
        self.assertEqual(os.path.getsize(path), len(payload))

    def test_reupload_replaces_the_previous_content(self):
        path = self._track("pr-test-replace.mp3")

        self._post("pr-test-replace.mp3", b"first-version")
        self._post("pr-test-replace.mp3", b"second")

        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"second")

    def test_failed_write_leaves_the_existing_file_untouched(self):
        from app.controllers.v1 import video as video_controller

        path = self._track("pr-test-keep.mp3")
        self._post("pr-test-keep.mp3", b"original-good-audio")

        with patch.object(
            video_controller.shutil, "copyfileobj", side_effect=OSError("disk full")
        ):
            self._post("pr-test-keep.mp3", b"doomed")

        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"original-good-audio")

    def test_no_temporary_files_are_left_behind(self):
        from app.controllers.v1 import video as video_controller

        self._track("pr-test-tmp.mp3")
        # tracked too: without the fix the patch is a no-op and the upload succeeds
        self._track("pr-test-tmp-failed.mp3")
        self._post("pr-test-tmp.mp3", b"x" * 4096)

        with patch.object(
            video_controller.shutil, "copyfileobj", side_effect=OSError("disk full")
        ):
            self._post("pr-test-tmp-failed.mp3", b"y" * 4096)

        leftovers = [n for n in os.listdir(self.song_dir) if n.startswith(".upload-")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
