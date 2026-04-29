#!/usr/bin/env python3
"""
Claude Code session archival hook.

Wired into Claude Code via two hooks in ~/.claude/settings.json:

  Stop          -> reconcile JSONLs in the current session's project dir
                   (catches the parent session and any subagent transcripts)
  SessionEnd    -> full sweep of ~/.claude/projects/ (catches anything missed,
                   e.g. crashed sessions, abandoned project dirs)

Reconciliation, not event-reaction: each invocation makes the archive match
the source for the JSONLs in scope, rather than archiving only the file
named in the hook payload. This means a missed event gets swept up by the
next one, and subagent transcripts (which don't appear as transcript_path)
are caught by the per-Stop scoped scan.

Archive destination: read from CLAUDE_CODE_SOURCES in the repo's .env, using
the entry matching the current hostname. The migration script
(migrations/002_setup_claude_code_archival.py) sets this up automatically.

Key assumption: source JSONL transcripts are immutable append-only logs.
Claude Code's context compression operates at API request time and does not
rewrite transcript files. The line-count based sync depends on this — if it
ever changes, archives could diverge. Truncation detection writes to
claude_code_anomalies.log as a canary for this assumption.
"""

from __future__ import annotations

import fcntl
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
from paths import CLAUDE_CODE_SOURCES_ENV_KEY, parse_claude_code_sources  # noqa: E402

CLAUDE_DIR = Path.home() / ".claude"
CLAUDE_PROJECTS_DIR = CLAUDE_DIR / "projects"
ANOMALY_LOG = REPO_ROOT / "claude_code_anomalies.log"
ENV_FILE = REPO_ROOT / ".env"


def load_env(env_path: Path) -> dict:
    config = {}
    if not env_path.exists():
        return config
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()
    return config


def resolve_archive_dir() -> Path:
    """Return the archive path for the current hostname from CLAUDE_CODE_SOURCES."""
    config = load_env(ENV_FILE)
    sources = parse_claude_code_sources(config)
    if not sources:
        raise RuntimeError(
            f"{CLAUDE_CODE_SOURCES_ENV_KEY} is not set in {ENV_FILE}. "
            f"Run `python migrations/002_setup_claude_code_archival.py` to configure."
        )
    host = socket.gethostname()
    for entry_host, path in sources:
        if entry_host == host:
            return path
    raise RuntimeError(
        f"No entry for hostname {host!r} in {CLAUDE_CODE_SOURCES_ENV_KEY}. "
        f"Run `python migrations/002_setup_claude_code_archival.py` on this machine."
    )


def validate_source_path(transcript_path: Path) -> None:
    """Ensure the transcript path is under ~/.claude/ to prevent path traversal."""
    try:
        transcript_path.resolve().relative_to(CLAUDE_DIR.resolve())
    except ValueError:
        raise ValueError(f"Refusing to archive file outside {CLAUDE_DIR}: {transcript_path}")


def get_archive_path(transcript_path: Path, archive_dir: Path) -> Path:
    """Mirror project/session structure under archive_dir.

    Source: ~/.claude/projects/<project-slug>/<session-id>.jsonl
    Dest:   <archive_dir>/<project-slug>/<session-id>.jsonl
    """
    parts = transcript_path.resolve().parts
    try:
        projects_idx = parts.index("projects")
    except ValueError:
        raise ValueError(f"Transcript path has no 'projects' component: {transcript_path}")
    result = (archive_dir / Path(*parts[projects_idx + 1:])).resolve()
    if not result.is_relative_to(archive_dir.resolve()):
        raise ValueError(f"Derived archive path escapes archive directory: {result}")
    return result


def sync_transcript(transcript_path: Path, archive_path: Path) -> int:
    """Append new lines from transcript to archive. Returns number of new lines written."""
    if not transcript_path.exists():
        return 0

    # Cheap shortcut: if the archive exists and is at least as large as the
    # source, there can be no new bytes to append. Skips the read+line-count
    # entirely on every Stop where nothing changed.
    if archive_path.exists():
        try:
            if archive_path.stat().st_size >= transcript_path.stat().st_size:
                return 0
        except OSError:
            pass  # fall through to the full sync path

    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with open(archive_path, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            existing_lines = sum(1 for _ in f)

            source_lines = []
            source_total = 0
            with open(transcript_path, "r", encoding="utf-8") as src:
                for i, line in enumerate(src):
                    if not line.endswith("\n"):
                        # Incomplete line — writer hasn't flushed. Defer to next sync.
                        break
                    source_total = i + 1
                    if i < existing_lines:
                        continue
                    if not line.strip():
                        continue
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        print(
                            f"Warning: skipping corrupt JSONL at line {i+1}: {line[:80]!r}",
                            file=sys.stderr,
                        )
                        continue
                    source_lines.append(line)

            if existing_lines > source_total > 0:
                _log_anomaly(
                    f"TRUNCATION DETECTED: {transcript_path}\n"
                    f"  archive has {existing_lines} lines, "
                    f"source has {source_total} complete lines\n"
                    f"  archive: {archive_path}"
                )

            if source_lines:
                f.seek(0, 2)
                f.writelines(source_lines)

            return len(source_lines)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def sync_directory(scan_root: Path, archive_dir: Path, event: str) -> None:
    """Sync every *.jsonl under scan_root into archive_dir."""
    total_files = 0
    total_lines = 0
    for jsonl in scan_root.rglob("*.jsonl"):
        try:
            validate_source_path(jsonl)
            archive_path = get_archive_path(jsonl, archive_dir)
        except ValueError as e:
            print(f"Skipping {jsonl}: {e}", file=sys.stderr)
            continue
        new_lines = sync_transcript(jsonl, archive_path)
        if new_lines > 0:
            total_files += 1
            total_lines += new_lines
    if total_lines > 0:
        print(
            f"[{event}] Archived {total_lines} new lines across {total_files} file(s) under {scan_root}",
            file=sys.stderr,
        )


def _log_anomaly(message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"[{timestamp}] {message}\n"
    print(f"ANOMALY: {message}", file=sys.stderr)
    try:
        with open(ANOMALY_LOG, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        # Fall back to stderr if the log file can't be written (read-only repo,
        # permissions, missing parent dir, etc.). The ANOMALY line above still
        # carries the message; this just notes the log failure for visibility.
        print(f"  (could not write {ANOMALY_LOG}: {e})", file=sys.stderr)


def main():
    hook_input = json.load(sys.stdin)
    transcript_path = Path(hook_input.get("transcript_path", ""))
    event = hook_input.get("hook_event_name", "unknown")

    try:
        archive_dir = resolve_archive_dir()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

    if event == "SessionEnd":
        scan_root = CLAUDE_PROJECTS_DIR
    else:
        if not transcript_path.exists():
            print(f"Warning: transcript not found: {transcript_path}", file=sys.stderr, flush=True)
            return
        try:
            validate_source_path(transcript_path)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr, flush=True)
            sys.exit(1)
        scan_root = transcript_path.parent

    sync_directory(scan_root, archive_dir, event)


if __name__ == "__main__":
    main()
