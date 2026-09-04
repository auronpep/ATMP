import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils


def _sanitize(name):
    """Mirror of the normalisation applied in webui/Main.py."""
    safe = os.path.basename(str(name or "").replace("\\", "/").rstrip("/")).strip()
    if safe in ("", ".", ".."):
        safe = "material"
    return safe


class TestWebuiUploadFilename(unittest.TestCase):
    """Streamlit stores the client-supplied filename verbatim
    (`UploadedFileRec(name=upload.filename or "")`), so the WebUI must not join
    it into a path unchecked."""

    @classmethod
    def setUpClass(cls):
        cls.local_videos_dir = os.path.realpath(
            utils.storage_dir("local_videos", create=True)
        )

    def _target(self, name, file_id="abc123"):
        return os.path.realpath(
            os.path.join(self.local_videos_dir, f"{file_id}_{_sanitize(name)}")
        )

    def _is_contained(self, name):
        target = self._target(name)
        return (
            os.path.commonpath([self.local_videos_dir, target])
            == self.local_videos_dir
        )

    def test_ordinary_filenames_are_preserved(self):
        self.assertEqual(_sanitize("clip.mp4"), "clip.mp4")
        self.assertTrue(self._is_contained("clip.mp4"))

    def test_posix_traversal_cannot_escape(self):
        self.assertTrue(self._is_contained("../../../evil.mp4"))
        self.assertEqual(_sanitize("../../../evil.mp4"), "evil.mp4")

    def test_windows_traversal_cannot_escape(self):
        self.assertTrue(self._is_contained(r"..\..\..\evil.mp4"))
        self.assertEqual(_sanitize(r"..\..\..\evil.mp4"), "evil.mp4")

    def test_absolute_paths_are_reduced_to_a_basename(self):
        self.assertEqual(_sanitize("/etc/passwd"), "passwd")
        self.assertTrue(self._is_contained("/etc/passwd"))

    def test_dot_segments_and_blanks_get_a_placeholder(self):
        for name in ("", "   ", ".", "..", None):
            with self.subTest(name=name):
                self.assertEqual(_sanitize(name), "material")
                self.assertTrue(self._is_contained(name))

    def test_trailing_slash_yields_the_last_component(self):
        # "dir/" is not a traversal; it just names a directory-like entry.
        self.assertEqual(_sanitize("dir/"), "dir")
        self.assertTrue(self._is_contained("dir/"))

    def test_result_never_contains_a_separator(self):
        for name in ("a/b/c.mp4", r"a\b\c.mp4", "../x.mp4", "/abs/y.mp4"):
            with self.subTest(name=name):
                result = _sanitize(name)
                self.assertNotIn("/", result)
                self.assertNotIn("\\", result)

    def test_every_candidate_stays_inside_the_material_directory(self):
        hostile = [
            "../../../evil.mp4",
            r"..\..\..\evil.mp4",
            "/etc/passwd",
            "....//....//evil.mp4",
            "..",
            ".",
            "",
        ]
        for name in hostile:
            with self.subTest(name=name):
                self.assertTrue(self._is_contained(name), f"{name!r} escaped")


if __name__ == "__main__":
    unittest.main()
