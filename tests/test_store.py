import json
import tempfile
import unittest
from pathlib import Path

from lib import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_atomic_write_json_roundtrip(self):
        path = Path(self.cwd) / "sub" / "data.json"
        store.atomic_write_json(path, {"a": 1})
        self.assertEqual(store.read_json(path), {"a": 1})

    def test_atomic_write_json_no_leftover_tmp_files(self):
        path = Path(self.cwd) / "data.json"
        store.atomic_write_json(path, {"a": 1})
        leftovers = list(Path(self.cwd).glob(".tmp-*"))
        self.assertEqual(leftovers, [])

    def test_read_json_missing_returns_default(self):
        path = Path(self.cwd) / "missing.json"
        self.assertEqual(store.read_json(path, default="fallback"), "fallback")

    def test_read_json_corrupt_returns_default(self):
        path = Path(self.cwd) / "bad.json"
        path.write_text("{not valid json")
        self.assertEqual(store.read_json(path, default={}), {})

    def test_append_event_and_read_events(self):
        store.append_event(self.cwd, "s1", "session_started", source="startup")
        store.append_event(self.cwd, "s1", "metric_sampled", utilizationPercent=10)
        events = store.read_events(self.cwd, "s1")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "session_started")
        self.assertEqual(events[1]["utilizationPercent"], 10)

    def test_read_events_skips_corrupt_lines(self):
        d = store.ensure_session_dir(self.cwd, "s1")
        events_path = d / "events.jsonl"
        events_path.write_text('{"type": "ok"}\nnot json\n{"type": "ok2"}\n')
        events = store.read_events(self.cwd, "s1")
        self.assertEqual([e["type"] for e in events], ["ok", "ok2"])

    def test_read_events_missing_file_returns_empty(self):
        self.assertEqual(store.read_events(self.cwd, "nope"), [])

    def test_current_session_pointer_roundtrip(self):
        store.set_current_session(self.cwd, "abc")
        store.ensure_session_dir(self.cwd, "abc")
        self.assertEqual(store.get_current_session(self.cwd), "abc")

    def test_get_current_session_falls_back_to_latest_by_mtime(self):
        store.ensure_session_dir(self.cwd, "older")
        store.ensure_session_dir(self.cwd, "newer")
        newer_dir = store.session_dir(self.cwd, "newer")
        import os
        import time

        now = time.time()
        os.utime(store.session_dir(self.cwd, "older"), (now - 100, now - 100))
        os.utime(newer_dir, (now, now))
        self.assertEqual(store.get_current_session(self.cwd), "newer")

    def test_get_current_session_no_sessions_returns_none(self):
        self.assertIsNone(store.get_current_session(self.cwd))

    def test_get_current_session_pointer_to_deleted_session_falls_back(self):
        store.set_current_session(self.cwd, "ghost")
        store.ensure_session_dir(self.cwd, "real")
        self.assertEqual(store.get_current_session(self.cwd), "real")

    def test_walk_lineage_root_session_only(self):
        store.atomic_write_json(
            store.session_json_path(self.cwd, "s1"),
            {"sessionId": "s1", "startedAt": "t1", "status": "active", "parentSessionId": None},
        )
        chain = store.walk_lineage(self.cwd, "s1")
        self.assertEqual([e["sessionId"] for e in chain], ["s1"])

    def test_walk_lineage_chain_oldest_first(self):
        store.atomic_write_json(
            store.session_json_path(self.cwd, "s1"),
            {"sessionId": "s1", "startedAt": "t1", "status": "ended", "parentSessionId": None},
        )
        store.atomic_write_json(
            store.session_json_path(self.cwd, "s2"),
            {"sessionId": "s2", "startedAt": "t2", "status": "ended", "parentSessionId": "s1"},
        )
        store.atomic_write_json(
            store.session_json_path(self.cwd, "s3"),
            {"sessionId": "s3", "startedAt": "t3", "status": "active", "parentSessionId": "s2"},
        )
        chain = store.walk_lineage(self.cwd, "s3")
        self.assertEqual([e["sessionId"] for e in chain], ["s1", "s2", "s3"])

    def test_walk_lineage_missing_session_returns_empty(self):
        self.assertEqual(store.walk_lineage(self.cwd, "nope"), [])

    def test_walk_lineage_breaks_cycle(self):
        store.atomic_write_json(
            store.session_json_path(self.cwd, "a"),
            {"sessionId": "a", "startedAt": "t1", "status": "active", "parentSessionId": "b"},
        )
        store.atomic_write_json(
            store.session_json_path(self.cwd, "b"),
            {"sessionId": "b", "startedAt": "t2", "status": "active", "parentSessionId": "a"},
        )
        chain = store.walk_lineage(self.cwd, "a")
        self.assertEqual(len(chain), 2)

    def test_path_helpers(self):
        self.assertTrue(str(store.session_json_path(self.cwd, "s1")).endswith(
            str(Path("s1") / "session.json")
        ))
        self.assertTrue(str(store.state_json_path(self.cwd, "s1")).endswith(
            str(Path("s1") / "state.json")
        ))
        self.assertTrue(str(store.handover_md_path(self.cwd, "s1")).endswith(
            str(Path("s1") / "HANDOVER.md")
        ))


if __name__ == "__main__":
    unittest.main()
