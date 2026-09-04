import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import toml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config


class TestSaveConfigIsAtomic(unittest.TestCase):
    """`config.toml` holds every API key and is rewritten on every WebUI rerun.

    A truncate-then-write must never be able to leave it empty or partial.
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.config_path = os.path.join(self.tmp_dir.name, "config.toml")
        self.original = "[app]\nopenai_api_key = \"sk-keep-me\"\n"
        Path(self.config_path).write_text(self.original, encoding="utf-8")

        self.original_app = dict(config.app)
        self.addCleanup(self._restore_app)

    def _restore_app(self):
        config.app.clear()
        config.app.update(self.original_app)

    def _leftovers(self):
        return [n for n in os.listdir(self.tmp_dir.name) if n != "config.toml"]

    def test_config_is_written_and_reloadable(self):
        config.app["openai_api_key"] = "sk-new"

        with patch.object(config, "config_file", self.config_path):
            config.save_config()

        saved = toml.loads(Path(self.config_path).read_text(encoding="utf-8"))
        self.assertEqual(saved["app"]["openai_api_key"], "sk-new")
        self.assertEqual(self._leftovers(), [])

    def test_original_config_survives_a_serialization_failure(self):
        with patch.object(config, "config_file", self.config_path), patch.object(
            config.toml, "dumps", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                config.save_config()

        self.assertEqual(
            Path(self.config_path).read_text(encoding="utf-8"), self.original
        )

    def test_original_config_survives_a_write_failure(self):
        real_fdopen = os.fdopen

        def exploding_fdopen(fd, *args, **kwargs):
            handle = real_fdopen(fd, *args, **kwargs)
            handle.close()
            raise OSError("disk full")

        with patch.object(config, "config_file", self.config_path), patch.object(
            config.os, "fdopen", exploding_fdopen
        ):
            with self.assertRaises(OSError):
                config.save_config()

        self.assertEqual(
            Path(self.config_path).read_text(encoding="utf-8"), self.original
        )
        self.assertEqual(self._leftovers(), [])


if __name__ == "__main__":
    unittest.main()
