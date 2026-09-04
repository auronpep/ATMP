import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.task import resolve_custom_audio_file
from app.utils import utils


class TestResolveCustomAudioFile(unittest.TestCase):
    """`custom_audio_file` arrives on POST /api/v1/videos as a free-form string.

    It decides which file becomes the soundtrack of the generated video, so its
    accept/reject rules are a security boundary as much as a convenience.
    """

    def setUp(self):
        self.task_id = "test-custom-audio"
        self.task_dir = utils.task_dir(self.task_id)
        self.addCleanup(shutil.rmtree, self.task_dir, True)

        self.task_local = os.path.join(self.task_dir, "custom-audio.mp3")
        Path(self.task_local).write_bytes(b"")

        self.project_file = os.path.join(utils.root_dir(), "pr-test-side-audio.mp3")
        Path(self.project_file).write_bytes(b"")
        self.addCleanup(
            lambda: os.path.exists(self.project_file) and os.remove(self.project_file)
        )

        self._outside_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._outside_dir, True)
        self.outside_file = os.path.join(self._outside_dir, "outside.mp3")
        Path(self.outside_file).write_bytes(b"")

    def _resolve(self, value):
        return resolve_custom_audio_file(self.task_id, value)

    # --- accepted -------------------------------------------------------

    def test_blank_input_means_no_custom_audio(self):
        for value in ("", "   ", None):
            with self.subTest(value=value):
                self.assertEqual(self._resolve(value), "")

    def test_task_local_filename_resolves_into_the_task_directory(self):
        self.assertEqual(self._resolve("custom-audio.mp3"), self.task_local)

    def test_task_local_absolute_path_is_accepted(self):
        self.assertEqual(self._resolve(self.task_local), self.task_local)

    def test_relative_path_inside_the_project_root_is_accepted(self):
        resolved = self._resolve("pr-test-side-audio.mp3")

        self.assertEqual(os.path.realpath(resolved), os.path.realpath(self.project_file))

    # --- rejected -------------------------------------------------------

    def test_relative_traversal_out_of_the_project_is_rejected(self):
        for value in ("../../../etc/passwd", "../outside.mp3"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as ctx:
                    self._resolve(value)
                self.assertIn("task-local or an existing server-side file", str(ctx.exception))

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self._resolve("does-not-exist.mp3")

        self.assertIn("does not exist", str(ctx.exception))

    def test_a_directory_is_not_accepted_as_audio(self):
        with self.assertRaises(ValueError):
            self._resolve(self.task_dir)

    # --- documented behaviour worth a second look -----------------------

    def test_absolute_path_outside_the_project_is_currently_accepted(self):
        """Pins current, deliberate behaviour.

        The error text ("task-local or an existing server-side file") shows the
        server-side escape hatch is intended. Note the combination though: the
        v1 router's auth dependency is commented out by default, so an
        unauthenticated caller can name any readable absolute path with an
        audio extension. Restricting this to a configured directory would be a
        product decision, so this test records the behaviour rather than
        changing it.
        """
        self.assertEqual(
            os.path.realpath(self._resolve(self.outside_file)),
            os.path.realpath(self.outside_file),
        )


if __name__ == "__main__":
    unittest.main()
