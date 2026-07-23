"""Local state persistence for Context Guardian.

All state lives under <project>/.claude/context-guardian/. Writes are
atomic (write-to-temp + rename) since a hook can be interrupted mid-write.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE_DIRNAME = os.path.join(".claude", "context-guardian")
SESSIONS_DIRNAME = "sessions"
CURRENT_POINTER_FILENAME = "current_session"
PENDING_CONTINUATION_FILENAME = "pending_continuation.json"


def state_root(cwd: str) -> Path:
    return Path(cwd) / STATE_DIRNAME


def sessions_root(cwd: str) -> Path:
    return state_root(cwd) / SESSIONS_DIRNAME


def session_dir(cwd: str, session_id: str) -> Path:
    return sessions_root(cwd) / session_id


def ensure_session_dir(cwd: str, session_id: str) -> Path:
    d = session_dir(cwd, session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".md")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def append_event(cwd: str, session_id: str, event_type: str, **fields) -> None:
    d = ensure_session_dir(cwd, session_id)
    record = {
        "timestamp": _now_iso(),
        "type": event_type,
        "sessionId": session_id,
    }
    record.update(fields)
    events_path = d / "events.jsonl"
    with open(events_path, "a") as f:
        f.write(json.dumps(record, sort_keys=False) + "\n")


def read_events(cwd: str, session_id: str):
    events_path = session_dir(cwd, session_id) / "events.jsonl"
    if not events_path.exists():
        return []
    out = []
    with open(events_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def set_current_session(cwd: str, session_id: str) -> None:
    root = state_root(cwd)
    root.mkdir(parents=True, exist_ok=True)
    atomic_write_text(root / CURRENT_POINTER_FILENAME, session_id.strip() + "\n")


def get_current_session(cwd: str):
    pointer = state_root(cwd) / CURRENT_POINTER_FILENAME
    if not pointer.exists():
        return _latest_session_by_mtime(cwd)
    session_id = pointer.read_text().strip()
    if session_id and session_dir(cwd, session_id).exists():
        return session_id
    return _latest_session_by_mtime(cwd)


def _latest_session_by_mtime(cwd: str):
    root = sessions_root(cwd)
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].name


def walk_lineage(cwd: str, session_id: str) -> list:
    """Walk `parentSessionId` backward from `session_id` to the root,
    returning each session's {sessionId, startedAt, status}, oldest-first.
    """
    chain = []
    seen = set()
    current_id = session_id
    while current_id and current_id not in seen:
        seen.add(current_id)
        session = read_json(session_json_path(cwd, current_id), default=None)
        if session is None:
            break
        chain.append({
            "sessionId": current_id,
            "startedAt": session.get("startedAt"),
            "status": session.get("status"),
        })
        current_id = session.get("parentSessionId")
    chain.reverse()
    return chain


def session_json_path(cwd: str, session_id: str) -> Path:
    return session_dir(cwd, session_id) / "session.json"


def state_json_path(cwd: str, session_id: str) -> Path:
    return session_dir(cwd, session_id) / "state.json"


def handover_md_path(cwd: str, session_id: str) -> Path:
    return session_dir(cwd, session_id) / "HANDOVER.md"


def handover_state_json_path(cwd: str, session_id: str) -> Path:
    return session_dir(cwd, session_id) / "handover_state.json"


def pending_continuation_json_path(cwd: str) -> Path:
    return state_root(cwd) / PENDING_CONTINUATION_FILENAME


def find_session_by_handover_id(cwd: str, handover_id: str):
    """Search every session's handover_state.json for a matching handoverId
    or lineageId. Returns the handover_state dict, or None if not found.
    """
    root = sessions_root(cwd)
    if not root.exists():
        return None
    for session_path in root.iterdir():
        if not session_path.is_dir():
            continue
        state = read_json(session_path / "handover_state.json", default=None)
        if state and (state.get("handoverId") == handover_id or state.get("lineageId") == handover_id):
            return state
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
