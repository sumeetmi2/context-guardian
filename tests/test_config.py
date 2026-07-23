import tempfile
import unittest
from pathlib import Path

from lib import config as config_mod


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name
        self._orig_user_path = config_mod.USER_CONFIG_PATH
        # Point user config at a fresh path inside the temp dir so real
        # ~/.claude/context-guardian.json never leaks into test results.
        config_mod.USER_CONFIG_PATH = Path(self.cwd) / "fake_home" / "context-guardian.json"

    def tearDown(self):
        config_mod.USER_CONFIG_PATH = self._orig_user_path
        self._tmp.cleanup()

    def test_defaults_when_no_config_files(self):
        cfg = config_mod.get_effective_config(self.cwd)
        self.assertEqual(cfg["monitoring"]["warningThresholdPercent"], 72)
        self.assertFalse(cfg["compaction"]["automatic"])
        self.assertTrue(cfg["enabled"])

    def test_project_config_overrides_defaults(self):
        config_mod.write_project_config(self.cwd, {"monitoring": {"warningThresholdPercent": 50}})
        cfg = config_mod.get_effective_config(self.cwd)
        self.assertEqual(cfg["monitoring"]["warningThresholdPercent"], 50)
        # Sibling keys in the same nested dict must survive the merge.
        self.assertEqual(cfg["monitoring"]["compactThresholdPercent"], 84)

    def test_user_config_overrides_defaults_but_not_project(self):
        config_mod.USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        config_mod.USER_CONFIG_PATH.write_text('{"monitoring": {"warningThresholdPercent": 40}}')
        config_mod.write_project_config(self.cwd, {"monitoring": {"warningThresholdPercent": 60}})
        cfg = config_mod.get_effective_config(self.cwd)
        self.assertEqual(cfg["monitoring"]["warningThresholdPercent"], 60)

    def test_overrides_param_wins_over_everything(self):
        config_mod.write_project_config(self.cwd, {"monitoring": {"warningThresholdPercent": 60}})
        cfg = config_mod.get_effective_config(
            self.cwd, overrides={"monitoring": {"warningThresholdPercent": 99}}
        )
        self.assertEqual(cfg["monitoring"]["warningThresholdPercent"], 99)

    def test_corrupt_project_config_falls_back_to_defaults(self):
        path = config_mod.project_config_path(self.cwd)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not valid")
        cfg = config_mod.get_effective_config(self.cwd)
        self.assertEqual(cfg["monitoring"]["warningThresholdPercent"], 72)

    def test_set_enabled_roundtrip(self):
        config_mod.set_enabled(self.cwd, False)
        self.assertFalse(config_mod.get_effective_config(self.cwd)["enabled"])
        config_mod.set_enabled(self.cwd, True)
        self.assertTrue(config_mod.get_effective_config(self.cwd)["enabled"])

    def test_deep_merge_does_not_mutate_base(self):
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"b": 99}}
        result = config_mod._deep_merge(base, override)
        self.assertEqual(result, {"a": {"b": 99, "c": 2}})
        self.assertEqual(base, {"a": {"b": 1, "c": 2}})


if __name__ == "__main__":
    unittest.main()
