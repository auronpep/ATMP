import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

FILE_SIZE = 1000


class TestParseRangeHeader(unittest.TestCase):
    def setUp(self):
        from app.controllers.v1.video import RANGE_UNSATISFIABLE, parse_range_header

        self.parse = parse_range_header
        self.UNSATISFIABLE = RANGE_UNSATISFIABLE

    def _parse(self, header):
        return self.parse(header, FILE_SIZE)

    def test_simple_range(self):
        self.assertEqual(self._parse("bytes=0-99"), (0, 99))

    def test_open_ended_range_runs_to_the_last_byte(self):
        self.assertEqual(self._parse("bytes=990-"), (990, 999))

    def test_end_beyond_eof_is_clamped(self):
        # Otherwise Content-Length promises more bytes than the file holds and
        # the client waits forever for data that never arrives.
        self.assertEqual(self._parse("bytes=0-999999"), (0, 999))

    def test_suffix_range_returns_the_last_n_bytes(self):
        self.assertEqual(self._parse("bytes=-100"), (900, 999))

    def test_suffix_range_larger_than_the_file_returns_the_whole_file(self):
        self.assertEqual(self._parse("bytes=-5000"), (0, 999))

    def test_unit_is_matched_case_insensitively(self):
        self.assertEqual(self._parse("BYTES=0-9"), (0, 9))

    def test_start_past_eof_is_unsatisfiable(self):
        self.assertIs(self._parse("bytes=5000-"), self.UNSATISFIABLE)

    def test_ignored_when_unparseable_or_unsupported(self):
        for header in (
            None,
            "",
            "garbage",
            "items=0-10",          # wrong unit
            "bytes=abc-def",       # non-numeric
            "bytes=0-10,20-30",    # multipart, not supported
            "bytes=500-100",       # end before start
            "bytes=-0",            # zero-length suffix
            "bytes=100",           # no separator
        ):
            with self.subTest(header=header):
                self.assertIsNone(self._parse(header))

    def test_empty_file_makes_any_range_unsatisfiable(self):
        self.assertIs(self.parse("bytes=0-", 0), self.UNSATISFIABLE)


class TestStreamEndpointRangeResponses(unittest.TestCase):
    """End-to-end through the real route."""

    @classmethod
    def setUpClass(cls):
        from starlette.testclient import TestClient

        from app.asgi import app
        from app.utils import utils

        cls.task_id = "test-range-endpoint"
        cls.task_dir = utils.task_dir(cls.task_id)
        with open(os.path.join(cls.task_dir, "final-1.mp4"), "wb") as f:
            f.write(b"A" * FILE_SIZE)
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.url = f"/api/v1/stream/{cls.task_id}/final-1.mp4"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.task_dir, ignore_errors=True)

    def _get(self, range_header=None):
        headers = {"Range": range_header} if range_header is not None else {}
        return self.client.get(self.url, headers=headers)

    def test_content_length_always_matches_the_body(self):
        # The core invariant. A mismatch leaves the client hanging.
        for header in (
            None,
            "bytes=0-99",
            "bytes=0-999999",
            "bytes=990-",
            "bytes=-100",
            "bytes=-5000",
            "bytes=abc-def",
            "items=0-10",
            "bytes=0-10,20-30",
            "garbage",
        ):
            with self.subTest(header=header):
                response = self._get(header)
                self.assertEqual(
                    int(response.headers["Content-Length"]), len(response.content)
                )

    def test_malformed_ranges_are_ignored_rather_than_erroring(self):
        for header in ("garbage", "items=0-10", "bytes=abc-def", "bytes=0-10,20-30"):
            with self.subTest(header=header):
                response = self._get(header)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.content), FILE_SIZE)

    def test_valid_range_returns_partial_content(self):
        response = self._get("bytes=0-99")

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"A" * 100)
        self.assertEqual(response.headers["Content-Range"], f"bytes 0-99/{FILE_SIZE}")

    def test_range_past_eof_returns_416_with_the_file_size(self):
        response = self._get("bytes=5000-")

        self.assertEqual(response.status_code, 416)
        self.assertEqual(response.headers["Content-Range"], f"bytes */{FILE_SIZE}")

    def test_no_range_header_returns_the_whole_file_as_200(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content), FILE_SIZE)

    def test_accept_ranges_is_always_advertised(self):
        for header in (None, "bytes=0-99", "bytes=5000-"):
            with self.subTest(header=header):
                self.assertEqual(self._get(header).headers["Accept-Ranges"], "bytes")


if __name__ == "__main__":
    unittest.main()
