"""
Tests for migrations/004_setup_codex_archival.py.

Pure helpers (hooks.json shape, source merging) plus an end-to-end main() run
driven entirely inside tmp dirs: find_repo_root and codex_home are monkeypatched
so the migration writes a temp .env, a temp $CODEX_HOME/hooks.json, and a temp
archive — the real ~/.codex and repo .env are never touched.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))


@pytest.fixture
def mig():
    spec = importlib.util.spec_from_file_location(
        "mig004", REPO / "migrations" / "004_setup_codex_archival.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- pure helpers -----------------------------------------------------------

def test_add_stop_hook_builds_codex_shape(mig):
    config = {}
    mig.add_stop_hook(config, "py codex_sync.py")
    assert config == {
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "py codex_sync.py"}]}]}}


def test_stop_hook_installed_detects_command(mig):
    config = {}
    mig.add_stop_hook(config, "cmd-a")
    assert mig.stop_hook_installed(config, "cmd-a") is True
    assert mig.stop_hook_installed(config, "cmd-b") is False
    assert mig.stop_hook_installed({}, "cmd-a") is False


def test_merged_source_pairs_last_wins(mig):
    text = "CODEX_SOURCES=a=/p1\nCODEX_SOURCES=a=/p2,b=/p3\n"
    assert mig.merged_source_pairs(text) == {"a": "/p2", "b": "/p3"}


# --- end-to-end main() inside tmp dirs --------------------------------------

@pytest.fixture
def staged(mig, tmp_path, monkeypatch):
    """A temp repo root + temp $CODEX_HOME with one real rollout fixture."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # codex_sync.py must be importable by name from the real repo; the migration
    # imports `codex_sync` (module), so add the real repo to the path. find_repo_root
    # is what points .env/archive at the tmp repo.
    codex_dir = tmp_path / "codexhome"
    sessions = codex_dir / "sessions" / "2026" / "06" / "13"
    sessions.mkdir(parents=True)
    fixture = REPO / "tests" / "fixtures" / "sample_codex_session.jsonl"
    (sessions / "rollout-2026-06-13T15-48-28-b19ec125.jsonl").write_bytes(fixture.read_bytes())

    monkeypatch.setattr(mig, "find_repo_root", lambda: repo)
    monkeypatch.setattr(mig, "codex_home", lambda: codex_dir)
    monkeypatch.setattr(sys, "argv", ["mig004", "--yes"])
    return mig, repo, codex_dir


def test_main_installs_hook_env_and_backfills(staged):
    mig, repo, codex_dir = staged
    mig.main()

    # hooks.json registers a Stop hook running codex_sync.py
    hooks = json.loads((codex_dir / "hooks.json").read_text())
    stop = hooks["hooks"]["Stop"]
    cmd = stop[0]["hooks"][0]["command"]
    assert "codex_sync.py" in cmd
    assert stop[0]["hooks"][0]["type"] == "command"

    # .env got a CODEX_SOURCES entry and the shared MACHINE_NAME for this host
    env_text = (repo / ".env").read_text()
    assert "CODEX_SOURCES=" in env_text
    assert "MACHINE_NAME=" in env_text

    # backfill mirrored the rollout under the archive (codex/<host>/...sessions tail)
    archived = list((repo / "data" / "llm_data" / "codex").rglob("rollout-*.jsonl"))
    assert len(archived) == 1
    assert archived[0].read_bytes() == (
        REPO / "tests" / "fixtures" / "sample_codex_session.jsonl").read_bytes()


def test_main_migrates_legacy_host_key(staged):
    # A pre-rename .env carrying CLAUDE_CODE_HOST is rewritten to MACHINE_NAME in
    # place, and the carried-over name keys CODEX_SOURCES.
    mig, repo, codex_dir = staged
    (repo / ".env").write_text("CLAUDE_CODE_HOST=mybox\n")

    mig.main()

    env_text = (repo / ".env").read_text()
    assert "MACHINE_NAME=mybox" in env_text
    assert "CLAUDE_CODE_HOST" not in env_text
    assert "CODEX_SOURCES=mybox=" in env_text


def test_main_is_idempotent(staged):
    mig, repo, codex_dir = staged
    mig.main()
    hooks_after_first = (codex_dir / "hooks.json").read_text()
    # Second run: hook already installed, env unchanged, archive present → no dup
    with pytest.raises(SystemExit) as exc:
        mig.main()
    assert exc.value.code == 0
    hooks = json.loads((codex_dir / "hooks.json").read_text())
    assert len(hooks["hooks"]["Stop"]) == 1  # not duplicated
