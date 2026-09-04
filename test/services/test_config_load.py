import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config


class TestLoadConfigRecovery(unittest.TestCase):
    """`load_config()` runs at import, before anything else.

    It has two recovery paths that only trigger on a broken machine, which is
    exactly why they are worth pinning: if either regresses, the app fails to
    start and the traceback points at TOML parsing rather than the cause.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_path = os.path.join(self._tmp.name, "config.toml")

    def _load(self):
        with patch.object(config, "config_file", self.config_path):
            return config.load_config()

    def test_missing_config_is_seeded_from_the_example(self):
        loaded = self._load()

        self.assertTrue(os.path.isfile(self.config_path))
        self.assertIn("app", loaded)

    def test_a_directory_named_config_toml_is_replaced(self):
        # Docker bind-mounts create a *directory* when the host path is absent:
        # "IsADirectoryError: [Errno 21] Is a directory: '/MoneyPrinterTurbo/config.toml'"
        os.makedirs(os.path.join(self.config_path, "nested"))
        self.assertTrue(os.path.isdir(self.config_path))

        loaded = self._load()

        self.assertTrue(os.path.isfile(self.config_path))
        self.assertIn("app", loaded)

    def test_an_existing_config_is_not_overwritten(self):
        Path(self.config_path).write_text(
            '[app]\nopenai_api_key = "sk-mine"\n', encoding="utf-8"
        )

        loaded = self._load()

        self.assertEqual(loaded["app"]["openai_api_key"], "sk-mine")

    def test_a_utf8_bom_file_still_loads(self):
        # Windows editors (Notepad, some PowerShell redirects) write a BOM,
        # which the plain TOML loader rejects.
        Path(self.config_path).write_text(
            '[app]\nopenai_api_key = "sk-bom"\n', encoding="utf-8-sig"
        )

        loaded = self._load()

        self.assertEqual(loaded["app"]["openai_api_key"], "sk-bom")

    def test_non_ascii_values_survive(self):
        Path(self.config_path).write_text(
            '[app]\nvideo_subject = "金钱的作用"\n', encoding="utf-8"
        )

        loaded = self._load()

        self.assertEqual(loaded["app"]["video_subject"], "金钱的作用")

    def test_seeded_config_matches_the_example_file(self):
        loaded = self._load()

        import tomllib

        example = tomllib.load(
            open(Path(__file__).parent.parent.parent / "config.example.toml", "rb")
        )
        self.assertEqual(set(loaded["app"]), set(example["app"]))

    def test_a_genuinely_malformed_config_still_raises(self):
        # The utf-8-sig retry must not swallow real syntax errors into a silent
        # empty config - that would start the app with every setting missing.
        Path(self.config_path).write_text("this is not = valid = toml", encoding="utf-8")

        with self.assertRaises(Exception):
            self._load()


if __name__ == "__main__":
    unittest.main()
