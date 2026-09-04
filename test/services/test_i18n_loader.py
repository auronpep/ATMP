import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils

I18N_DIR = Path(__file__).parent.parent.parent / "webui" / "i18n"


class TestLoadLocales(unittest.TestCase):
    """Streamlit re-executes the whole script on every interaction, so this is
    cached — the comment says so explicitly. A cache that silently misses turns
    every click into a full re-read and re-parse of nine JSON files."""

    def setUp(self):
        utils.load_locales.cache_clear()
        self.addCleanup(utils.load_locales.cache_clear)

    def test_loads_every_shipped_locale(self):
        locales = utils.load_locales(str(I18N_DIR))

        on_disk = {p.stem for p in I18N_DIR.glob("*.json")}
        self.assertEqual(set(locales), on_disk)

    def test_each_locale_exposes_a_display_name_and_translations(self):
        locales = utils.load_locales(str(I18N_DIR))

        for code, data in locales.items():
            with self.subTest(code=code):
                self.assertTrue(data.get("Language"), f"{code} has no display name")
                self.assertTrue(data.get("Translation"), f"{code} has no translations")

    def test_repeated_calls_are_served_from_the_cache(self):
        utils.load_locales(str(I18N_DIR))
        first = utils.load_locales.cache_info()
        utils.load_locales(str(I18N_DIR))
        second = utils.load_locales.cache_info()

        self.assertEqual(first.misses, second.misses)
        self.assertEqual(second.hits, first.hits + 1)

    def test_non_json_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, "en.json").write_text(
                json.dumps({"Language": "English", "Translation": {"a": "A"}}),
                encoding="utf-8",
            )
            Path(tmp_dir, "README.md").write_text("not a locale", encoding="utf-8")
            Path(tmp_dir, "notes.txt").write_text("also not", encoding="utf-8")

            locales = utils.load_locales(tmp_dir)

        self.assertEqual(set(locales), {"en"})

    def test_locale_key_is_the_filename_stem(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, "zh.json").write_text(
                json.dumps({"Language": "中文", "Translation": {"a": "甲"}}),
                encoding="utf-8",
            )

            locales = utils.load_locales(tmp_dir)

        self.assertIn("zh", locales)
        self.assertEqual(locales["zh"]["Language"], "中文")

    def test_non_ascii_translations_survive_the_round_trip(self):
        locales = utils.load_locales(str(I18N_DIR))

        self.assertTrue(
            any(ord(ch) > 127 for ch in json.dumps(locales["zh"], ensure_ascii=False))
        )

    def test_empty_directory_yields_no_locales(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertEqual(utils.load_locales(tmp_dir), {})


class TestTranslationLookup(unittest.TestCase):
    """Mirror of webui.Main.tr(): a missing key must degrade to the key itself
    rather than raise, since keys are English phrases."""

    @classmethod
    def setUpClass(cls):
        utils.load_locales.cache_clear()
        cls.locales = utils.load_locales(str(I18N_DIR))

    @classmethod
    def tearDownClass(cls):
        utils.load_locales.cache_clear()

    def _tr(self, code, key):
        return self.locales.get(code, {}).get("Translation", {}).get(key, key)

    def test_known_key_is_translated(self):
        self.assertNotEqual(self._tr("zh", "Video Ratio"), "Video Ratio")

    def test_unknown_key_falls_back_to_itself(self):
        self.assertEqual(self._tr("en", "No Such Key At All"), "No Such Key At All")

    def test_unknown_locale_falls_back_to_the_key(self):
        self.assertEqual(self._tr("xx", "Video Ratio"), "Video Ratio")

    def test_every_locale_can_be_looked_up_without_raising(self):
        for code in self.locales:
            with self.subTest(code=code):
                self.assertIsInstance(self._tr(code, "Video Ratio"), str)


if __name__ == "__main__":
    unittest.main()
