import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils


class TestOpenTaskFolder(unittest.TestCase):
    """Hands a path to the OS shell via webbrowser.open.

    The comment on the function states the two protections: validate the id as
    a UUID so nothing exotic reaches the shell, and re-check containment even
    after that, in case the caller's source of task ids ever changes.
    """

    @classmethod
    def setUpClass(cls):
        import webui.Main as webui_main

        cls.main = webui_main

    def setUp(self):
        self.task_id = str(uuid.uuid4())
        self.task_dir = utils.task_dir(self.task_id)
        self.addCleanup(shutil.rmtree, self.task_dir, True)

    def _open(self, task_id):
        opened = []
        with patch.object(
            self.main.webbrowser, "open", side_effect=lambda url: opened.append(url)
        ):
            self.main.open_task_folder(task_id)
        return opened

    def test_a_real_task_folder_is_opened(self):
        opened = self._open(self.task_id)

        self.assertEqual(len(opened), 1)
        self.assertIn(self.task_id, opened[0])
        self.assertTrue(opened[0].startswith("file://"))

    def test_traversal_ids_are_refused(self):
        for task_id in ("../../etc", "..", "../" + self.task_id, "/etc/passwd"):
            with self.subTest(task_id=task_id):
                self.assertEqual(self._open(task_id), [])

    def test_non_uuid_ids_are_refused(self):
        for task_id in ("not-a-uuid", "", "; rm -rf /", "task 1", "%2e%2e"):
            with self.subTest(task_id=task_id):
                self.assertEqual(self._open(task_id), [])

    def test_none_is_refused_without_raising(self):
        self.assertEqual(self._open(None), [])

    def test_a_valid_uuid_with_no_folder_opens_nothing(self):
        self.assertEqual(self._open(str(uuid.uuid4())), [])

    def test_uuid_is_normalised_before_use(self):
        # Upper-case / brace forms parse as the same UUID and must resolve to
        # the same canonical directory rather than a second one.
        opened = self._open(self.task_id.upper())

        self.assertEqual(len(opened), 1)
        self.assertIn(self.task_id, opened[0])

    def test_opened_path_stays_inside_the_tasks_root(self):
        opened = self._open(self.task_id)
        tasks_root = Path(utils.task_dir()).resolve()
        target = Path(opened[0].replace("file://", "")).resolve()

        self.assertEqual(
            Path(shutil.os.path.commonpath([tasks_root, target])), tasks_root
        )


if __name__ == "__main__":
    unittest.main()
