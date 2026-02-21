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
