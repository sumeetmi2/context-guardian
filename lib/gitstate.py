"""Deterministic git state capture (FR-19). Never infers repo state from the
model — only from these commands, run directly.
"""

import subprocess


def _run(cwd: str, args):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def collect(cwd: str) -> dict:
    toplevel = _run(cwd, ["rev-parse", "--show-toplevel"])
    if toplevel is None:
        return {
            "isRepo": False,
            "toplevel": None,
            "branch": None,
            "head": None,
            "statusShort": [],
            "diffStat": None,
            "diffCachedStat": None,
        }

    branch = _run(cwd, ["branch", "--show-current"])
    head = _run(cwd, ["rev-parse", "HEAD"])
    status_short_raw = _run(cwd, ["status", "--short"]) or ""
    diff_stat = _run(cwd, ["diff", "--stat"])
    diff_cached_stat = _run(cwd, ["diff", "--cached", "--stat"])

    return {
        "isRepo": True,
        "toplevel": toplevel,
        "branch": branch or None,
        "head": head or None,
        "statusShort": [line for line in status_short_raw.splitlines() if line.strip()],
        "diffStat": diff_stat or None,
        "diffCachedStat": diff_cached_stat or None,
    }


def changed_files(git_state: dict):
    """Best-effort list of touched paths, derived from `git status --short`."""
    files = []
    for line in git_state.get("statusShort", []):
        # Format: "XY path" or "XY orig -> new" for renames.
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if "->" in path:
            path = path.split("->")[-1].strip()
        if path:
            files.append(path)
    return files
