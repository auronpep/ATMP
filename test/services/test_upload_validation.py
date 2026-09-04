import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils


class _UploadEndpointTestCase(unittest.TestCase):
    """Uploads must only be accepted when the listing endpoint can find them.

    Both upload routes validated with `endswith(...)`, which has no dot, so a
    file called `mp3` or `clip.badmov` was written to disk and then never
    appeared in the corresponding `GET`, because those glob for `*.<suffix>`.
    """

    upload_url = ""
    list_url = ""
    target_dir = ""

    @classmethod
    def setUpClass(cls):
        if cls is _UploadEndpointTestCase:
            raise unittest.SkipTest("base class")
        from starlette.testclient import TestClient

        from app.asgi import app

        cls.client = TestClient(app, raise_server_exceptions=False)

    def setUp(self):
        self._created = []

    def tearDown(self):
        for path in self._created:
            try:
                os.remove(path)
            except OSError:
                pass

    def _upload(self, filename):
        path = os.path.join(self.target_dir, filename)
        self._created.append(path)
        return self.client.post(
            self.upload_url,
            files={"file": (filename, io.BytesIO(b"\x00" * 16), "application/octet-stream")},
        )

    def _listed_names(self):
        payload = self.client.get(self.list_url).json()
        return {entry["name"] for entry in payload.get("data", {}).get("files", [])}

    def assert_rejected(self, filename):
        response = self._upload(filename)
        self.assertEqual(response.status_code, 400, f"{filename} was accepted")
        self.assertFalse(
            os.path.exists(os.path.join(self.target_dir, filename)),
            f"{filename} was written to disk",
        )

    def assert_accepted_and_listed(self, filename):
        response = self._upload(filename)
        self.assertEqual(response.status_code, 200, f"{filename} was rejected")
        self.assertIn(filename, self._listed_names())


class TestBgmUploadValidation(_UploadEndpointTestCase):
    upload_url = "/api/v1/musics"
    list_url = "/api/v1/musics"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_dir = utils.song_dir()

    def test_real_mp3_extension_is_accepted_and_listed(self):
        self.assert_accepted_and_listed("pr-test-track.mp3")

    def test_uppercase_extension_is_accepted(self):
        self.assert_accepted_and_listed("PR-TEST-TRACK.MP3")

    def test_names_merely_ending_in_mp3_are_rejected(self):
        for filename in ("mp3", "pr-test-song.wavmp3", "pr-testmp3"):
            with self.subTest(filename=filename):
                self.assert_rejected(filename)

    def test_unrelated_extension_is_rejected(self):
        self.assert_rejected("pr-test.txt")


class TestVideoMaterialUploadValidation(_UploadEndpointTestCase):
    upload_url = "/api/v1/video_materials"
    list_url = "/api/v1/video_materials"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_dir = utils.storage_dir("local_videos", create=True)

    def test_real_extensions_are_accepted_and_listed(self):
        for filename in ("pr-test-clip.mp4", "pr-test-still.png", "pr-test-clip.MOV"):
            with self.subTest(filename=filename):
                self.assert_accepted_and_listed(filename)

    def test_names_merely_ending_in_an_allowed_suffix_are_rejected(self):
        for filename in ("mp4", "pr-test-clip.badmov", "pr-test-shotpng"):
            with self.subTest(filename=filename):
                self.assert_rejected(filename)

    def test_unrelated_extension_is_rejected(self):
        self.assert_rejected("pr-test.exe")


if __name__ == "__main__":
    unittest.main()
