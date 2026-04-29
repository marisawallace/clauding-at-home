#!/usr/bin/env python3
"""
Migration 002: Set up Claude Code session archival.

Wires the in-repo `claude_code_hook.py` into Claude Code so every Stop /
SessionEnd event reconciles ~/.claude/projects/ JSONLs into a per-host
archive that the search/view tools index.

What it does:
  1. Adds Stop + SessionEnd hooks to ~/.claude/settings.json (with backup)
  2. Upserts CLAUDE_CODE_SOURCES=<hostname>=<archive-path> in .env
  3. Creates data/llm_data/claude-code/<hostname>/

Usage:
  python3 migrations/002_setup_claude_code_archival.py
  python3 migrations/002_setup_claude_code_archival.py --yes   # skip prompt

To uninstall: delete the Stop and SessionEnd entries pointing at
claude_code_hook.py in ~/.claude/settings.json, and unset
CLAUDE_CODE_SOURCES in .env.
"""

import argparse
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

# ANSI colors (match migration 001)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

REPO_MARKER = "claude_code_hook.py"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def find_repo_root() -> Path | None:
    """Find the repo root by looking for claude_code_hook.py."""
    candidate = Path(__file__).resolve().parent
    for _ in range(4):
        if (candidate / REPO_MARKER).exists():
            return candidate
        candidate = candidate.parent
    return None


def hook_command(repo_root: Path) -> str:
    return f"python3 {repo_root / REPO_MARKER}"


def settings_already_installed(settings: dict, command: str) -> tuple[bool, bool]:
    """Return (stop_installed, sessionend_installed)."""

    def has_command(event: str) -> bool:
        for matcher in settings.get("hooks", {}).get(event, []):
            for h in matcher.get("hooks", []):
                if h.get("type") == "command" and h.get("command") == command:
                    return True
        return False

    return has_command("Stop"), has_command("SessionEnd")


def add_hook(settings: dict, event: str, command: str) -> None:
    hooks_section = settings.setdefault("hooks", {})
    event_list = hooks_section.setdefault(event, [])
    event_list.append({"hooks": [{"type": "command", "command": command}]})


def parse_sources_value(raw: str) -> list[tuple[str, str]]:
    """Parse a raw CLAUDE_CODE_SOURCES value into [(host, path), ...]."""
    out = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        host, path = entry.split("=", 1)
        out.append((host.strip(), path.strip()))
    return out


def serialize_sources(pairs: list[tuple[str, str]]) -> str:
    return ",".join(f"{h}={p}" for h, p in pairs)


def upsert_env_sources(env_path: Path, hostname: str, archive_path: str) -> str:
    """
    Add or update the entry for hostname in CLAUDE_CODE_SOURCES.
    Returns one of: "added", "updated", "unchanged".
    """
    existing_lines = env_path.read_text().splitlines() if env_path.exists() else []
    new_lines = []
    found = False
    status = "added"

    for line in existing_lines:
        stripped = line.strip()
        if stripped.startswith("CLAUDE_CODE_SOURCES=") or stripped.startswith(
            "#CLAUDE_CODE_SOURCES="
        ):
            found = True
            # Re-parse value (strip leading '#' if commented out)
            raw_value = stripped.split("=", 1)[1] if "=" in stripped else ""
            pairs = parse_sources_value(raw_value)
            host_to_path = {h: p for h, p in pairs}

            if host_to_path.get(hostname) == archive_path and not stripped.startswith("#"):
                status = "unchanged"
                new_lines.append(line)
                continue

            host_to_path[hostname] = archive_path
            new_pairs = [(h, host_to_path[h]) for h in host_to_path]
            new_lines.append(f"CLAUDE_CODE_SOURCES={serialize_sources(new_pairs)}")
            status = "updated" if not stripped.startswith("#") else "added"
        else:
            new_lines.append(line)

    if not found:
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        new_lines.append(f"CLAUDE_CODE_SOURCES={hostname}={archive_path}")

    env_path.write_text("\n".join(new_lines) + "\n")
    return status


def main():
    parser = argparse.ArgumentParser(
        description="Migration 002: Set up Claude Code session archival",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Migration 002: Claude Code session archival{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    repo_root = find_repo_root()
    if repo_root is None:
        print(f"{RED}ERROR: Could not find clauding-at-home repo root.{RESET}")
        print(f"  Looked for {REPO_MARKER} starting from {Path(__file__).resolve().parent}.")
        sys.exit(1)

    hostname = socket.gethostname()
    archive_dir = repo_root / "data" / "llm_data" / "claude-code" / hostname
    command = hook_command(repo_root)
    env_path = repo_root / ".env"

    print(f"  Repository root:  {CYAN}{repo_root}{RESET}")
    print(f"  Hostname:         {CYAN}{hostname}{RESET}")
    print(f"  Archive path:     {CYAN}{archive_dir}{RESET}")
    print(f"  Hook command:     {CYAN}{command}{RESET}")
    print(f"  Settings file:    {CYAN}{SETTINGS_PATH}{RESET}")
    print(f"  .env file:        {CYAN}{env_path}{RESET}")

    # Load (or initialize) settings.json
    if SETTINGS_PATH.exists():
        try:
            settings = json.loads(SETTINGS_PATH.read_text())
        except json.JSONDecodeError as e:
            print(f"\n{RED}ERROR: {SETTINGS_PATH} is not valid JSON: {e}{RESET}")
            print("  Fix it manually before re-running this migration.")
            sys.exit(1)
    else:
        settings = {}

    stop_done, send_done = settings_already_installed(settings, command)

    print(f"\n{BOLD}Planned changes:{RESET}")
    settings_changes_needed = not (stop_done and send_done)
    if stop_done:
        print(f"  {DIM}Stop hook already installed — skip{RESET}")
    else:
        print(f"  {GREEN}+{RESET} Add Stop hook → {command}")
    if send_done:
        print(f"  {DIM}SessionEnd hook already installed — skip{RESET}")
    else:
        print(f"  {GREEN}+{RESET} Add SessionEnd hook → {command}")

    # Compute env change preview without writing
    raw_existing = ""
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            s = line.strip()
            if s.startswith("CLAUDE_CODE_SOURCES="):
                raw_existing = s.split("=", 1)[1]
                break
    existing_pairs = dict(parse_sources_value(raw_existing))
    if existing_pairs.get(hostname) == str(archive_dir):
        env_action = "unchanged"
        print(f"  {DIM}.env CLAUDE_CODE_SOURCES already has {hostname}={archive_dir} — skip{RESET}")
    elif hostname in existing_pairs:
        env_action = "update"
        print(
            f"  {YELLOW}~{RESET} .env CLAUDE_CODE_SOURCES[{hostname}]: "
            f"{existing_pairs[hostname]} → {archive_dir}"
        )
    elif raw_existing:
        env_action = "append"
        print(f"  {GREEN}+{RESET} .env CLAUDE_CODE_SOURCES: append {hostname}={archive_dir}")
    else:
        env_action = "create"
        print(f"  {GREEN}+{RESET} .env CLAUDE_CODE_SOURCES={hostname}={archive_dir}")

    archive_dir_exists = archive_dir.exists()
    if archive_dir_exists:
        print(f"  {DIM}Archive dir already exists — skip mkdir{RESET}")
    else:
        print(f"  {GREEN}+{RESET} mkdir -p {archive_dir}")

    if not settings_changes_needed and env_action == "unchanged" and archive_dir_exists:
        print(f"\n{GREEN}✓ Already installed — nothing to do.{RESET}\n")
        sys.exit(0)

    if not args.yes:
        print(f"\n{YELLOW}This will modify {SETTINGS_PATH} and {env_path}.{RESET}")
        print(f"{YELLOW}A timestamped backup of settings.json will be made before writing.{RESET}")
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    print(f"\n{BOLD}Applying...{RESET}")

    # 1. settings.json
    if settings_changes_needed:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        if SETTINGS_PATH.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = SETTINGS_PATH.with_suffix(f".json.bak.{ts}")
            backup.write_text(SETTINGS_PATH.read_text())
            print(f"  {GREEN}✓{RESET} Backed up settings.json → {backup.name}")

        if not stop_done:
            add_hook(settings, "Stop", command)
        if not send_done:
            add_hook(settings, "SessionEnd", command)
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")
        print(f"  {GREEN}✓{RESET} Updated {SETTINGS_PATH}")

    # 2. .env
    if env_action != "unchanged":
        env_path.touch(exist_ok=True)
        result = upsert_env_sources(env_path, hostname, str(archive_dir))
        print(f"  {GREEN}✓{RESET} .env CLAUDE_CODE_SOURCES: {result}")

    # 3. archive dir
    if not archive_dir_exists:
        archive_dir.mkdir(parents=True, exist_ok=True)
        print(f"  {GREEN}✓{RESET} Created {archive_dir}")

    # Done
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{GREEN}{BOLD}  Setup complete!{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"""
  How it works:
    Every time a Claude Code session ends (Stop or SessionEnd), the hook
    reconciles ~/.claude/projects/*.jsonl into:

      {CYAN}{archive_dir}{RESET}

    {BOLD}Stop{RESET}        — scans the current session's project dir.
                  Catches the parent session and any subagent transcripts.
    {BOLD}SessionEnd{RESET}  — full sweep of ~/.claude/projects/.
                  Backfills anything missed (crashed sessions, etc.).

    The sync is append-only and idempotent: it line-count compares the
    archive against the source and writes only the new tail.

    {BOLD}Assumption:{RESET} Claude Code JSONL transcripts are immutable append-only
    logs. If that ever changes, archives could diverge — the script writes
    to {CYAN}claude_code_anomalies.log{RESET} as a canary.

  {BOLD}Verify it's working:{RESET}
    1. Open and exit any Claude Code session.
       (On the first SessionEnd, all your existing on-disk history will
       backfill into the archive in one sweep — no manual import step.)
    2. {CYAN}python3 full_text_search_chats_archive.py <some query>{RESET}
       Results from this machine will be tagged with hostname {CYAN}{hostname}{RESET}.

  {BOLD}To uninstall:{RESET}
    Delete the Stop and SessionEnd entries pointing at {REPO_MARKER}
    in {SETTINGS_PATH}, and unset CLAUDE_CODE_SOURCES in .env.
""")


if __name__ == "__main__":
    main()
