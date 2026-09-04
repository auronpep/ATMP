import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import voice as vs

SENTINEL = object()
OUT = "/tmp/dispatch-test.mp3"


class TestTtsProviderDispatch(unittest.TestCase):
    """`tts()` routes on the voice-name prefix and unpacks provider arguments
    out of it. A mis-route sends the request to the wrong backend, and a bad
    unpack sends the wrong model or voice id — both surface only as a remote
    API error, with nothing pointing back at the parsing."""

    def _dispatch(self, target, voice_name):
        with patch.object(vs, target, return_value=SENTINEL) as mock:
            result = vs.tts(
                text="hello",
                voice_name=voice_name,
                voice_rate=1.0,
                voice_file=OUT,
                voice_volume=1.0,
            )
        self.assertIs(result, SENTINEL, f"{voice_name} was not routed to {target}")
        mock.assert_called_once()
        return mock.call_args

    def test_siliconflow_voice_passes_model_and_qualified_voice(self):
        args = self._dispatch(
            "siliconflow_tts", "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male"
        )

        # signature: (text, model, full_voice, voice_rate, voice_file, voice_volume)
        self.assertEqual(args.args[1], "FunAudioLLM/CosyVoice2-0.5B")
        self.assertEqual(args.args[2], "FunAudioLLM/CosyVoice2-0.5B:alex")

    def test_gemini_voice_strips_the_gender_suffix(self):
        args = self._dispatch("gemini_tts", "gemini:Zephyr-Female")

        self.assertEqual(args.args[1], "Zephyr")

    def test_mimo_voice_strips_the_gender_suffix(self):
        args = self._dispatch("mimo_tts", "mimo:mimo_default-Female")

        self.assertEqual(args.args[1], "mimo_default")

    def test_elevenlabs_voice_passes_the_voice_id(self):
        args = self._dispatch("elevenlabs_tts", "elevenlabs:abc123:Rachel")

        self.assertEqual(args.args[1], "abc123")

    def test_chatterbox_keeps_hyphens_inside_the_voice_name(self):
        # Chatterbox voices are operator-defined and routinely contain hyphens.
        # Only a trailing -Female/-Male display suffix may be stripped.
        args = self._dispatch("chatterbox_tts", "chatterbox:my-custom-voice")

        self.assertEqual(args.args[1], "my-custom-voice")

    def test_chatterbox_strips_only_the_trailing_gender_suffix(self):
        args = self._dispatch("chatterbox_tts", "chatterbox:my-custom-voice-Female")

        self.assertEqual(args.args[1], "my-custom-voice")

    def test_azure_v2_voice_uses_the_v2_path(self):
        self._dispatch("azure_tts_v2", "zh-CN-XiaoxiaoMultilingualNeural-V2-Female")

    def test_plain_voice_falls_through_to_azure_v1(self):
        self._dispatch("azure_tts_v1", "zh-CN-XiaoxiaoNeural-Female")

    def test_incomplete_siliconflow_and_chatterbox_names_are_rejected(self):
        # Both guard the voice segment before dispatching.
        for voice_name, target in (
            ("siliconflow:onlymodel", "siliconflow_tts"),
            ("chatterbox:", "chatterbox_tts"),
        ):
            with self.subTest(voice_name=voice_name):
                with patch.object(vs, target) as backend, patch.object(
                    vs, "azure_tts_v1"
                ) as fallback:
                    result = vs.tts(
                        text="hello",
                        voice_name=voice_name,
                        voice_rate=1.0,
                        voice_file=OUT,
                    )
                self.assertIsNone(result)
                backend.assert_not_called()
                # must not silently fall through to the default provider
                fallback.assert_not_called()

    def test_empty_voice_segment_currently_reaches_the_backend(self):
        """Documents current behaviour, which is inconsistent.

        siliconflow and chatterbox validate the voice segment before
        dispatching; gemini, mimo and elevenlabs do not, so "gemini:" calls the
        provider with an empty voice and the failure surfaces as an opaque
        remote API error instead of the "Invalid ... voice name format" log the
        other branches already produce. Pinned here so the difference is
        visible rather than accidental.
        """
        for voice_name, target in (
            ("gemini:", "gemini_tts"),
            ("mimo:", "mimo_tts"),
            ("elevenlabs:", "elevenlabs_tts"),
        ):
            with self.subTest(voice_name=voice_name):
                with patch.object(vs, target, return_value=SENTINEL) as backend:
                    result = vs.tts(
                        text="hello",
                        voice_name=voice_name,
                        voice_rate=1.0,
                        voice_file=OUT,
                    )
                self.assertIs(result, SENTINEL)
                self.assertEqual(backend.call_args.args[1], "")


if __name__ == "__main__":
    unittest.main()
