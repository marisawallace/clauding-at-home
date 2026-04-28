"""
Default directory paths relative to the repository root.

All data lives under data/ so that the entire data/ folder can be
synced as a single unit (e.g. with MEGA, Syncthing, or similar).

  data/
    llm_data/           - organized chat archives (claude/, chatgpt/, etc.)
    archived_exports/   - processed export zip files
    local_views/        - generated Markdown/HTML conversation views

Any of these can be overridden via .env:
  DATA_DIR=/absolute/path/to/llm_data
  ARCHIVED_EXPORTS_DIR=/absolute/path/to/archived_exports
  LOCAL_VIEWS_DIR=/absolute/path/to/local_views
"""
from pathlib import Path

# Single sync root - everything lives under here
DATA_ROOT = Path("data")

# Subdirectories under DATA_ROOT
LLM_DATA_SUBDIR = DATA_ROOT / "llm_data"
ARCHIVED_EXPORTS_SUBDIR = DATA_ROOT / "archived_exports"
LOCAL_VIEWS_SUBDIR = DATA_ROOT / "local_views"

# External data sources for Claude Code conversations (JSONL archives).
# Configured via CLAUDE_CODE_SOURCES in .env as comma-separated host=path
# pairs, e.g. "laptop=~/syncs/cc/laptop,desktop=~/syncs/cc/desktop". Each
# path points at a per-machine ~/.claude/projects/ tree synced into a shared
# location. The host label is stamped onto search results so the resume
# command can be attributed to the originating machine.
CLAUDE_CODE_SOURCES_ENV_KEY = "CLAUDE_CODE_SOURCES"


def parse_claude_code_sources(config: dict) -> list[tuple[str, Path]]:
    """Return list of (hostname, path) tuples parsed from CLAUDE_CODE_SOURCES.

    Returns [] if the var is unset or empty.
    """
    raw = config.get(CLAUDE_CODE_SOURCES_ENV_KEY, "").strip()
    if not raw:
        return []

    sources: list[tuple[str, Path]] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(
                f"{CLAUDE_CODE_SOURCES_ENV_KEY} entry {entry!r} is missing '=': "
                f"expected 'host=path'"
            )
        host, path = entry.split("=", 1)
        host = host.strip()
        path = path.strip()
        if not host or not path:
            raise ValueError(
                f"{CLAUDE_CODE_SOURCES_ENV_KEY} entry {entry!r} has empty host or path"
            )
        sources.append((host, Path(path).expanduser()))
    return sources
