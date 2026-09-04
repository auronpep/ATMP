import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import voice as vs


class TestIsAzureV2Voice(unittest.TestCase):
    """Selects the Azure V2 synthesis path, which needs a different SDK call
    and different credentials than V1. A wrong answer sends the request down
    the wrong API entirely."""

    def test_v2_voice_returns_the_bare_name(self):
        self.assertEqual(
            vs.is_azure_v2_voice("zh-CN-XiaoxiaoMultilingualNeural-V2-Female"),
            "zh-CN-XiaoxiaoMultilingualNeural",
        )

    def test_gender_suffix_is_stripped_before_the_v2_check(self):
        for name in (
            "zh-CN-XiaoxiaoMultilingualNeural-V2-Female",
            "zh-CN-XiaoxiaoMultilingualNeural-V2-Male",
            "zh-CN-XiaoxiaoMultilingualNeural-V2",
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    vs.is_azure_v2_voice(name), "zh-CN-XiaoxiaoMultilingualNeural"
                )

    def test_non_v2_voice_returns_empty_string(self):
        # The result is used as a truthiness check by tts().
        for name in ("zh-CN-XiaoyiNeural-Female", "en-US-AriaNeural", ""):
            with self.subTest(name=name):
                self.assertEqual(vs.is_azure_v2_voice(name), "")

    def test_v2_must_be_a_suffix_not_a_substring(self):
        # A "-V2-" in the middle is a different voice, not a V2 voice.
        self.assertEqual(vs.is_azure_v2_voice("en-US-V2-SomethingNeural-Female"), "")

    def test_provider_prefixed_voices_are_not_azure_v2(self):
        for name in (
            "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male",
            "gemini:Zephyr-Female",
            "chatterbox:default-Female",
        ):
            with self.subTest(name=name):
                self.assertEqual(vs.is_azure_v2_voice(name), "")


class TestEnsureFilePathExists(unittest.TestCase):
    """edge_tts 7.x opens the output file before making its network call, so a
    missing parent directory surfaces as a local path error that masks the
    actual TTS result."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_creates_a_missing_parent_directory(self):
        target = os.path.join(self._tmp.name, "tasks", "abc", "audio.mp3")

        vs.ensure_file_path_exists(target)

        self.assertTrue(os.path.isdir(os.path.dirname(target)))

    def test_is_idempotent_for_an_existing_directory(self):
        target = os.path.join(self._tmp.name, "audio.mp3")

        vs.ensure_file_path_exists(target)
        vs.ensure_file_path_exists(target)  # must not raise FileExistsError

        self.assertTrue(os.path.isdir(self._tmp.name))

    def test_does_not_create_the_file_itself(self):
        target = os.path.join(self._tmp.name, "nested", "audio.mp3")

        vs.ensure_file_path_exists(target)

        self.assertFalse(os.path.exists(target))

    def test_bare_filename_with_no_directory_is_a_no_op(self):
        # os.path.dirname("audio.mp3") is "", which makedirs would reject.
        vs.ensure_file_path_exists("audio.mp3")

        self.assertFalse(os.path.exists("audio.mp3"))


if __name__ == "__main__":
    unittest.main()
