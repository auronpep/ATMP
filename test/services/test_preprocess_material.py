import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PIL import Image

from app.models.schema import MaterialInfo
from app.services import video as vd
from app.utils import utils

RESOURCES = Path(__file__).parent.parent / "resources"
SAMPLE_IMAGE = RESOURCES / "1.png"


class TestPreprocessMaterialGates(unittest.TestCase):
    """`preprocess_video` is the gate between user-supplied local materials and
    the render pipeline. Everything it rejects is rejected **silently** — a
    warning is logged and the material is dropped — so a regression here either
    lets bad material into the video or quietly discards good material."""

    def setUp(self):
        self.local_dir = utils.storage_dir("local_videos", create=True)
        self._created = []

    def tearDown(self):
        for path in self._created:
            if os.path.exists(path):
                os.remove(path)

    def _place(self, name, size=None):
        path = os.path.join(self.local_dir, name)
        self._created.append(path)
        if size is None:
            shutil.copy(SAMPLE_IMAGE, path)
        else:
            Image.new("RGB", size, (10, 20, 30)).save(path)
        return path

    def _material(self, url):
        material = MaterialInfo()
        material.provider = "local"
        material.url = url
        return material

    def test_empty_material_list_returns_empty(self):
        self.assertEqual(vd.preprocess_video([]), [])
        self.assertEqual(vd.preprocess_video(None), [])

    def test_material_without_a_url_is_skipped(self):
        self.assertEqual(vd.preprocess_video([self._material("")]), [])

    def test_low_resolution_material_is_rejected(self):
        # Below 480x480 the clip would be upscaled into a blurry mess.
        self._place("pr-test-small.png", size=(320, 240))

        self.assertEqual(
            vd.preprocess_video([self._material("pr-test-small.png")]), []
        )

    def test_paths_outside_the_material_directory_are_rejected(self):
        # `video_source: local` materials come from API input.
        for url in ("../../etc/passwd", "/etc/passwd", "../config.toml"):
            with self.subTest(url=url):
                self.assertEqual(vd.preprocess_video([self._material(url)]), [])

    def test_a_missing_file_is_skipped_not_fatal(self):
        self.assertEqual(
            vd.preprocess_video([self._material("pr-test-absent.png")]), []
        )

    def test_an_unreadable_file_is_skipped_not_fatal(self):
        path = os.path.join(self.local_dir, "pr-test-junk.png")
        self._created.append(path)
        Path(path).write_bytes(b"not really a png")

        self.assertEqual(vd.preprocess_video([self._material("pr-test-junk.png")]), [])

    def test_one_bad_material_does_not_discard_the_good_ones(self):
        self._place("pr-test-good.png", size=(480, 480))
        self._place("pr-test-tiny.png", size=(100, 100))

        result = vd.preprocess_video(
            [
                self._material("pr-test-tiny.png"),
                self._material("pr-test-good.png"),
            ],
            clip_duration=1,
        )
        self._created.append(os.path.join(self.local_dir, "pr-test-good.png.mp4"))

        self.assertEqual(len(result), 1)

    def test_accepted_image_material_is_converted_to_a_video(self):
        self._place("pr-test-conv.png", size=(480, 480))

        result = vd.preprocess_video([self._material("pr-test-conv.png")], clip_duration=1)
        self._created.append(os.path.join(self.local_dir, "pr-test-conv.png.mp4"))

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].url.endswith(".mp4"))
        self.assertTrue(os.path.isfile(result[0].url))


if __name__ == "__main__":
    unittest.main()
