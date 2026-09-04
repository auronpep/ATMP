import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestDetectAudioMime(unittest.TestCase):
    """Chooses the MIME type for the WebUI's voice-preview player.

    The comment on the function explains why it sniffs bytes rather than
    trusting the request: some OpenAI-compatible TTS servers return WAV even
    when asked for mp3, and a wrong MIME makes the browser refuse to play the
    preview — with no error anywhere, just a dead player.
    """

    @classmethod
    def setUpClass(cls):
        import webui.Main as webui_main

        cls.detect = staticmethod(webui_main._detect_audio_mime)

    # --- content sniffing wins over the extension ----------------------

    def test_riff_wave_header_is_detected_as_wav(self):
        header = b"RIFF\x24\x08\x00\x00WAVEfmt "

        self.assertEqual(self.detect("voice.mp3", header), "audio/wav")

    def test_id3_tagged_mp3_is_detected(self):
        self.assertEqual(self.detect("voice.bin", b"ID3\x03\x00\x00\x00\x00\x00\x00"), "audio/mp3")

    def test_raw_mpeg_frame_sync_is_detected_as_mp3(self):
        for sync in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
            with self.subTest(sync=sync):
                self.assertEqual(self.detect("voice.bin", sync + b"\x90d" * 4), "audio/mp3")

    def test_ogg_container_is_detected(self):
        self.assertEqual(self.detect("voice.bin", b"OggS\x00\x02" + b"\x00" * 6), "audio/ogg")

    def test_riff_without_wave_is_not_claimed_as_wav(self):
        # RIFF also fronts AVI and other containers; only WAVE is audio/wav.
        header = b"RIFF\x24\x08\x00\x00AVI LIST"

        self.assertNotEqual(self.detect("voice.bin", header), "audio/wav")

    # --- extension fallback when the bytes are unrecognised -------------

    def test_extension_is_used_when_the_header_is_unknown(self):
        cases = {
            "a.wav": "audio/wav",
            "a.m4a": "audio/mp4",
            "a.aac": "audio/aac",
            "a.ogg": "audio/ogg",
            "a.flac": "audio/flac",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.detect(name, b"unrecognised-header"), expected)

    def test_extension_matching_is_case_insensitive(self):
        self.assertEqual(self.detect("VOICE.FLAC", b"unrecognised-header"), "audio/flac")

    def test_unknown_header_and_extension_fall_back_to_mp3(self):
        self.assertEqual(self.detect("voice.xyz", b"unrecognised-header"), "audio/mp3")

    # --- robustness ----------------------------------------------------

    def test_short_and_empty_payloads_do_not_raise(self):
        for payload in (b"", b"R", b"RIFF"):
            with self.subTest(payload=payload):
                self.assertTrue(self.detect("voice.mp3", payload).startswith("audio/"))


if __name__ == "__main__":
    unittest.main()
