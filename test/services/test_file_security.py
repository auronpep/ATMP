import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils.file_security import resolve_path_within_directory


class TestResolvePathWithinDirectory(unittest.TestCase):
    """Guards the single containment check used by every user-supplied path.

    Call sites: BGM upload/selection, local material uploads, task output
    download/stream endpoints and the custom audio file, i.e. everything an
    anonymous API caller can influence.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base_dir = os.path.realpath(self._tmp.name)

        self.inside = os.path.join(self.base_dir, "inside.mp3")
        Path(self.inside).write_bytes(b"x")

        self.nested_dir = os.path.join(self.base_dir, "nested")
        os.makedirs(self.nested_dir)
        self.nested = os.path.join(self.nested_dir, "deep.mp3")
        Path(self.nested).write_bytes(b"x")

        # A sibling whose name shares the base directory's prefix. A naive
        # startswith() check would treat this as "inside".
        self.sibling_dir = self.base_dir + "_evil"
        os.makedirs(self.sibling_dir, exist_ok=True)
        self.addCleanup(self._cleanup_sibling)
        self.outside = os.path.join(self.sibling_dir, "outside.mp3")
        Path(self.outside).write_bytes(b"x")

    def _cleanup_sibling(self):
        for name in os.listdir(self.sibling_dir):
            os.remove(os.path.join(self.sibling_dir, name))
        os.rmdir(self.sibling_dir)

    # --- accepted -------------------------------------------------------

    def test_plain_filename_resolves_inside_the_base_directory(self):
        self.assertEqual(
            resolve_path_within_directory(self.base_dir, "inside.mp3"), self.inside
        )

    def test_nested_relative_path_is_allowed(self):
        self.assertEqual(
            resolve_path_within_directory(self.base_dir, "nested/deep.mp3"),
            self.nested,
        )

    def test_absolute_path_inside_the_base_directory_is_allowed(self):
        self.assertEqual(
            resolve_path_within_directory(self.base_dir, self.inside), self.inside
        )

    def test_redundant_separators_and_dot_segments_are_normalised(self):
        self.assertEqual(
            resolve_path_within_directory(self.base_dir, "./nested//./deep.mp3"),
            self.nested,
        )

    def test_traversal_that_returns_inside_is_allowed(self):
        # "nested/../inside.mp3" never leaves the base directory.
        self.assertEqual(
            resolve_path_within_directory(self.base_dir, "nested/../inside.mp3"),
            self.inside,
        )

    def test_directory_is_allowed_when_require_file_is_false(self):
        self.assertEqual(
            resolve_path_within_directory(
                self.base_dir, "nested", require_file=False
            ),
            self.nested_dir,
        )

    def test_missing_path_is_allowed_when_require_file_is_false(self):
        self.assertEqual(
            resolve_path_within_directory(
                self.base_dir, "not-created-yet.mp3", require_file=False
            ),
            os.path.join(self.base_dir, "not-created-yet.mp3"),
        )

    # --- rejected -------------------------------------------------------

    def test_empty_path_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_path_within_directory(self.base_dir, "")
        self.assertIn("empty path", str(ctx.exception))

    def test_relative_traversal_escaping_the_base_is_rejected(self):
        for candidate in ("../outside.mp3", "nested/../../outside.mp3"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    resolve_path_within_directory(self.base_dir, candidate)

    def test_absolute_path_outside_the_base_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_path_within_directory(self.base_dir, self.outside)
        self.assertIn("outside the allowed directory", str(ctx.exception))

    def test_sibling_directory_sharing_the_base_prefix_is_rejected(self):
        # base="/tmp/x", candidate="/tmp/x_evil/outside.mp3"
        self.assertTrue(self.outside.startswith(self.base_dir))
        with self.assertRaises(ValueError):
            resolve_path_within_directory(self.base_dir, self.outside)

    def test_directory_is_rejected_when_a_file_is_required(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_path_within_directory(self.base_dir, "nested")
        self.assertIn("file does not exist", str(ctx.exception))

    def test_missing_file_is_rejected_when_a_file_is_required(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_path_within_directory(self.base_dir, "nope.mp3")
        self.assertIn("file does not exist", str(ctx.exception))

    @unittest.skipUnless(sys.platform == "win32", "windows-only path semantics")
    def test_path_on_another_drive_is_rejected(self):
        # commonpath() raises ValueError across drives; it must surface as a
        # containment failure rather than escaping the caller.
        other_drive = "Z:\\somewhere\\outside.mp3"
        with self.assertRaises(ValueError) as ctx:
            resolve_path_within_directory(self.base_dir, other_drive)
        self.assertIn("outside the allowed directory", str(ctx.exception))

    @unittest.skipUnless(sys.platform == "win32", "windows-only path semantics")
    def test_windows_path_matching_is_case_insensitive(self):
        self.assertEqual(
            resolve_path_within_directory(self.base_dir, "INSIDE.MP3"), self.inside
        )

    def test_symlink_pointing_outside_the_base_is_rejected(self):
        link = os.path.join(self.base_dir, "escape.mp3")
        try:
            os.symlink(self.outside, link)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        # realpath() resolves the link, so containment is judged on the target.
        with self.assertRaises(ValueError):
            resolve_path_within_directory(self.base_dir, "escape.mp3")


if __name__ == "__main__":
    unittest.main()
