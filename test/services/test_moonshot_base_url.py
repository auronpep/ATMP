import io
import re
import sys
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import llm

REPO_ROOT = Path(__file__).parent.parent.parent


class TestMoonshotBaseUrl(unittest.TestCase):
    """`moonshot_base_url` is documented in config.example.toml, so a user who
    points it at a corporate gateway expects it to be used. It was hardcoded,
    so the setting silently did nothing and requests kept going to the public
    endpoint — no error, and no way to tell from the outside."""

    def setUp(self):
        self.original_app = dict(config.app)
        config.app["llm_provider"] = "moonshot"
        config.app["moonshot_api_key"] = "sk-test"
        config.app["moonshot_model_name"] = "moonshot-v1-8k"

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app)

    def _captured_base_url(self):
        captured = {}

        class _Completions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(message=SimpleNamespace(content="hello"))
                    ]
                )

        def fake_openai(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                chat=SimpleNamespace(completions=_Completions())
            )

        with patch.object(llm, "OpenAI", side_effect=fake_openai):
            llm._generate_response("hi")
        return captured.get("base_url")

    def test_configured_base_url_is_used(self):
        config.app["moonshot_base_url"] = "https://gateway.internal/v1"

        self.assertEqual(self._captured_base_url(), "https://gateway.internal/v1")

    def test_unset_base_url_falls_back_to_the_official_endpoint(self):
        config.app.pop("moonshot_base_url", None)

        self.assertEqual(self._captured_base_url(), "https://api.moonshot.cn/v1")

    def test_empty_base_url_falls_back_to_the_official_endpoint(self):
        config.app["moonshot_base_url"] = ""

        self.assertEqual(self._captured_base_url(), "https://api.moonshot.cn/v1")

    def test_the_documented_default_matches_the_code_fallback(self):
        example = tomllib.load(open(REPO_ROOT / "config.example.toml", "rb"))

        self.assertEqual(
            example["app"]["moonshot_base_url"], "https://api.moonshot.cn/v1"
        )


class TestNoDocumentedAppKeyIsDeadConfig(unittest.TestCase):
    """A key documented in config.example.toml that nothing reads is a setting
    the user can change with no effect."""

    KNOWN_UNREAD = {
        # Documented as "API Key is optional - leave empty for public access",
        # but the pollinations branch sends no Authorization header, so a
        # configured key is never used. Left as-is here: the correct auth
        # mechanism for that API needs verifying against their docs, and
        # guessing a header format would be worse than reporting it.
        "pollinations_api_key",
    }

    def test_every_documented_app_key_is_read_somewhere(self):
        sources = [
            "app/services/llm.py", "app/services/material.py", "app/services/task.py",
            "app/services/video.py", "app/services/voice.py", "app/services/subtitle.py",
            "app/services/twelvelabs.py", "app/services/upload_post.py",
            "app/controllers/v1/video.py", "app/controllers/base.py",
            "app/config/config.py", "app/services/state.py", "webui/Main.py",
        ]
        source = "".join(
            io.open(REPO_ROOT / p, encoding="utf-8").read() for p in sources
        )
        read = set(re.findall(r'config\.app\.get\(\s*["\']([a-z0-9_]+)["\']', source))
        read |= set(re.findall(r'config\.app\[\s*["\']([a-z0-9_]+)["\']', source))
        read |= set(re.findall(r'app\.get\(\s*["\']([a-z0-9_]+)["\']', source))

        example = tomllib.load(open(REPO_ROOT / "config.example.toml", "rb"))
        dead = sorted(set(example["app"]) - read - self.KNOWN_UNREAD)

        self.assertEqual(dead, [], f"documented but never read: {dead}")


if __name__ == "__main__":
    unittest.main()
