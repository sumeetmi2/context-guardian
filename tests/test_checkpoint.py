import tempfile
import unittest
from pathlib import Path

from lib import checkpoint as checkpoint_mod
from lib import config as config_mod
from lib import store


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name
        self.session_id = "s1"
        # build_checkpoint now reads config (monitoring.contextWindowTokens),
        # so isolate USER_CONFIG_PATH like test_config.py/test_handover.py do
        # — a real ~/.claude/context-guardian.json must never leak in here.
        self._orig_user_path = config_mod.USER_CONFIG_PATH
        config_mod.USER_CONFIG_PATH = Path(self.cwd) / "fake_home" / "context-guardian.json"

    def tearDown(self):
        config_mod.USER_CONFIG_PATH = self._orig_user_path
        self._tmp.cleanup()

    def test_first_checkpoint_has_empty_narrative_fields(self):
        cp = checkpoint_mod.build_checkpoint(self.cwd, self.session_id)
        self.assertIsNone(cp["objective"])
        self.assertEqual(cp["decisions"], [])
        self.assertEqual(cp["remainingWork"], [])
        self.assertIn("gitState", cp)
        self.assertIn("utilizationEstimate", cp)

    def test_overrides_apply_only_to_known_narrative_fields(self):
        cp = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id,
            overrides={"objective": "ship the feature", "notAField": "ignored"},
        )
        self.assertEqual(cp["objective"], "ship the feature")
        self.assertNotIn("notAField", cp)

    def test_write_then_rebuild_carries_forward_narrative_fields(self):
        cp1 = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id,
            overrides={"objective": "fix the bug", "remainingWork": ["write tests"]},
        )
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp1)

        cp2 = checkpoint_mod.build_checkpoint(self.cwd, self.session_id)
        self.assertEqual(cp2["objective"], "fix the bug")
        self.assertEqual(cp2["remainingWork"], ["write tests"])

    def test_second_checkpoint_overrides_win_over_carried_forward(self):
        cp1 = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id, overrides={"objective": "first objective"},
        )
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp1)

        cp2 = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id, overrides={"objective": "second objective"},
        )
        self.assertEqual(cp2["objective"], "second objective")

    def test_write_checkpoint_persists_to_disk(self):
        cp = checkpoint_mod.build_checkpoint(self.cwd, self.session_id)
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp)
        on_disk = store.read_json(store.state_json_path(self.cwd, self.session_id))
        self.assertEqual(on_disk["sessionId"], self.session_id)

    def test_build_checkpoint_honors_configured_context_window(self):
        config_mod.write_project_config(self.cwd, {"monitoring": {"contextWindowTokens": 500_000}})
        cp = checkpoint_mod.build_checkpoint(self.cwd, self.session_id)
        self.assertEqual(cp["utilizationEstimate"]["contextWindowTokens"], 500_000)

    def test_write_checkpoint_appends_event(self):
        cp = checkpoint_mod.build_checkpoint(self.cwd, self.session_id)
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp)
        events = store.read_events(self.cwd, self.session_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "checkpoint_created")


if __name__ == "__main__":
    unittest.main()
