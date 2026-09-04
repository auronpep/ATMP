import sys
import threading
import time
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import voice as vs


class _SyncCommunicate:
    """edge_tts 7.x shape: exposes stream_sync()."""

    def __init__(self, chunks, delay=0.0, raises=None):
        self._chunks = chunks
        self._delay = delay
        self._raises = raises

    def stream_sync(self):
        for chunk in self._chunks:
            if self._delay:
                time.sleep(self._delay)
            yield chunk
        if self._raises:
            raise self._raises


class _AsyncCommunicate:
    """Older edge_tts shape: only an async stream()."""

    def __init__(self, chunks):
        self._chunks = chunks

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


class TestStreamEdgeTtsChunks(unittest.TestCase):
    """`azure_tts_v1` is the default TTS path. This shim is what lets it work
    against both the 7.x sync stream and an older async-only install, and what
    stops a stalled network read from hanging the task forever."""

    def _collect(self, communicate, timeout=None):
        received = []
        vs.stream_edge_tts_chunks(communicate, received.append, timeout_seconds=timeout)
        return received

    def test_sync_stream_is_consumed_in_order(self):
        chunks = [{"type": "audio", "data": b"a"}, {"type": "WordBoundary"}]

        self.assertEqual(self._collect(_SyncCommunicate(chunks)), chunks)

    def test_sync_stream_with_timeout_is_consumed_in_order(self):
        chunks = [{"type": "audio", "data": b"a"}, {"type": "audio", "data": b"b"}]

        self.assertEqual(self._collect(_SyncCommunicate(chunks), timeout=5), chunks)

    def test_async_only_communicate_is_supported(self):
        chunks = [{"type": "audio", "data": b"x"}]

        self.assertEqual(self._collect(_AsyncCommunicate(chunks)), chunks)

    def test_async_stream_honours_a_timeout(self):
        self.assertEqual(self._collect(_AsyncCommunicate([{"n": 1}]), timeout=5), [{"n": 1}])

    def test_object_without_any_stream_method_raises(self):
        with self.assertRaises(AttributeError):
            vs.stream_edge_tts_chunks(types.SimpleNamespace(), lambda c: None)

    def test_producer_errors_propagate_to_the_caller(self):
        communicate = _SyncCommunicate([{"n": 1}], raises=RuntimeError("stream broke"))

        with self.assertRaises(RuntimeError):
            self._collect(communicate, timeout=5)

    def test_a_stalled_stream_times_out_instead_of_hanging(self):
        class _Stalled:
            def stream_sync(self):
                # Never yields; models a socket that connected and went quiet.
                time.sleep(30)
                yield {"n": 1}

        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            self._collect(_Stalled(), timeout=0.2)

        # Must return promptly rather than waiting out the stall.
        self.assertLess(time.monotonic() - started, 5)

    def test_timeout_does_not_leave_the_caller_thread_blocked(self):
        class _Stalled:
            def stream_sync(self):
                time.sleep(30)
                yield {"n": 1}

        before = threading.current_thread()
        with self.assertRaises(TimeoutError):
            self._collect(_Stalled(), timeout=0.2)

        self.assertIs(threading.current_thread(), before)

    def test_no_timeout_means_no_deadline(self):
        chunks = [{"n": i} for i in range(3)]

        self.assertEqual(self._collect(_SyncCommunicate(chunks), timeout=None), chunks)


if __name__ == "__main__":
    unittest.main()
