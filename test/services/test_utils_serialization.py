import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils


class TestToJson(unittest.TestCase):
    """Used to log task params and to write storage/tasks/<id>/script.json.

    Two properties matter: it must never raise (it is called from logging and
    error paths), and it must not dump raw binary into a log line.
    """

    def test_plain_values_round_trip(self):
        payload = {"subject": "coffee", "count": 3, "ok": True, "none": None}

        self.assertEqual(json.loads(utils.to_json(payload)), payload)

    def test_non_ascii_is_preserved_not_escaped(self):
        # ensure_ascii=False, so Chinese subjects stay readable in script.json.
        result = utils.to_json({"subject": "中文标题"})

        self.assertIn("中文标题", result)
        self.assertEqual(json.loads(result)["subject"], "中文标题")

    def test_binary_is_redacted_rather_than_serialized(self):
        result = utils.to_json({"audio": b"\x00\x01\x02binary"})

        self.assertEqual(json.loads(result)["audio"], "*** binary data ***")

    def test_tuples_become_arrays(self):
        self.assertEqual(json.loads(utils.to_json({"size": (1920, 1080)}))["size"], [1920, 1080])

    def test_nested_objects_are_serialized_via_their_dict(self):
        class Params:
            def __init__(self):
                self.subject = "coffee"
                self.count = 2

        result = json.loads(utils.to_json({"params": Params()}))

        self.assertEqual(result["params"], {"subject": "coffee", "count": 2})

    def test_unsupported_types_become_null_instead_of_raising(self):
        self.assertEqual(json.loads(utils.to_json({"s": {1, 2}}))["s"], None)

    def test_returns_none_when_serialization_fails(self):
        class Exploding:
            @property
            def __dict__(self):
                raise RuntimeError("boom")

        self.assertIsNone(utils.to_json(Exploding()))

    def test_output_is_indented_for_readability(self):
        self.assertIn("\n    ", utils.to_json({"a": 1}))


class TestGetFfmpegBinary(unittest.TestCase):
    """Resolution order is documented in the function: explicit env var, then
    PATH, then the bundled imageio binary, then the bare name."""

    def setUp(self):
        self.original = os.environ.get("IMAGEIO_FFMPEG_EXE")
        os.environ.pop("IMAGEIO_FFMPEG_EXE", None)

    def tearDown(self):
        os.environ.pop("IMAGEIO_FFMPEG_EXE", None)
        if self.original is not None:
            os.environ["IMAGEIO_FFMPEG_EXE"] = self.original

    def test_explicit_env_var_wins(self):
        os.environ["IMAGEIO_FFMPEG_EXE"] = "/custom/ffmpeg"

        with patch.object(utils.shutil, "which", return_value="/usr/bin/ffmpeg"):
            self.assertEqual(utils.get_ffmpeg_binary(), "/custom/ffmpeg")

    def test_path_lookup_is_used_when_no_env_var(self):
        with patch.object(utils.shutil, "which", return_value="/usr/bin/ffmpeg"):
            self.assertEqual(utils.get_ffmpeg_binary(), "/usr/bin/ffmpeg")

    def test_falls_back_to_the_bare_name_when_nothing_resolves(self):
        with patch.object(utils.shutil, "which", return_value=None), patch.dict(
            sys.modules, {"imageio_ffmpeg": None}
        ):
            self.assertEqual(utils.get_ffmpeg_binary(), "ffmpeg")

    def test_always_returns_a_non_empty_string(self):
        self.assertTrue(utils.get_ffmpeg_binary())


if __name__ == "__main__":
    unittest.main()
