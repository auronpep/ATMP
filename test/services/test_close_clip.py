import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.video import close_clip


class _Reader:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _Leaf:
    """A clip that owns an ffmpeg-backed reader (VideoFileClip / AudioFileClip)."""

    def __init__(self):
        self.reader = _Reader()


class _CompositeAudio:
    """CompositeAudioClip shape: children, but no reader of its own."""

    def __init__(self, clips):
        self.clips = clips


class _Composite:
    def __init__(self, clips=None, audio=None, mask=None):
        self.clips = clips or []
        if audio is not None:
            self.audio = audio
        if mask is not None:
            self.mask = mask


class TestCloseClip(unittest.TestCase):
    """Every leaf reader holds an ffmpeg subprocess and an open pipe, so any
    branch this helper misses leaks one per render."""

    def test_none_is_a_no_op(self):
        close_clip(None)  # must not raise

    def test_leaf_reader_is_closed(self):
        leaf = _Leaf()

        close_clip(leaf)

        self.assertTrue(leaf.reader.closed)

    def test_child_clips_are_closed(self):
        child = _Leaf()

        close_clip(_Composite(clips=[child]))

        self.assertTrue(child.reader.closed)

    def test_plain_audio_reader_is_closed(self):
        audio = _Leaf()

        close_clip(_Composite(audio=audio))

        self.assertTrue(audio.reader.closed)

    def test_composite_audio_children_are_closed(self):
        # CompositeAudioClip has no .reader; the voice and BGM AudioFileClips
        # underneath it are what hold the ffmpeg processes.
        voice, bgm = _Leaf(), _Leaf()

        close_clip(_Composite(audio=_CompositeAudio([voice, bgm])))

        self.assertTrue(voice.reader.closed, "voice reader leaked")
        self.assertTrue(bgm.reader.closed, "bgm reader leaked")

    def test_video_and_audio_trees_are_both_drained(self):
        source, voice, bgm = _Leaf(), _Leaf(), _Leaf()

        close_clip(_Composite(clips=[source], audio=_CompositeAudio([voice, bgm])))

        self.assertTrue(all(c.reader.closed for c in (source, voice, bgm)))

    def test_mask_reader_is_closed(self):
        mask = _Leaf()

        close_clip(_Composite(mask=mask))

        self.assertTrue(mask.reader.closed)

    def test_nested_composites_are_drained(self):
        deep = _Leaf()

        close_clip(_Composite(clips=[_Composite(clips=[_Composite(clips=[deep])])]))

        self.assertTrue(deep.reader.closed)

    def test_self_reference_does_not_recurse_forever(self):
        clip = _Composite()
        clip.clips = [clip]
        clip.audio = clip

        close_clip(clip)  # must return rather than hit the recursion limit

    def test_a_failing_close_does_not_propagate(self):
        class _Exploding:
            @property
            def reader(self):
                raise RuntimeError("boom")

        close_clip(_Exploding())  # logged, not raised


if __name__ == "__main__":
    unittest.main()
