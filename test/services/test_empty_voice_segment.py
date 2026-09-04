import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import voice as vs

OUT = "/tmp/empty-voice-segment.mp3"
PROVIDERS = (
    ("gemini:", "gemini_tts"),
    ("mimo:", "mimo_tts"),
    ("elevenlabs:", "elevenlabs_tts"),
)


class TestEmptyVoiceSegmentIsRejected(unittest.TestCase):
    """A prefix with no voice after it must fail locally, not at the provider."""

    def _tts(self, voice_name, target):
        with patch.object(vs, target, return_value="CALLED") as backend, patch.object(
            vs, "azure_tts_v1"
        ) as fallback:
            result = vs.tts(
                text="hello", voice_name=voice_name, voice_rate=1.0, voice_file=OUT
            )
        return result, backend, fallback

    def test_empty_voice_segment_does_not_reach_the_provider(self):
        for voice_name, target in PROVIDERS:
            with self.subTest(voice_name=voice_name):
                result, backend, fallback = self._tts(voice_name, target)

                self.assertIsNone(result)
                backend.assert_not_called()
                # must not silently fall through to the default provider either
                fallback.assert_not_called()

    def test_whitespace_only_voice_segment_is_rejected(self):
        for voice_name, target in PROVIDERS:
            with self.subTest(voice_name=voice_name):
                result, backend, _ = self._tts(voice_name + "   ", target)

                self.assertIsNone(result)
                backend.assert_not_called()

    def test_valid_voice_names_are_unaffected(self):
        cases = (
            ("gemini:Zephyr-Female", "gemini_tts", "Zephyr"),
            ("mimo:mimo_default-Female", "mimo_tts", "mimo_default"),
            ("elevenlabs:abc123:Rachel", "elevenlabs_tts", "abc123"),
        )
        for voice_name, target, expected in cases:
            with self.subTest(voice_name=voice_name):
                result, backend, _ = self._tts(voice_name, target)

                self.assertEqual(result, "CALLED")
                self.assertEqual(backend.call_args.args[1], expected)

    def test_surrounding_whitespace_is_trimmed_from_a_valid_voice(self):
        result, backend, _ = self._tts("elevenlabs:  abc123  :Rachel", "elevenlabs_tts")

        self.assertEqual(result, "CALLED")
        self.assertEqual(backend.call_args.args[1], "abc123")


if __name__ == "__main__":
    unittest.main()
