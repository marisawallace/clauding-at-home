#!/usr/bin/env python3
"""
Migration 001: Consolidate data directories under data/

Before:
  clauding-at-home/
    data/               <- chat archives (claude/, chatgpt/, ...)
    archived_exports/   <- processed export zips
    local_views/        <- generated markdown/html views

After:
  clauding-at-home/
    data/
      llm_data/         <- chat archives (was: data/)
      archived_exports/ <- processed export zips (was: archived_exports/)
      local_views/      <- generated markdown/html views (was: local_views/)

Why: Consolidating into a single data/ folder makes it easy to sync
everything with a single MEGA (or Syncthing, etc.) sync pair, while
keeping the .git directory untouched.

Usage:
  python3 migrations/001_consolidate_data_dirs.py
  python3 migrations/001_consolidate_data_dirs.py --yes   # skip confirmation
"""

import argparse
import shutil
import sys
from pathlib import Path


# ANSI colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def find_repo_root() -> Path:
    """
    Find the repository root by looking for sync_local_chats_archive.py.
    Searches the current directory and up to 3 parent directories.
    """
    marker = "sync_local_chats_archive.py"
    candidate = Path.cwd()
    for _ in range(4):
        if (candidate / marker).exists():
            return candidate
        candidate = candidate.parent
    return None


def check_already_migrated(repo_root: Path) -> bool:
    """Return True if the migration appears to have already been run."""
    llm_data = repo_root / "data" / "llm_data"
    old_archived = repo_root / "archived_exports"
    old_local_views = repo_root / "local_views"

    # Already migrated if llm_data exists and old top-level dirs are gone
    return (
        llm_data.exists()
        and not old_archived.exists()
        and not old_local_views.exists()
    )


def list_dir_contents(path: Path, indent: str = "  ") -> list[str]:
    """Return a list of lines describing the directory contents (one level deep)."""
    lines = []
    if not path.exists():
        return lines
    for item in sorted(path.iterdir()):
        label = "/" if item.is_dir() else ""
        lines.append(f"{indent}{item.name}{label}")
    return lines


def move_dir(src: Path, dst: Path, label: str) -> bool:
    """
    Move src to dst. dst must not already exist.
    Returns True on success, False on failure.
    """
    if not src.exists():
        print(f"  {DIM}(skipping {label}: {src.name}/ does not exist){RESET}")
        return True

    if dst.exists():
        print(f"  {RED}ERROR: Destination already exists: {dst}{RESET}")
        print(f"  {RED}       Cannot move {src} → {dst}{RESET}")
        return False

    try:
        shutil.move(str(src), str(dst))
        print(f"  {GREEN}✓{RESET} {label}")
        print(f"    {DIM}{src}{RESET}")
        print(f"    {DIM}→ {dst}{RESET}")
        return True
    except Exception as e:
        print(f"  {RED}✗ Failed to move {label}: {e}{RESET}")
        return False


def move_data_contents(data_dir: Path, llm_data_dir: Path) -> bool:
    """
    Move all subdirectories from data/ into data/llm_data/,
    skipping llm_data/, archived_exports/, and local_views/ themselves.
    Returns True on success.
    """
    skip_names = {"llm_data", "archived_exports", "local_views"}
    items_to_move = [
        item for item in sorted(data_dir.iterdir())
        if item.is_dir() and item.name not in skip_names
    ]

    if not items_to_move:
        print(f"  {DIM}(data/ has no subdirectories to move into llm_data/){RESET}")
        return True

    all_ok = True
    for item in items_to_move:
        dst = llm_data_dir / item.name
        ok = move_dir(item, dst, f"data/{item.name}/ → data/llm_data/{item.name}/")
        if not ok:
            all_ok = False
    return all_ok


def update_env_file(repo_root: Path) -> None:
    """
    If .env exists and has DATA_DIR, ARCHIVED_EXPORTS_DIR, or LOCAL_VIEWS_DIR
    pointing to the old locations, update them and report what changed.
    """
    env_path = repo_root / ".env"
    if not env_path.exists():
        return

    old_lines = env_path.read_text().splitlines()
    new_lines = []
    changes = []

    for line in old_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Detect if this points to a path ending in the old directory name
        if key == "DATA_DIR" and value and not value.endswith("/llm_data"):
            new_value = value.rstrip("/") + "/llm_data"
            new_lines.append(f"{key}={new_value}")
            changes.append(f"  DATA_DIR: {value} → {new_value}")
        elif key == "ARCHIVED_EXPORTS_DIR" and value:
            # Already under data/? Skip.
            if "/data/" not in value and not value.endswith("/data/archived_exports"):
                # Best guess: replace old archived_exports path with data/archived_exports
                # If it ends in /archived_exports, update to /data/archived_exports
                if value.endswith("/archived_exports"):
                    new_value = value[: -len("archived_exports")] + "data/archived_exports"
                    new_lines.append(f"{key}={new_value}")
                    changes.append(f"  ARCHIVED_EXPORTS_DIR: {value} → {new_value}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        elif key == "LOCAL_VIEWS_DIR" and value:
            if "/data/" not in value and not value.endswith("/data/local_views"):
                if value.endswith("/local_views"):
                    new_value = value[: -len("local_views")] + "data/local_views"
                    new_lines.append(f"{key}={new_value}")
                    changes.append(f"  LOCAL_VIEWS_DIR: {value} → {new_value}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if changes:
        env_path.write_text("\n".join(new_lines) + "\n")
        print(f"\n  {CYAN}Updated .env:{RESET}")
        for change in changes:
            print(f"  {GREEN}✓{RESET}{change}")
    else:
        print(f"\n  {DIM}.env found but no path updates were needed{RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Migration 001: Consolidate data directories under data/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and proceed immediately",
    )
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Migration 001: Consolidate data directories{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    # --- Find repo root ---
    repo_root = find_repo_root()
    if repo_root is None:
        print(f"{RED}ERROR: Could not find the clauding-at-home repository root.{RESET}")
        print("Run this script from inside the repository directory.")
        sys.exit(1)

    print(f"  Repository root: {CYAN}{repo_root}{RESET}\n")

    # --- Check if already migrated ---
    if check_already_migrated(repo_root):
        print(f"{GREEN}✓ Already migrated!{RESET}")
        print("  data/llm_data/ exists and old top-level dirs are gone.")
        print("  Nothing to do.\n")
        sys.exit(0)

    # --- Show current state ---
    data_dir = repo_root / "data"
    archived_exports_dir = repo_root / "archived_exports"
    local_views_dir = repo_root / "local_views"

    print(f"{BOLD}Current state:{RESET}")
    for path in [data_dir, archived_exports_dir, local_views_dir]:
        status = f"{GREEN}exists{RESET}" if path.exists() else f"{DIM}not found{RESET}"
        print(f"  {path.name}/  [{status}]")
        if path.exists():
            contents = list_dir_contents(path)
            for line in contents[:5]:
                print(line)
            if len(contents) > 5:
                print(f"  ... and {len(contents) - 5} more")

    # --- Show migration plan ---
    print(f"\n{BOLD}This migration will:{RESET}")
    print(f"  1. Create          {CYAN}data/llm_data/{RESET}")

    if data_dir.exists():
        subdirs = [
            item.name for item in sorted(data_dir.iterdir())
            if item.is_dir() and item.name not in {"llm_data", "archived_exports", "local_views"}
        ]
        for name in subdirs:
            print(f"  2. Move            {CYAN}data/{name}/  →  data/llm_data/{name}/{RESET}")
    else:
        print(f"  2. {DIM}(data/ not found, nothing to move into llm_data/){RESET}")

    step = 3
    if archived_exports_dir.exists():
        print(f"  {step}. Move            {CYAN}archived_exports/  →  data/archived_exports/{RESET}")
        step += 1
    else:
        print(f"  {step}. {DIM}(archived_exports/ not found, will skip){RESET}")
        step += 1

    if local_views_dir.exists():
        print(f"  {step}. Move            {CYAN}local_views/  →  data/local_views/{RESET}")
        step += 1
    else:
        print(f"  {step}. {DIM}(local_views/ not found, will skip){RESET}")
        step += 1

    print(f"  {step}. Update .env paths (if .env exists)")

    # --- Confirmation ---
    if not args.yes:
        print(f"\n{YELLOW}This will move your data files. Make sure you have a backup.{RESET}")
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    print(f"\n{BOLD}Running migration...{RESET}\n")

    # --- Step 1: Create data/llm_data/ ---
    llm_data_dir = data_dir / "llm_data"
    data_dir.mkdir(exist_ok=True)
    llm_data_dir.mkdir(exist_ok=True)
    print(f"  {GREEN}✓{RESET} Created data/llm_data/")

    # --- Step 2: Move data/ contents into data/llm_data/ ---
    ok = move_data_contents(data_dir, llm_data_dir)
    if not ok:
        print(f"\n{RED}Migration failed during data/ contents move. No data was lost.{RESET}")
        sys.exit(1)

    # --- Step 3: Move archived_exports/ → data/archived_exports/ ---
    ok = move_dir(
        archived_exports_dir,
        data_dir / "archived_exports",
        "archived_exports/ → data/archived_exports/",
    )
    if not ok:
        print(f"\n{RED}Migration failed during archived_exports/ move.{RESET}")
        sys.exit(1)

    # --- Step 4: Move local_views/ → data/local_views/ ---
    ok = move_dir(
        local_views_dir,
        data_dir / "local_views",
        "local_views/ → data/local_views/",
    )
    if not ok:
        print(f"\n{RED}Migration failed during local_views/ move.{RESET}")
        sys.exit(1)

    # --- Step 5: Update .env ---
    update_env_file(repo_root)

    # --- Done ---
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{GREEN}{BOLD}  Migration complete!{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"""
  New structure:
    data/
      llm_data/           ← your chat archives
      archived_exports/   ← processed export zips
      local_views/        ← generated markdown/html views

  {CYAN}If you wish, you can now sync your data/{RESET} folder with MEGA or your preferred tool.
  Your .git directory is untouched and safe.

  If you have shell aliases pointing to old paths, update them.
  Run the test suite to verify everything works:

    pytest
""")


if __name__ == "__main__":
    main()
