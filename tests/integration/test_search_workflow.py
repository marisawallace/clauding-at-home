"""
Integration tests for search workflow (full_text_search_chats_archive.py).

These tests exercise the search functionality with real data.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_search_exact_phrase_match(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test searching for an exact phrase in conversations."""
    # Setup: Import conversations first
    zip_dest = isolated_workspace / "data-2025-01-05.zip"
    shutil.copy(sample_claude_export, zip_dest)

    sync_result = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--claude"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_result.returncode == 0, "Setup sync failed"

    # Execute: Search for phrase that exists in test data
    result = subprocess.run(
        [sys.executable, str(repo_root / "full_text_search_chats_archive.py"), "Python function"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nSearch STDOUT:\n{result.stdout}")
    print(f"\nSearch STDERR:\n{result.stderr}")

    # Verify: Search succeeded
    assert result.returncode == 0, f"Search failed: {result.stderr}"

    # Verify: Output contains expected conversation
    assert "Test Conversation 1" in result.stdout, "Expected conversation not in results"
    assert "Python" in result.stdout, "Search term not highlighted in results"


@pytest.mark.integration
def test_search_json_output(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test search with JSON output format."""
    # Setup: Import conversations
    zip_dest = isolated_workspace / "data-2025-01-05.zip"
    shutil.copy(sample_claude_export, zip_dest)

    sync_result = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--claude"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_result.returncode == 0

    # Execute: Search with JSON output
    result = subprocess.run(
        [sys.executable, str(repo_root / "full_text_search_chats_archive.py"), "integration testing", "-j"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nJSON Search STDOUT:\n{result.stdout}")

    assert result.returncode == 0, f"Search failed: {result.stderr}"

    # Verify: Output is valid JSON
    try:
        search_results = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Output is not valid JSON: {e}\nOutput: {result.stdout}")

    # Verify: Results have expected structure
    assert isinstance(search_results, list), "JSON output should be a list"
    assert len(search_results) > 0, "Should have at least one result"

    # Verify: Each result has required fields
    first_result = search_results[0]
    assert "uuid" in first_result
    assert "name" in first_result
    assert "total_score" in first_result  # Field is actually called total_score
    assert "matches" in first_result
    assert "type" in first_result  # Field is actually called type (not provider)

    # Verify: Correct conversation found
    result_uuids = {r["uuid"] for r in search_results}
    assert "conv-uuid-002" in result_uuids, "Integration Testing conversation should be found"


@pytest.mark.integration
def test_search_cross_provider(isolated_workspace, sample_claude_export, sample_chatgpt_export,
                                test_env_file, repo_root):
    """Test searching across both Claude and ChatGPT conversations."""
    # Setup: Import both Claude and ChatGPT conversations
    claude_zip = isolated_workspace / "data-2025-01-05.zip"
    shutil.copy(sample_claude_export, claude_zip)

    chatgpt_zip = isolated_workspace / sample_chatgpt_export.name
    shutil.copy(sample_chatgpt_export, chatgpt_zip)

    # Sync Claude
    sync_claude = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--claude"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_claude.returncode == 0

    # Sync ChatGPT
    sync_chatgpt = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--chatgpt"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_chatgpt.returncode == 0

    # Execute: Search for term that appears in ChatGPT conversation
    result = subprocess.run(
        [sys.executable, str(repo_root / "full_text_search_chats_archive.py"), "ChatGPT", "-j"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nCross-provider search:\n{result.stdout}")

    assert result.returncode == 0

    # Verify: Results include ChatGPT conversation
    search_results = json.loads(result.stdout)
    # Note: Search results include a filepath which contains the provider name
    # Extract provider from filepath or check the type field
    providers = set()
    for r in search_results:
        filepath = r.get("filepath", "")
        if "/claude/" in filepath:
            providers.add("claude")
        elif "/chatgpt/" in filepath:
            providers.add("chatgpt")

    assert "chatgpt" in providers, "ChatGPT results should be included"

    # Verify: Can find ChatGPT conversation
    chatgpt_results = [r for r in search_results if "/chatgpt/" in r.get("filepath", "")]
    assert len(chatgpt_results) > 0, "Should find ChatGPT conversations"


@pytest.mark.integration
def test_search_no_results(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test search with query that has no matches."""
    # Setup: Import conversations
    zip_dest = isolated_workspace / "data-2025-01-05.zip"
    shutil.copy(sample_claude_export, zip_dest)

    sync_result = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--claude"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_result.returncode == 0

    # Execute: Search for non-existent term
    result = subprocess.run(
        [sys.executable, str(repo_root / "full_text_search_chats_archive.py"),
         "xyzabc123nonexistentterm"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nNo results search:\n{result.stdout}")

    # Verify: Returns 0 (success) even with no results
    assert result.returncode == 0

    # Verify: Output indicates no results
    assert "0 results" in result.stdout.lower() or "no results" in result.stdout.lower() or result.stdout.strip() == ""


@pytest.mark.integration
def test_search_scoring_accuracy(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test that search scoring ranks results correctly."""
    # Setup: Import conversations
    zip_dest = isolated_workspace / "data-2025-01-05.zip"
    shutil.copy(sample_claude_export, zip_dest)

    sync_result = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--claude"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_result.returncode == 0

    # Execute: Search with JSON to get scores
    result = subprocess.run(
        [sys.executable, str(repo_root / "full_text_search_chats_archive.py"),
         "integration testing", "-j"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0

    search_results = json.loads(result.stdout)

    # Verify: Results are sorted by score (descending)
    scores = [r["total_score"] for r in search_results]
    assert scores == sorted(scores, reverse=True), "Results should be sorted by score descending"

    # Verify: Conversation with "integration testing" in title has highest score
    top_result = search_results[0]
    assert "Integration Testing" in top_result["name"], \
        "Conversation with search term in title should rank highest"
