import importlib
import sys
import unittest
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import MaterialInfo


class TestNoDeprecatedPydanticConfig(unittest.TestCase):
    """Pydantic V2 deprecated class-based `Config` and removes it in V3."""

    def test_importing_the_schema_module_emits_no_class_based_config_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import app.models.schema as schema

            importlib.reload(schema)

        offenders = [
            str(w.message) for w in caught if "class-based `config`" in str(w.message)
        ]
        self.assertEqual(offenders, [])

    def test_schema_module_declares_no_nested_config_classes(self):
        source = (
            Path(__file__).parent.parent.parent / "app" / "models" / "schema.py"
        ).read_text(encoding="utf-8")

        # assertTrue, not assertNotIn: a failing assertNotIn dumps the whole
        # 380-line module into the report.
        self.assertTrue(
            "class Config:" not in source,
            "schema.py still declares a nested class Config",
        )


class TestSchemaExamplesSurvive(unittest.TestCase):
    """`json_schema_extra` drives the examples shown in /docs, so the migration
    must not drop them."""

    @classmethod
    def setUpClass(cls):
        from starlette.testclient import TestClient

        from app.asgi import app

        cls.spec = TestClient(app, raise_server_exceptions=False).get(
            "/openapi.json"
        ).json()

    def test_response_models_still_publish_examples(self):
        documented = [
            name
            for name, schema in self.spec["components"]["schemas"].items()
            if "example" in schema
        ]

        self.assertGreaterEqual(len(documented), 10)

    def test_task_response_example_is_intact(self):
        example = self.spec["components"]["schemas"]["TaskResponse"]["example"]

        self.assertEqual(example["status"], 200)
        self.assertIn("task_id", example["data"])


class TestMaterialInfoDataclass(unittest.TestCase):
    """MaterialInfo is a pydantic dataclass configured with
    arbitrary_types_allowed; the config migration must keep it constructible."""

    def test_defaults(self):
        material = MaterialInfo()

        self.assertEqual(material.provider, "pexels")
        self.assertEqual(material.url, "")
        self.assertEqual(material.duration, 0)

    def test_explicit_values(self):
        material = MaterialInfo(provider="local", url="/x.mp4", duration=3)

        self.assertEqual(material.provider, "local")
        self.assertEqual(material.url, "/x.mp4")
        self.assertEqual(material.duration, 3)

    def test_attributes_are_mutable(self):
        # material.url is reassigned during preprocess_video().
        material = MaterialInfo()
        material.url = "/converted.mp4"

        self.assertEqual(material.url, "/converted.mp4")


if __name__ == "__main__":
    unittest.main()
