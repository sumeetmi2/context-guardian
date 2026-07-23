import tempfile
import unittest
from pathlib import Path

from lib import checkpoint as checkpoint_mod
from lib import config as config_mod
from lib import handover, store


class HandoverValidateTests(unittest.TestCase):
    def setUp(self):
        self.effective_config = config_mod.DEFAULTS

    def _cp(self, **overrides):
        base = {
            "sessionId": "s1",
            "timestamp": "2026-01-01T00:00:00+0000",
            "modifiedFiles": [],
            "gitDiffSummary": None,
            "testStatus": "unknown",
            "utilizationEstimate": {"utilizationPercent": 10},
            "gitState": {"isRepo": True, "toplevel": "/repo", "branch": "main",
                         "head": "abc123", "statusShort": [], "diffStat": None,
                         "diffCachedStat": None},
            "objective": None, "currentPlan": None, "lastCompletedAction": None,
            "nextExpectedAction": None, "nextAction": None, "repositoryContext": None,
            "userCommunicationState": None, "pendingQuestions": [], "decisions": [],
            "constraints": [], "filesInspected": [], "commandsExecuted": [],
            "evidence": [], "risks": [], "remainingWork": [], "doNotRepeat": [],
        }
        base.update(overrides)
        return base

    def test_valid_handover_passes(self):
        cp = self._cp(nextAction="run the tests")
        md = handover.build_handover_markdown("/repo", "s1", "cg-h1", "cg-l1", None, cp)
        j = handover.build_handover_json("s1", "cg-h1", "cg-l1", None, cp)
        ok, reasons = handover.validate(md, j, self.effective_config)
        self.assertTrue(ok, reasons)
        self.assertEqual(reasons, [])

    def test_missing_next_action_fails(self):
        cp = self._cp(nextAction=None)
        md = handover.build_handover_markdown("/repo", "s1", "cg-h1", "cg-l1", None, cp)
        j = handover.build_handover_json("s1", "cg-h1", "cg-l1", None, cp)
        ok, reasons = handover.validate(md, j, self.effective_config)
        self.assertFalse(ok)
        self.assertTrue(any("next action" in r for r in reasons))

    def test_non_git_repo_does_not_fail_validation(self):
        cp = self._cp(
            nextAction="do the thing",
            gitState={"isRepo": False, "toplevel": None, "branch": None, "head": None,
                      "statusShort": [], "diffStat": None, "diffCachedStat": None},
        )
        md = handover.build_handover_markdown("/tmp/nogit", "s1", "cg-h1", "cg-l1", None, cp)
        j = handover.build_handover_json("s1", "cg-h1", "cg-l1", None, cp)
        ok, reasons = handover.validate(md, j, self.effective_config)
        self.assertTrue(ok, reasons)
        self.assertIn("WARNING: no git repository detected", md)

    def test_secret_in_markdown_fails_validation(self):
        cp = self._cp(nextAction="rotate the leaked key",
                       evidence=["found AKIAABCDEFGHIJKLMNOP in logs"])
        md = handover.build_handover_markdown("/repo", "s1", "cg-h1", "cg-l1", None, cp)
        j = handover.build_handover_json("s1", "cg-h1", "cg-l1", None, cp)
        ok, reasons = handover.validate(md, j, self.effective_config)
        self.assertFalse(ok)
        self.assertTrue(any("secret" in r for r in reasons))

    def test_oversized_handover_fails_validation(self):
        cp = self._cp(nextAction="x", evidence=["y" * 50000])
        md = handover.build_handover_markdown("/repo", "s1", "cg-h1", "cg-l1", None, cp)
        j = handover.build_handover_json("s1", "cg-h1", "cg-l1", None, cp)
        ok, reasons = handover.validate(md, j, self.effective_config)
        self.assertFalse(ok)
        self.assertTrue(any("exceeds maximumTokens" in r for r in reasons))

    def test_all_required_sections_present(self):
        cp = self._cp(nextAction="do it")
        md = handover.build_handover_markdown("/repo", "s1", "cg-h1", "cg-l1", None, cp)
        for header in ["## Identity", "## Objective", "## Decisions made",
                       "## Git state", "## Next action", "## Do not repeat"]:
            self.assertIn(header, md)

    def test_identity_block_has_four_distinct_ids(self):
        cp = self._cp(nextAction="do it")
        md = handover.build_handover_markdown("/repo", "s1", "cg-h1", "cg-l1", "cg-h0", cp)
        self.assertIn("Handover ID: cg-h1", md)
        self.assertIn("Source session ID: s1", md)
        self.assertIn("Lineage ID: cg-l1", md)
        self.assertIn("Parent handover ID: cg-h0", md)

    def test_identity_block_root_session_shows_none_for_parent_handover(self):
        cp = self._cp(nextAction="do it")
        md = handover.build_handover_markdown("/repo", "s1", "cg-h1", "cg-l1", None, cp)
        self.assertIn("Parent handover ID: none", md)

    def test_fact_tag_defaults_to_unverified_for_plain_strings(self):
        self.assertEqual(handover._fact_tag("plain fact"), "[unverified] plain fact")

    def test_fact_tag_uses_provided_status(self):
        self.assertEqual(
            handover._fact_tag({"text": "confirmed fact", "status": "confirmed"}),
            "[confirmed] confirmed fact",
        )


class HandoverGenerateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name
        self.session_id = "s1"
        self._orig_user_path = config_mod.USER_CONFIG_PATH
        config_mod.USER_CONFIG_PATH = Path(self.cwd) / "fake_home" / "context-guardian.json"

    def tearDown(self):
        config_mod.USER_CONFIG_PATH = self._orig_user_path
        self._tmp.cleanup()

    def test_generate_fails_without_next_action_and_writes_no_file(self):
        result = handover.generate(self.cwd, self.session_id)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["path"])
        self.assertFalse(store.handover_md_path(self.cwd, self.session_id).exists())

    def test_generate_succeeds_after_setting_next_action(self):
        cp = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id, overrides={"nextAction": "write the README"}
        )
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp)

        result = handover.generate(self.cwd, self.session_id)
        self.assertTrue(result["ok"], result["reasons"])
        self.assertTrue(store.handover_md_path(self.cwd, self.session_id).exists())
        self.assertIn("write the README", result["markdown"])

    def test_generate_redacts_secrets_before_writing(self):
        # checkpoint.build_checkpoint's security.redactBeforeStateWrite (default
        # on) already redacts narrative fields at checkpoint time, so by the
        # time handover.generate() re-derives cp and redacts the rendered
        # markdown, the secret is long gone from state.json too — defense in
        # depth, not just a final markdown-only redaction pass.
        cp = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id,
            overrides={
                "nextAction": "rotate credentials",
                "evidence": ["leaked key AKIAABCDEFGHIJKLMNOP found in commit"],
            },
        )
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", cp["evidence"][0])
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp)

        result = handover.generate(self.cwd, self.session_id)
        self.assertTrue(result["ok"], result["reasons"])
        on_disk = store.handover_md_path(self.cwd, self.session_id).read_text()
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", on_disk)

    def test_checkpoint_redaction_can_be_disabled(self):
        config_mod.write_project_config(self.cwd, {"security": {"redactBeforeStateWrite": False}})
        cp = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id,
            overrides={"evidence": ["leaked key AKIAABCDEFGHIJKLMNOP found in commit"]},
        )
        self.assertIn("AKIAABCDEFGHIJKLMNOP", cp["evidence"][0])

    def test_generate_reuses_lineage_id_but_mints_fresh_handover_id(self):
        cp = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id, overrides={"nextAction": "step one"}
        )
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp)
        first = handover.generate(self.cwd, self.session_id)
        first_state = store.read_json(store.handover_state_json_path(self.cwd, self.session_id))

        cp2 = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id, overrides={"nextAction": "step two"}
        )
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp2)
        second = handover.generate(self.cwd, self.session_id)
        second_state = store.read_json(store.handover_state_json_path(self.cwd, self.session_id))

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(first_state["lineageId"], second_state["lineageId"])
        self.assertNotEqual(first_state["handoverId"], second_state["handoverId"])
        self.assertIn(second_state["lineageId"], second["markdown"])

    def test_generate_inherits_lineage_linked_at_session_start(self):
        store.atomic_write_json(
            store.session_json_path(self.cwd, self.session_id),
            {
                "sessionId": self.session_id, "parentSessionId": "s0",
                "parentHandoverId": "cg-parent-handover", "lineageId": "cg-inherited",
            },
        )
        cp = checkpoint_mod.build_checkpoint(
            self.cwd, self.session_id, overrides={"nextAction": "continue prior work"}
        )
        checkpoint_mod.write_checkpoint(self.cwd, self.session_id, cp)

        result = handover.generate(self.cwd, self.session_id)
        self.assertTrue(result["ok"], result["reasons"])
        handover_state = store.read_json(store.handover_state_json_path(self.cwd, self.session_id))
        self.assertEqual(handover_state["lineageId"], "cg-inherited")
        self.assertEqual(handover_state["parentHandoverId"], "cg-parent-handover")
        self.assertEqual(handover_state["sourceSessionId"], self.session_id)


if __name__ == "__main__":
    unittest.main()
