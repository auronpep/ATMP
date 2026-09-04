import sys
import unittest
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import asgi


class TestLifespanHandlers(unittest.TestCase):
    def test_startup_and_shutdown_are_logged_through_lifespan(self):
        from starlette.testclient import TestClient

        records = []
        handler_id = asgi.logger.add(lambda m: records.append(m.record["message"]))
        try:
            with TestClient(asgi.app):
                pass
        finally:
            asgi.logger.remove(handler_id)

        self.assertIn("startup event", records)
        self.assertIn("shutdown event", records)

    def test_app_registers_no_deprecated_on_event_handlers(self):
        # `@app.on_event` appends to these legacy lists and emits a
        # DeprecationWarning on FastAPI 0.136.3. Lifespan handlers leave them empty.
        self.assertEqual(asgi.app.router.on_startup, [])
        self.assertEqual(asgi.app.router.on_shutdown, [])

    def test_building_the_app_emits_no_on_event_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            asgi.get_application()

        on_event_warnings = [
            str(w.message) for w in caught if "on_event is deprecated" in str(w.message)
        ]
        self.assertEqual(on_event_warnings, [])


if __name__ == "__main__":
    unittest.main()
