import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLE = REPO_ROOT / "config.example.toml"

UPLOAD_POST_KEYS = (
    "upload_post_enabled",
    "upload_post_api_key",
    "upload_post_username",
    "upload_post_platforms",
    "upload_post_auto_upload",
    "upload_post_youtube_privacy_status",
)


def _example():
    with open(EXAMPLE, "rb") as handle:
        return tomllib.load(handle)


class TestUploadPostKeysLandInTheAppSection(unittest.TestCase):
    """`config.example.toml` is copied verbatim to `config.toml` on first run,
    so a key documented under the wrong TOML section is simply never read.

    Every Upload-Post setting is consumed via `config.app.get(...)`, so they
    must sit above the first `[section]` header.
    """

    @classmethod
    def setUpClass(cls):
        cls.example = _example()

    def test_all_upload_post_keys_are_in_app(self):
        for key in UPLOAD_POST_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.example["app"])

    def test_no_upload_post_key_leaked_into_ui(self):
        for key in UPLOAD_POST_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, self.example.get("ui", {}))

    def test_the_service_reads_the_documented_defaults(self):
        # The example ships the feature disabled; the service must agree.
        from app.config import config
        from app.services import upload_post

        original = dict(config.app)
        try:
            config.app.clear()
            config.app.update(self.example["app"])
            service = upload_post.UploadPostService()

            self.assertFalse(service.is_configured())
            self.assertFalse(service.auto_upload)
            self.assertEqual(service.platforms, ["tiktok", "instagram"])
            self.assertEqual(service.youtube_privacy_status, "public")
        finally:
            config.app.clear()
            config.app.update(original)

    def test_filling_in_the_documented_keys_enables_the_feature(self):
        # The actual user journey: copy the example, fill in three values.
        from app.config import config
        from app.services import upload_post

        original = dict(config.app)
        try:
            config.app.clear()
            config.app.update(self.example["app"])
            config.app["upload_post_api_key"] = "key"
            config.app["upload_post_username"] = "user"
            config.app["upload_post_enabled"] = True

            self.assertTrue(upload_post.UploadPostService().is_configured())
        finally:
            config.app.clear()
            config.app.update(original)


class TestEveryConfigSectionIsReadFromWhereItIsDocumented(unittest.TestCase):
    """Generalises the above: a key documented under `[x]` but read via
    `config.y.get(...)` is dead configuration."""

    def test_ui_section_only_documents_keys_the_ui_reads(self):
        import io
        import re

        example = _example()
        source = io.open(REPO_ROOT / "webui" / "Main.py", encoding="utf-8").read()
        source += io.open(REPO_ROOT / "app" / "models" / "schema.py", encoding="utf-8").read()
        ui_reads = set(re.findall(r'config\.ui\.get\(\s*["\']([a-z0-9_]+)["\']', source))

        for key in example.get("ui", {}):
            with self.subTest(key=key):
                self.assertIn(
                    key, ui_reads, f"[ui] documents {key!r} but nothing reads config.ui[{key!r}]"
                )


if __name__ == "__main__":
    unittest.main()
