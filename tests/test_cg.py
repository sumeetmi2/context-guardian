import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

from lib import store

_CG_PATH = Path(__file__).resolve().parent.parent / "bin" / "cg.py"
_spec = importlib.util.spec_from_file_location("cg", _CG_PATH)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class LineageLinkingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name
        self._orig_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmp.cleanup()

    def _session(self, session_id, **overrides):
        session = {
            "sessionId": session_id, "lineageId": None, "parentSessionId": None,
            "childSessionId": None, "repository": self.cwd, "branch": "main",
            "startedAt": "2026-01-01T00:00:00+0000", "endedAt": None, "model": "unknown",
            "metricsSource": "heuristic-estimation", "compactionCount": 0, "turnCount": 0,
            "status": "active", "transcriptBytesAtLastCompaction": 0,
            "lastNotifiedStatus": "nominal", "lastNotifiedTurn": 0,
        }
        session.update(overrides)
        store.atomic_write_json(store.session_json_path(self.cwd, session_id), session)
        return session

    def test_no_marker_means_no_auto_link(self):
        self._session("s1")
        new_session = self._session("s2")
        cg._maybe_link_lineage(self.cwd, "s2", new_session, "s1")

        relinked = store.read_json(store.session_json_path(self.cwd, "s2"))
        self.assertIsNone(relinked["parentSessionId"])
        self.assertIsNone(relinked["lineageId"])

    def test_unrelated_prior_handover_does_not_auto_link(self):
        # Even if s1 generated a handover in the past, without a pending
        # marker naming s1 specifically, a fresh s2 must not auto-link.
        self._session("s1")
        store.atomic_write_json(
            store.handover_state_json_path(self.cwd, "s1"),
            {"handoverId": "cg-old", "lineageId": "cg-old", "sourceSessionId": "s1"},
        )
        new_session = self._session("s2")
        cg._maybe_link_lineage(self.cwd, "s2", new_session, "s1")

        relinked = store.read_json(store.session_json_path(self.cwd, "s2"))
        self.assertIsNone(relinked["parentSessionId"])

    def test_matching_unexpired_marker_links_and_is_consumed(self):
        self._session("s1")
        store.atomic_write_json(store.pending_continuation_json_path(self.cwd), {
            "sessionId": "s1", "lineageId": "cg-abc", "handoverId": "cg-abc",
            "expiresAt": time.time() + 60,
        })
        new_session = self._session("s2")
        cg._maybe_link_lineage(self.cwd, "s2", new_session, "s1")

        relinked = store.read_json(store.session_json_path(self.cwd, "s2"))
        self.assertEqual(relinked["parentSessionId"], "s1")
        self.assertEqual(relinked["lineageId"], "cg-abc")
        parent = store.read_json(store.session_json_path(self.cwd, "s1"))
        self.assertEqual(parent["childSessionId"], "s2")
        self.assertFalse(store.pending_continuation_json_path(self.cwd).exists())

    def test_expired_marker_does_not_link_and_is_removed(self):
        self._session("s1")
        store.atomic_write_json(store.pending_continuation_json_path(self.cwd), {
            "sessionId": "s1", "lineageId": "cg-abc", "handoverId": "cg-abc",
            "expiresAt": time.time() - 1,
        })
        new_session = self._session("s2")
        cg._maybe_link_lineage(self.cwd, "s2", new_session, "s1")

        relinked = store.read_json(store.session_json_path(self.cwd, "s2"))
        self.assertIsNone(relinked["parentSessionId"])
        self.assertFalse(store.pending_continuation_json_path(self.cwd).exists())

    def test_marker_for_a_different_session_does_not_link(self):
        self._session("s1")
        store.atomic_write_json(store.pending_continuation_json_path(self.cwd), {
            "sessionId": "s0", "lineageId": "cg-abc", "handoverId": "cg-abc",
            "expiresAt": time.time() + 60,
        })
        new_session = self._session("s2")
        cg._maybe_link_lineage(self.cwd, "s2", new_session, "s1")

        relinked = store.read_json(store.session_json_path(self.cwd, "s2"))
        self.assertIsNone(relinked["parentSessionId"])


class CmdContinueTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name
        self._orig_cwd = os.getcwd()
        os.chdir(self.cwd)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmp.cleanup()

    def _session(self, session_id):
        session = {
            "sessionId": session_id, "lineageId": None, "parentSessionId": None,
            "childSessionId": None, "repository": self.cwd, "branch": "main",
            "startedAt": "2026-01-01T00:00:00+0000", "endedAt": None, "model": "unknown",
            "status": "active",
        }
        store.atomic_write_json(store.session_json_path(self.cwd, session_id), session)
        return session

    def test_continue_links_current_session_to_matching_handover(self):
        self._session("s1")
        store.atomic_write_json(
            store.handover_state_json_path(self.cwd, "s1"),
            {"handoverId": "cg-xyz", "lineageId": "cg-xyz", "sourceSessionId": "s1"},
        )
        self._session("s2")
        store.set_current_session(self.cwd, "s2")

        cg.cmd_continue(_Args(handover_id="cg-xyz"))

        linked = store.read_json(store.session_json_path(self.cwd, "s2"))
        self.assertEqual(linked["parentSessionId"], "s1")
        self.assertEqual(linked["lineageId"], "cg-xyz")

    def test_continue_exits_nonzero_for_unknown_handover_id(self):
        self._session("s2")
        store.set_current_session(self.cwd, "s2")
        with self.assertRaises(SystemExit):
            cg.cmd_continue(_Args(handover_id="cg-nope"))

    def test_continue_refuses_self_link(self):
        self._session("s1")
        store.atomic_write_json(
            store.handover_state_json_path(self.cwd, "s1"),
            {"handoverId": "cg-xyz", "lineageId": "cg-xyz", "sourceSessionId": "s1"},
        )
        store.set_current_session(self.cwd, "s1")
        with self.assertRaises(SystemExit):
            cg.cmd_continue(_Args(handover_id="cg-xyz"))


class FindSessionByHandoverIdTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_finds_by_handover_id_or_lineage_id(self):
        store.atomic_write_json(
            store.handover_state_json_path(self.cwd, "s1"),
            {"handoverId": "cg-h1", "lineageId": "cg-l1", "sourceSessionId": "s1"},
        )
        self.assertEqual(store.find_session_by_handover_id(self.cwd, "cg-h1")["sourceSessionId"], "s1")
        self.assertEqual(store.find_session_by_handover_id(self.cwd, "cg-l1")["sourceSessionId"], "s1")
        self.assertIsNone(store.find_session_by_handover_id(self.cwd, "cg-nope"))


if __name__ == "__main__":
    unittest.main()
