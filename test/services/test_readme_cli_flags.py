import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import cli

REPO_ROOT = Path(__file__).parent.parent.parent
READMES = sorted(REPO_ROOT.glob("README*.md"))
FLAG_RE = re.compile(r"--[a-z][a-z0-9-]*")


def _documented_cli_flags(text):
    """Flags appearing on a line that invokes cli.py, including continuations."""
    flags = set()
    in_cli_command = False
    for line in text.splitlines():
        stripped = line.strip()
        if "cli.py" in stripped:
            in_cli_command = True
        if in_cli_command:
            flags.update(FLAG_RE.findall(stripped))
            # a shell continuation keeps the command open
            if not stripped.endswith("\\"):
                in_cli_command = False
    return flags


def _parser_flags():
    parser = cli.parse_args.__globals__["argparse"].ArgumentParser()
    # Build the real parser by invoking parse_args on --help would exit, so
    # inspect the module's own parser construction instead.
    import contextlib
    import io as _io

    buffer = _io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            cli.parse_args(["--help"])
        except SystemExit:
            pass
    return set(FLAG_RE.findall(buffer.getvalue()))


class TestReadmeCliFlagsExist(unittest.TestCase):
    """Documented commands are copy-pasted by users.

    A flag that no longer exists fails with `unrecognized arguments`, which
    reads like the user's mistake rather than a stale doc.
    """

    @classmethod
    def setUpClass(cls):
        cls.parser_flags = _parser_flags()

    def test_the_parser_exposes_flags(self):
        self.assertTrue(self.parser_flags, "could not read flags from --help")

    def test_every_readme_documents_only_real_flags(self):
        self.assertTrue(READMES, "no README files found")

        for readme in READMES:
            documented = _documented_cli_flags(readme.read_text(encoding="utf-8"))
            unknown = sorted(documented - self.parser_flags)
            with self.subTest(readme=readme.name):
                self.assertEqual(
                    unknown, [], f"{readme.name} documents non-existent CLI flags"
                )

    def test_the_primary_documented_example_parses(self):
        args = cli.parse_args(["--video-subject", "The Role of Money"])

        self.assertEqual(args.video_subject, "The Role of Money")

    def test_the_local_materials_example_parses(self):
        args = cli.parse_args(
            [
                "--video-subject", "The Role of Money",
                "--video-source", "local",
                "--video-materials", "1.mp4,2.mp4",
                "--stop-at", "video",
            ]
        )

        self.assertEqual(args.video_source, "local")
        self.assertEqual(args.video_materials, "1.mp4,2.mp4")
        self.assertEqual(args.stop_at, "video")

    def test_video_subject_is_required(self):
        import contextlib
        import io as _io

        with contextlib.redirect_stderr(_io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.parse_args([])


if __name__ == "__main__":
    unittest.main()
