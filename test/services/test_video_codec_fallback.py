import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import video as vd

HARDWARE_CODEC = "h264_nvenc"
DEFAULT = "libx264"


def _encoders_output(*codecs):
    body = "\n".join(f" V....D {c}    {c} encoder" for c in codecs)
    return f"Encoders:\n{body}\n"


class _CodecTestCase(unittest.TestCase):
    def setUp(self):
        self.original_app = dict(config.app)
        self.original_disabled = set(vd._runtime_disabled_video_codecs)
        vd._runtime_disabled_video_codecs.clear()
        vd._ffmpeg_encoder_exists.cache_clear()

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)
        vd._runtime_disabled_video_codecs.clear()
        vd._runtime_disabled_video_codecs.update(self.original_disabled)
        vd._ffmpeg_encoder_exists.cache_clear()


class TestConfiguredVideoCodec(_CodecTestCase):
    def test_default_when_unset(self):
        config.app.pop("video_codec", None)
        self.assertEqual(vd._get_configured_video_codec(), DEFAULT)

    def test_supported_codec_is_returned(self):
        config.app["video_codec"] = HARDWARE_CODEC
        self.assertEqual(vd._get_configured_video_codec(), HARDWARE_CODEC)

    def test_surrounding_whitespace_is_tolerated(self):
        config.app["video_codec"] = f"  {HARDWARE_CODEC}  "
        self.assertEqual(vd._get_configured_video_codec(), HARDWARE_CODEC)

    def test_unsupported_value_falls_back_to_the_default(self):
        # The allowlist exists so a typo can't inject arbitrary ffmpeg args.
        for value in ("h264_totally_made_up", "-vcodec copy", "libx265"):
            with self.subTest(value=value):
                config.app["video_codec"] = value
                self.assertEqual(vd._get_configured_video_codec(), DEFAULT)

    def test_empty_or_none_falls_back_to_the_default(self):
        for value in ("", None):
            with self.subTest(value=value):
                config.app["video_codec"] = value
                self.assertEqual(vd._get_configured_video_codec(), DEFAULT)


class TestEffectiveVideoCodec(_CodecTestCase):
    def test_default_codec_skips_the_ffmpeg_probe(self):
        # libx264 is always present; probing would be a wasted subprocess on
        # every clip.
        with patch.object(vd.subprocess, "run") as run:
            self.assertEqual(vd._get_effective_video_codec(DEFAULT), DEFAULT)
        run.assert_not_called()

    def test_available_hardware_encoder_is_used(self):
        with patch.object(
            vd.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [], 0, _encoders_output(DEFAULT, HARDWARE_CODEC), ""
            ),
        ):
            self.assertEqual(
                vd._get_effective_video_codec(HARDWARE_CODEC), HARDWARE_CODEC
            )

    def test_encoder_missing_from_ffmpeg_falls_back(self):
        with patch.object(
            vd.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, _encoders_output(DEFAULT), ""),
        ):
            self.assertEqual(vd._get_effective_video_codec(HARDWARE_CODEC), DEFAULT)

    def test_ffmpeg_probe_failure_falls_back(self):
        for side_effect in (
            OSError("ffmpeg missing"),
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10),
        ):
            with self.subTest(side_effect=type(side_effect).__name__):
                vd._ffmpeg_encoder_exists.cache_clear()
                with patch.object(vd.subprocess, "run", side_effect=side_effect):
                    self.assertEqual(
                        vd._get_effective_video_codec(HARDWARE_CODEC), DEFAULT
                    )

    def test_nonzero_probe_exit_code_falls_back(self):
        with patch.object(
            vd.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 1, "", "boom"),
        ):
            self.assertEqual(vd._get_effective_video_codec(HARDWARE_CODEC), DEFAULT)

    def test_runtime_disabled_codec_is_not_retried(self):
        vd._disable_runtime_video_codec(HARDWARE_CODEC, "nvenc device not available")

        # No ffmpeg probe should happen once the codec is known-bad; otherwise
        # every clip in the task repeats the same failing detection.
        with patch.object(vd.subprocess, "run") as run:
            self.assertEqual(vd._get_effective_video_codec(HARDWARE_CODEC), DEFAULT)
        run.assert_not_called()

    def test_reads_the_configured_codec_when_none_is_passed(self):
        config.app["video_codec"] = HARDWARE_CODEC
        with patch.object(
            vd.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [], 0, _encoders_output(DEFAULT, HARDWARE_CODEC), ""
            ),
        ):
            self.assertEqual(vd._get_effective_video_codec(), HARDWARE_CODEC)


class TestRuntimeCodecDisabling(_CodecTestCase):
    def test_hardware_codec_is_recorded_as_disabled(self):
        vd._disable_runtime_video_codec(HARDWARE_CODEC, "driver error")

        self.assertIn(HARDWARE_CODEC, vd._runtime_disabled_video_codecs)

    def test_the_default_codec_is_never_disabled(self):
        # Disabling libx264 would leave no working encoder at all.
        vd._disable_runtime_video_codec(DEFAULT, "some failure")

        self.assertNotIn(DEFAULT, vd._runtime_disabled_video_codecs)


if __name__ == "__main__":
    unittest.main()
