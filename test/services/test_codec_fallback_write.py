import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import video as vd

HARDWARE = "h264_nvenc"
DEFAULT = "libx264"


class _RecordingClip:
    """Stands in for a MoviePy clip; records each write_videofile attempt."""

    def __init__(self, fail_codecs=()):
        self.attempts = []
        self._fail_codecs = set(fail_codecs)

    def write_videofile(self, output_file, codec=None, **kwargs):
        self.attempts.append(codec)
        if codec in self._fail_codecs:
            raise RuntimeError(f"{codec} unavailable")


class TestWriteVideofileWithCodecFallback(unittest.TestCase):
    """A hardware encoder that FFmpeg advertises can still fail at runtime on
    the GPU or driver. A render must never die because of that — but the
    fallback also must not mask a genuine IO failure by blaming the codec."""

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

    def _encoders_available(self, *codecs):
        body = "\n".join(f" V....D {c}  {c}" for c in codecs)
        return patch.object(
            vd.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, f"Encoders:\n{body}\n", ""),
        )

    def test_successful_hardware_write_is_used_as_is(self):
        clip = _RecordingClip()

        with self._encoders_available(DEFAULT, HARDWARE):
            used = vd._write_videofile_with_codec_fallback(clip, "out.mp4", HARDWARE)

        self.assertEqual(used, HARDWARE)
        self.assertEqual(clip.attempts, [HARDWARE])
        self.assertNotIn(HARDWARE, vd._runtime_disabled_video_codecs)

    def test_hardware_failure_retries_with_libx264(self):
        clip = _RecordingClip(fail_codecs=[HARDWARE])

        with self._encoders_available(DEFAULT, HARDWARE):
            used = vd._write_videofile_with_codec_fallback(clip, "out.mp4", HARDWARE)

        self.assertEqual(used, DEFAULT)
        self.assertEqual(clip.attempts, [HARDWARE, DEFAULT])

    def test_a_successful_retry_disables_the_hardware_codec_for_the_process(self):
        clip = _RecordingClip(fail_codecs=[HARDWARE])

        with self._encoders_available(DEFAULT, HARDWARE):
            vd._write_videofile_with_codec_fallback(clip, "out.mp4", HARDWARE)

        self.assertIn(HARDWARE, vd._runtime_disabled_video_codecs)

    def test_a_failing_retry_leaves_the_codec_enabled_and_reraises(self):
        # Both attempts failing means the cause is probably IO (locked file,
        # permissions, AV), not the encoder. Blaming the codec would wrongly
        # disable it for every later clip in the task.
        clip = _RecordingClip(fail_codecs=[HARDWARE, DEFAULT])

        with self._encoders_available(DEFAULT, HARDWARE):
            with self.assertRaises(RuntimeError):
                vd._write_videofile_with_codec_fallback(clip, "out.mp4", HARDWARE)

        self.assertNotIn(HARDWARE, vd._runtime_disabled_video_codecs)

    def test_libx264_failure_propagates_without_a_pointless_retry(self):
        clip = _RecordingClip(fail_codecs=[DEFAULT])

        with self.assertRaises(RuntimeError):
            vd._write_videofile_with_codec_fallback(clip, "out.mp4", DEFAULT)

        self.assertEqual(clip.attempts, [DEFAULT])

    def test_write_kwargs_are_forwarded_on_both_attempts(self):
        received = []

        class _Clip:
            def write_videofile(self, output_file, codec=None, **kwargs):
                received.append(kwargs)
                if codec == HARDWARE:
                    raise RuntimeError("nope")

        with self._encoders_available(DEFAULT, HARDWARE):
            vd._write_videofile_with_codec_fallback(
                _Clip(), "out.mp4", HARDWARE, fps=30, threads=2, logger=None
            )

        self.assertEqual(len(received), 2)
        for kwargs in received:
            self.assertEqual(kwargs["fps"], 30)
            self.assertEqual(kwargs["threads"], 2)


class TestFfmpegConcatPathEscaping(unittest.TestCase):
    """The concat demuxer wraps each path in single quotes, so a quote in a
    filename would terminate the string and corrupt the list file."""

    def test_plain_paths_are_unchanged(self):
        self.assertEqual(vd._escape_ffmpeg_concat_path("plain.mp4"), "plain.mp4")

    def test_spaces_are_preserved(self):
        self.assertEqual(vd._escape_ffmpeg_concat_path("a b.mp4"), "a b.mp4")

    def test_single_quotes_are_escaped(self):
        self.assertEqual(
            vd._escape_ffmpeg_concat_path("it's here.mp4"),
            "it'" + chr(92) + "''s here.mp4",
        )

    def test_formatted_paths_use_forward_slashes(self):
        formatted = vd._format_ffmpeg_concat_path("some/clip.mp4")

        self.assertNotIn("\\", formatted)

    def test_formatted_paths_are_absolute(self):
        import os

        formatted = vd._format_ffmpeg_concat_path("clip.mp4")

        self.assertTrue(os.path.isabs(formatted.replace("/", os.sep)))


if __name__ == "__main__":
    unittest.main()
