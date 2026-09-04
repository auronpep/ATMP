import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.controllers import base
from app.models.exception import HttpException
from app.utils import utils


class TestGetTaskId(unittest.TestCase):
    """Correlates log lines and error messages with a caller's request."""

    def _request(self, header=None):
        request = MagicMock()
        request.headers = {"x-task-id": header} if header is not None else {}
        return request

    def test_supplied_header_is_used(self):
        self.assertEqual(base.get_task_id(self._request("caller-123")), "caller-123")

    def test_missing_header_gets_a_generated_id(self):
        generated = base.get_task_id(self._request())

        self.assertTrue(generated)
        self.assertIsInstance(generated, str)

    def test_generated_ids_are_unique(self):
        ids = {base.get_task_id(self._request()) for _ in range(5)}

        self.assertEqual(len(ids), 5)

    def test_result_is_always_a_string(self):
        # It is interpolated into messages and paths.
        for header in ("abc", None, ""):
            with self.subTest(header=header):
                self.assertIsInstance(base.get_task_id(self._request(header)), str)


class TestHttpException(unittest.TestCase):
    """Carries the status/message/data that reach the client."""

    def test_fields_are_retained(self):
        exc = HttpException(task_id="t1", status_code=418, message="teapot", data={"a": 1})

        self.assertEqual(exc.status_code, 418)
        self.assertEqual(exc.message, "teapot")
        self.assertEqual(exc.data, {"a": 1})

    def test_defaults(self):
        exc = HttpException(task_id="t1", status_code=500)

        self.assertEqual(exc.message, "")
        self.assertIsNone(exc.data)

    def test_client_errors_log_at_warning_and_others_at_error(self):
        from app.models import exception as exception_module

        levels = []
        handler_id = exception_module.logger.add(
            lambda m: levels.append(m.record["level"].name)
        )
        try:
            HttpException(task_id="t1", status_code=400, message="bad input")
            HttpException(task_id="t1", status_code=500, message="boom")
        finally:
            exception_module.logger.remove(handler_id)

        self.assertEqual(levels, ["WARNING", "ERROR"])


class TestGetResponse(unittest.TestCase):
    """Envelope shared by every endpoint."""

    def test_status_only(self):
        self.assertEqual(utils.get_response(200), {"status": 200})

    def test_data_and_message_are_included(self):
        response = utils.get_response(200, {"task_id": "t1"}, "ok")

        self.assertEqual(response["status"], 200)
        self.assertEqual(response["data"], {"task_id": "t1"})
        self.assertEqual(response["message"], "ok")


class TestApiErrorResponses(unittest.TestCase):
    """End-to-end through the real app."""

    @classmethod
    def setUpClass(cls):
        from starlette.testclient import TestClient

        from app.asgi import app

        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_validation_failure_returns_400_with_field_details(self):
        response = self.client.post("/api/v1/videos", json={})
        payload = response.json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["status"], 400)
        self.assertEqual(payload["message"], "field required")
        self.assertTrue(any("video_subject" in str(item) for item in payload["data"]))

    def test_unknown_task_returns_404_in_the_standard_envelope(self):
        response = self.client.get("/api/v1/tasks/does-not-exist")
        payload = response.json()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(payload["status"], 404)
        self.assertIn("task not found", payload["message"])

    def test_deleting_an_unknown_task_returns_404(self):
        response = self.client.delete("/api/v1/tasks/does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], 404)

    def test_error_body_status_matches_the_http_status(self):
        # Clients read the envelope, not just the HTTP code; a mismatch is a
        # silent trap.
        for request in (
            lambda: self.client.post("/api/v1/videos", json={}),
            lambda: self.client.get("/api/v1/tasks/nope"),
            lambda: self.client.delete("/api/v1/tasks/nope"),
        ):
            response = request()
            with self.subTest(url=response.url):
                self.assertEqual(response.json()["status"], response.status_code)

    def test_the_request_id_is_echoed_in_the_error_message(self):
        response = self.client.get(
            "/api/v1/tasks/nope", headers={"x-task-id": "my-correlation-id"}
        )

        self.assertIn("my-correlation-id", response.json()["message"])


if __name__ == "__main__":
    unittest.main()
