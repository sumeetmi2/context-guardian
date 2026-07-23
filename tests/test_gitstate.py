import subprocess
import tempfile
import unittest
from pathlib import Path

from lib import gitstate


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class GitstateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_non_repo_returns_is_repo_false(self):
        state = gitstate.collect(self.cwd)
        self.assertFalse(state["isRepo"])
        self.assertIsNone(state["branch"])
        self.assertIsNone(state["head"])
        self.assertEqual(state["statusShort"], [])

    def test_repo_with_no_commits(self):
        _git(self.cwd, "init", "-q")
        state = gitstate.collect(self.cwd)
        self.assertTrue(state["isRepo"])
        # No commits yet, so HEAD doesn't resolve.
        self.assertIsNone(state["head"])

    def test_repo_with_commit_and_dirty_file(self):
        _git(self.cwd, "init", "-q")
        _git(self.cwd, "config", "user.email", "test@example.com")
        _git(self.cwd, "config", "user.name", "Test")
        (Path(self.cwd) / "committed.txt").write_text("hello\n")
        _git(self.cwd, "add", "committed.txt")
        _git(self.cwd, "commit", "-q", "-m", "initial")
        (Path(self.cwd) / "untracked.txt").write_text("new\n")

        state = gitstate.collect(self.cwd)
        self.assertTrue(state["isRepo"])
        self.assertIsNotNone(state["head"])
        self.assertTrue(any("untracked.txt" in line for line in state["statusShort"]))

    def test_changed_files_parses_status_short(self):
        git_state = {"statusShort": ["?? new.txt", " M modified.txt", "R  old.txt -> new_name.txt"]}
        files = gitstate.changed_files(git_state)
        self.assertIn("new.txt", files)
        self.assertIn("modified.txt", files)
        self.assertIn("new_name.txt", files)
        self.assertNotIn("old.txt", files)

    def test_changed_files_empty_when_no_status(self):
        self.assertEqual(gitstate.changed_files({"statusShort": []}), [])


if __name__ == "__main__":
    unittest.main()
