"""
Integration tests for OpenAI Codex search functionality.

Mirrors test_claude_code_search.py: drives full_text_search_chats_archive.py as a
subprocess against a workspace-local CODEX_SOURCES archive, so the whole index →
rescore → render path is exercised end to end.
"""
import json
import shutil
from pathlib import Path

import pytest

# The committed no-tools fixture: session id + a typed prompt to search for.
SESSION_ID = "b19ec125-978e-7f30-8b5b-61448a2fc5d7"
ROLLOUT_NAME = f"rollout-2026-06-13T15-48-28-{SESSION_ID}.jsonl"


@pytest.fixture
def codex_workspace(isolated_workspace):
    """A workspace whose CODEX_SOURCES archive holds one real rollout fixture."""
    codex_dir = isolated_workspace / "codex_data"
    day = codex_dir / "2026" / "06" / "13"
    day.mkdir(parents=True)
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_codex_session.jsonl"
    shutil.copy(fixture, day / ROLLOUT_NAME)

    (isolated_workspace / ".env").write_text(
        f"CODEX_SOURCES=testhost={codex_dir}\n"
        f"MACHINE_NAME=testhost\n"
        f"LLM_DATA_DIR={isolated_workspace / 'data' / 'llm_data'}\n"
        f"LOCAL_VIEWS_DIR={isolated_workspace / 'data' / 'local_views'}\n"
        f"SEARCH_INDEX_DB={isolated_workspace / 'search_index.db'}\n"
    )
    return isolated_workspace


def _write_codex_rollout(path: Path, session_id: str, cwd: str, created_at: str, text: str):
    """Write a minimal valid Codex rollout (session_meta + turn_context + a turn)."""
    lines = [
        {"timestamp": created_at, "type": "session_meta",
         "payload": {"id": session_id, "timestamp": created_at, "cwd": cwd,
                     "cli_version": "0.133.0"}},
        {"timestamp": created_at, "type": "turn_context",
         "payload": {"model": "gpt-5.5", "cwd": cwd}},
        {"timestamp": created_at, "type": "event_msg",
         "payload": {"type": "user_message", "message": text}},
        {"timestamp": created_at, "type": "event_msg",
         "payload": {"type": "agent_message", "message": "ok", "phase": "final_answer"}},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")


@pytest.mark.integration
def test_search_codex_only(codex_workspace, run_cli):
    result = run_cli(
        "full_text_search_chats_archive.py", "Reply", "-s", "codex",
        config=codex_workspace / ".env",
    )
    assert result.returncode == 0, result.stderr
    assert "Found" in result.stdout
    assert "CODEX" in result.stdout


@pytest.mark.integration
def test_search_codex_json_output(codex_workspace, run_cli):
    result = run_cli(
        "full_text_search_chats_archive.py", "Reply", "-s", "codex", "-j",
        config=codex_workspace / ".env",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert len(data) == 1
    entry = data[0]
    assert entry["provider"] == "codex"
    assert entry["uuid"] == SESSION_ID
    assert entry["extra"].get("host") == "testhost"
    assert entry["extra"].get("cwd") == "/tmp/codex-resume-test"
    assert "codex resume" in entry["url"]
    assert "[testhost]" in entry["url"]


@pytest.mark.integration
def test_search_codex_resume_command(codex_workspace, run_cli):
    result = run_cli(
        "full_text_search_chats_archive.py", "Reply", "-s", "codex",
        config=codex_workspace / ".env",
    )
    assert result.returncode == 0, result.stderr
    assert f"pushd /tmp/codex-resume-test && codex resume {SESSION_ID}" in result.stdout


@pytest.mark.integration
def test_search_source_all_includes_codex(codex_workspace, run_cli):
    result = run_cli(
        "full_text_search_chats_archive.py", "Reply",
        config=codex_workspace / ".env",
    )
    assert result.returncode == 0, result.stderr
    assert "CODEX" in result.stdout


@pytest.mark.integration
def test_search_source_llm_excludes_codex(codex_workspace, run_cli):
    result = run_cli(
        "full_text_search_chats_archive.py", "Reply", "-s", "llm",
        config=codex_workspace / ".env",
    )
    assert result.returncode == 0, result.stderr
    assert "CODEX" not in result.stdout


@pytest.mark.integration
def test_search_no_codex_dir_configured(isolated_workspace, run_cli):
    env_path = isolated_workspace / ".env"
    env_path.write_text(
        f"LLM_DATA_DIR={isolated_workspace / 'data' / 'llm_data'}\n"
        f"SEARCH_INDEX_DB={isolated_workspace / 'search_index.db'}\n"
    )
    result = run_cli(
        "full_text_search_chats_archive.py", "test", "-s", "codex",
        config=env_path,
    )
    assert result.returncode != 0
    assert "not configured" in result.stderr


@pytest.mark.integration
def test_verify_codex_index_matches_scan(codex_workspace, run_cli):
    """--verify proves the index path and the full scan agree for codex."""
    result = run_cli(
        "full_text_search_chats_archive.py", "Reply", "-s", "codex", "--verify",
        config=codex_workspace / ".env",
    )
    assert result.returncode == 0, result.stderr
    assert "VERIFY OK" in result.stdout


@pytest.mark.integration
def test_search_here_includes_codex(isolated_workspace, run_cli, tmp_path):
    """--here scopes to this dir's local-CLI sessions, including codex."""
    codex_dir = isolated_workspace / "codex_data"
    run_dir = tmp_path / "workdir"
    run_dir.mkdir()
    _write_codex_rollout(
        codex_dir / "2026" / "06" / "13" / "rollout-2026-06-13T10-00-00-here-codex-1.jsonl",
        "here-codex-1", str(run_dir), "2026-06-13T10:00:00.000Z",
        "widgets and gadgets here")
    (isolated_workspace / ".env").write_text(
        f"CODEX_SOURCES=testhost={codex_dir}\n"
        f"MACHINE_NAME=testhost\n"
        f"LLM_DATA_DIR={isolated_workspace / 'data' / 'llm_data'}\n"
        f"SEARCH_INDEX_DB={isolated_workspace / 'search_index.db'}\n"
    )
    result = run_cli(
        "full_text_search_chats_archive.py", "--here", "-j",
        config=isolated_workspace / ".env", cwd=run_dir,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert [e["uuid"] for e in data] == ["here-codex-1"]
    assert data[0]["provider"] == "codex"


@pytest.mark.integration
def test_search_here_honors_legacy_host_key(isolated_workspace, run_cli, tmp_path):
    """Zero-effort upgrade: an old .env with only CLAUDE_CODE_HOST (no
    MACHINE_NAME) still resolves the current host, so --here keeps matching
    after pulling the rename without re-running any migration."""
    codex_dir = isolated_workspace / "codex_data"
    run_dir = tmp_path / "workdir"
    run_dir.mkdir()
    _write_codex_rollout(
        codex_dir / "2026" / "06" / "13" / "rollout-2026-06-13T10-00-00-legacy-host-1.jsonl",
        "legacy-host-1", str(run_dir), "2026-06-13T10:00:00.000Z",
        "widgets and gadgets here")
    (isolated_workspace / ".env").write_text(
        f"CODEX_SOURCES=testhost={codex_dir}\n"
        f"CLAUDE_CODE_HOST=testhost\n"  # legacy key only — no MACHINE_NAME
        f"LLM_DATA_DIR={isolated_workspace / 'data' / 'llm_data'}\n"
        f"SEARCH_INDEX_DB={isolated_workspace / 'search_index.db'}\n"
    )
    result = run_cli(
        "full_text_search_chats_archive.py", "--here", "-j",
        config=isolated_workspace / ".env", cwd=run_dir,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert [e["uuid"] for e in data] == ["legacy-host-1"]
    assert data[0]["extra"].get("host") == "testhost"
