import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils


def _import_main():
    """webui/Main.py runs Streamlit code at import; import it once, lazily."""
    import webui.Main as webui_main

    return webui_main


class TestAssetListingIsCaseInsensitive(unittest.TestCase):
    """Fonts and BGM are discovered by walking resource/. Users drop files in
    by hand, so `Impact.TTF` and `Track.MP3` must be found — a case-sensitive
    suffix check makes them vanish from the dropdown with no error."""

    @classmethod
    def setUpClass(cls):
        cls.main = _import_main()

    def _make(self, directory, names):
        created = []
        for name in names:
            path = os.path.join(directory, name)
            Path(path).write_bytes(b"\x00")
            created.append(path)
            self.addCleanup(lambda p=path: os.path.exists(p) and os.remove(p))
        return created

    def test_fonts_are_listed_regardless_of_suffix_case(self):
        font_dir = utils.font_dir()
        names = ["PrTest-Lower.ttf", "PrTest-Upper.TTF", "PrTest-Collection.TTC"]
        self._make(font_dir, names)

        listed = self.main.get_all_fonts()

        for name in names:
            with self.subTest(name=name):
                self.assertIn(name, listed)

    def test_non_font_files_are_not_listed(self):
        font_dir = utils.font_dir()
        self._make(font_dir, ["PrTest-Readme.txt", "PrTest-NoExtTtf"])

        listed = self.main.get_all_fonts()

        self.assertNotIn("PrTest-Readme.txt", listed)
        self.assertNotIn("PrTest-NoExtTtf", listed)

    def test_songs_are_listed_regardless_of_suffix_case(self):
        song_dir = utils.song_dir()
        names = ["pr-test-lower.mp3", "PR-TEST-UPPER.MP3"]
        self._make(song_dir, names)

        listed = self.main.get_all_songs()

        for name in names:
            with self.subTest(name=name):
                self.assertIn(name, listed)

    def test_non_song_files_are_not_listed(self):
        song_dir = utils.song_dir()
        self._make(song_dir, ["pr-test-notes.txt", "pr-test-nodotmp3"])

        listed = self.main.get_all_songs()

        self.assertNotIn("pr-test-notes.txt", listed)
        self.assertNotIn("pr-test-nodotmp3", listed)

    def test_fonts_remain_sorted(self):
        listed = self.main.get_all_fonts()

        self.assertEqual(listed, sorted(listed))


if __name__ == "__main__":
    unittest.main()
