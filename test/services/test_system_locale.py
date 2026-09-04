import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils

I18N_DIR = Path(__file__).parent.parent.parent / "webui" / "i18n"


def _available_locales():
    return {p.stem for p in I18N_DIR.glob("*.json")}


class TestGetSystemLocale(unittest.TestCase):
    """Picks the WebUI's default language.

    `webui/Main.py` does `locales.get(st.session_state["ui_language"], {})`, and
    `tr()` falls back to the raw key. So a value that is not an i18n filename
    does not raise — it silently renders the entire UI in untranslated keys.
    """

    def test_returns_a_short_language_code(self):
        for full, expected in (
            ("en_US", "en"),
            ("zh_CN", "zh"),
            ("zh_TW", "zh"),
            ("de_DE", "de"),
            ("pt_BR", "pt"),
        ):
            with self.subTest(full=full):
                with patch.object(
                    utils.locale, "getdefaultlocale", return_value=(full, "UTF-8")
                ):
                    self.assertEqual(utils.get_system_locale(), expected)

    def test_falls_back_to_english_when_the_locale_is_unset(self):
        for value in ((None, None), None):
            with self.subTest(value=value):
                with patch.object(
                    utils.locale, "getdefaultlocale", return_value=value
                ):
                    self.assertEqual(utils.get_system_locale(), "en")

    def test_falls_back_to_english_when_lookup_raises(self):
        with patch.object(
            utils.locale, "getdefaultlocale", side_effect=OSError("no locale")
        ):
            self.assertEqual(utils.get_system_locale(), "en")

    def test_real_result_is_short_and_lowercase(self):
        result = utils.get_system_locale()

        self.assertTrue(result.islower(), f"{result!r} is not a lowercase code")
        self.assertLessEqual(len(result), 3, f"{result!r} is not a language code")

    def test_result_is_usable_as_an_i18n_filename_or_degrades_to_english(self):
        # The value is looked up directly against webui/i18n/<code>.json.
        result = utils.get_system_locale()

        self.assertIn(
            result,
            _available_locales() | {"en"},
            f"{result!r} matches no i18n file and is not the 'en' fallback",
        )


class TestLocaleApiSwapIsNotSafe(unittest.TestCase):
    """Guards against the tempting `getdefaultlocale` -> `getlocale` swap.

    `locale.getdefaultlocale()` is deprecated and slated for removal, so the
    obvious fix is `locale.getlocale()`. They are NOT interchangeable here.
    On Windows:

        getdefaultlocale() -> ('en_US', 'cp1252')            -> "en"
        getlocale()        -> ('English_United States', ...) -> "English"

    "English" is not an i18n filename, so that swap silently renders the whole
    WebUI in untranslated keys. Any replacement has to normalise the verbose
    Windows form back to a short code.
    """

    def test_windows_style_locale_name_would_not_produce_a_language_code(self):
        with patch.object(
            utils.locale,
            "getdefaultlocale",
            return_value=("English_United States", "1252"),
        ):
            result = utils.get_system_locale()

        self.assertNotIn(
            result,
            _available_locales(),
            "verbose locale names must not be treated as i18n codes",
        )

    def test_the_english_i18n_file_exists_under_the_short_code(self):
        # i.e. the code must yield "en", not "English".
        self.assertTrue((I18N_DIR / "en.json").is_file())
        self.assertFalse((I18N_DIR / "English.json").exists())

    def test_all_i18n_files_use_short_codes(self):
        for name in _available_locales():
            with self.subTest(name=name):
                self.assertLessEqual(len(name), 3)
                self.assertTrue(name.islower())

    def test_every_i18n_file_is_valid_json_with_a_translation_block(self):
        for path in I18N_DIR.glob("*.json"):
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn("Translation", data)


if __name__ == "__main__":
    unittest.main()
