import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import video as vd
from app.utils import utils


class TestResolveBgmFilePath(unittest.TestCase):
    """`bgm_file` comes straight from the API body / WebUI text box and is
    handed to MoviePy. It must stay inside resource/songs."""

    @classmethod
    def setUpClass(cls):
        cls.song_dir = utils.song_dir()
        cls.existing = sorted(
            f for f in os.listdir(cls.song_dir) if f.lower().endswith(".mp3")
        )[0]

    def _resolve(self, value):
        return vd._resolve_bgm_file_path(self.song_dir, value)

    def test_bare_filename_from_the_bgm_list_resolves(self):
        self.assertEqual(
            self._resolve(self.existing), os.path.join(self.song_dir, self.existing)
        )

    def test_project_relative_path_resolves(self):
        # Users copy the layout from the repo tree; both forms are supported.
        for prefix in ("./resource/songs/", "resource/songs/"):
            with self.subTest(prefix=prefix):
                self.assertEqual(
                    self._resolve(prefix + self.existing),
                    os.path.join(self.song_dir, self.existing),
                )

    def test_traversal_is_rejected(self):
        for value in ("../../etc/passwd", "../config.toml", "..\..\config.toml"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self._resolve(value)

    def test_absolute_paths_outside_the_song_directory_are_rejected(self):
        for value in ("/etc/passwd", "C:/Windows/win.ini"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self._resolve(value)

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ValueError):
            self._resolve("definitely-not-here.mp3")


class TestGetBgmFile(unittest.TestCase):
    def test_empty_bgm_type_disables_background_music(self):
        self.assertEqual(vd.get_bgm_file(bgm_type=""), "")

    def test_random_picks_an_existing_song(self):
        chosen = vd.get_bgm_file(bgm_type="random")

        self.assertTrue(os.path.isfile(chosen))
        self.assertTrue(chosen.lower().endswith(".mp3"))

    def test_unsafe_bgm_file_is_refused_rather_than_raising(self):
        # get_bgm_file swallows the ValueError and returns "" so the render
        # continues without music instead of failing the whole task.
        for value in ("/etc/passwd", "../../config.toml"):
            with self.subTest(value=value):
                self.assertEqual(vd.get_bgm_file(bgm_type="custom", bgm_file=value), "")

    def test_non_mp3_inside_the_song_directory_is_refused(self):
        stray = os.path.join(utils.song_dir(), "pr-test-not-audio.txt")
        Path(stray).write_text("not audio", encoding="utf-8")
        self.addCleanup(lambda: os.path.exists(stray) and os.remove(stray))

        self.assertEqual(
            vd.get_bgm_file(bgm_type="custom", bgm_file="pr-test-not-audio.txt"), ""
        )

    def test_valid_song_is_returned(self):
        existing = sorted(
            f for f in os.listdir(utils.song_dir()) if f.lower().endswith(".mp3")
        )[0]

        self.assertEqual(
            vd.get_bgm_file(bgm_type="custom", bgm_file=existing),
            os.path.join(utils.song_dir(), existing),
        )


if __name__ == "__main__":
    unittest.main()
