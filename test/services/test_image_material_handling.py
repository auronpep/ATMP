import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import video as vd

RESOURCES = Path(__file__).parent.parent / "resources"
SAMPLE_IMAGE = RESOURCES / "1.png"


class TestOpenImageClipWithFallback(unittest.TestCase):
    """Local image materials are user-supplied. Some open in Pillow but crash
    ImageClip on damaged EXIF, so this falls back to a metadata-stripped copy
    rather than dropping the material."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.image = os.path.join(self._tmp.name, "sample.png")
        shutil.copy(SAMPLE_IMAGE, self.image)

    def test_healthy_image_opens_directly_without_a_copy(self):
        clip, path = vd._open_image_clip_with_fallback(self.image)
        self.addCleanup(vd.close_clip, clip)

        self.assertEqual(path, self.image)
        self.assertEqual(clip.size, (580, 751))
        self.assertFalse(
            os.path.exists(os.path.join(self._tmp.name, "sample.sanitized.png")),
            "no sanitized copy should be produced for a healthy image",
        )

    def test_unreadable_image_falls_back_to_a_sanitized_copy(self):
        real_image_clip = vd.ImageClip
        calls = {"n": 0}

        def flaky_image_clip(path, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("broken EXIF")
            return real_image_clip(path, *args, **kwargs)

        with patch.object(vd, "ImageClip", flaky_image_clip):
            clip, path = vd._open_image_clip_with_fallback(self.image)
        self.addCleanup(vd.close_clip, clip)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

        self.assertNotEqual(path, self.image)
        self.assertTrue(path.endswith(".sanitized.png"))
        self.assertTrue(os.path.isfile(path))

    def test_fallback_preserves_the_image_dimensions(self):
        sanitized = vd._sanitize_image_file(self.image)
        self.addCleanup(lambda: os.path.exists(sanitized) and os.remove(sanitized))

        clip = vd.ImageClip(sanitized)
        self.addCleanup(vd.close_clip, clip)

        self.assertEqual(clip.size, (580, 751))

    def test_sanitized_copy_sits_beside_the_original(self):
        sanitized = vd._sanitize_image_file(self.image)
        self.addCleanup(lambda: os.path.exists(sanitized) and os.remove(sanitized))

        self.assertEqual(os.path.dirname(sanitized), os.path.dirname(self.image))
        self.assertTrue(os.path.isfile(sanitized))

    def test_sanitized_copy_is_a_png_regardless_of_input_extension(self):
        jpg_path = os.path.join(self._tmp.name, "sample.jpg")
        clip = vd.ImageClip(self.image)
        try:
            from PIL import Image

            Image.open(self.image).convert("RGB").save(jpg_path)
        finally:
            vd.close_clip(clip)

        sanitized = vd._sanitize_image_file(jpg_path)
        self.addCleanup(lambda: os.path.exists(sanitized) and os.remove(sanitized))

        self.assertTrue(sanitized.endswith(".sanitized.png"))

    def test_a_non_image_file_still_raises(self):
        junk = os.path.join(self._tmp.name, "not-an-image.png")
        Path(junk).write_bytes(b"definitely not a png")

        with self.assertRaises(Exception):
            vd._open_image_clip_with_fallback(junk)


class TestTempAudioDir(unittest.TestCase):
    """MoviePy's temp audio file must not live in the task output directory on
    Windows: Defender locks it mid-scan and the render dies with WinError 32,
    leaving a 0-byte MP4."""

    def test_windows_uses_the_system_temp_directory(self):
        with patch.object(vd.sys, "platform", "win32"):
            self.assertEqual(vd._get_temp_audio_dir("/task/out"), tempfile.gettempdir())

    def test_other_platforms_keep_the_output_directory(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform):
                with patch.object(vd.sys, "platform", platform):
                    self.assertEqual(vd._get_temp_audio_dir("/task/out"), "/task/out")

    def test_the_returned_directory_exists(self):
        self.assertTrue(os.path.isdir(vd._get_temp_audio_dir(tempfile.gettempdir())))


if __name__ == "__main__":
    unittest.main()
