"""
Integration tests for view workflow (view_conversation.py).

These tests exercise conversation viewing and format conversion.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_view_markdown_format(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test viewing a conversation in Markdown format."""
    # Setup: Import conversations first
    zip_dest = isolated_workspace / "data-2025-01-05.zip"
    shutil.copy(sample_claude_export, zip_dest)

    sync_result = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--claude"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_result.returncode == 0

    # Execute: View conversation in markdown (without opening editor)
    result = subprocess.run(
        [sys.executable, str(repo_root / "view_conversation.py"),
         "conv-uuid-001", "--format", "markdown", "--no-open"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nView STDOUT:\n{result.stdout}")
    print(f"\nView STDERR:\n{result.stderr}")

    # Verify: Script succeeded
    assert result.returncode == 0, f"View failed: {result.stderr}"

    # Verify: Markdown file was created
    md_file = isolated_workspace / "data/local_views/claude/conv-uuid-001.md"
    assert md_file.exists(), "Markdown file not created"

    # Verify: Markdown content is correct
    md_content = md_file.read_text()
    assert "# Test Conversation 1" in md_content, "Title not in markdown"
    assert "How do I write a Python function?" in md_content, "Human message not in markdown"
    assert "Here's how to write a Python function" in md_content, "Assistant message not in markdown"
    assert "**User**" in md_content or "**Assistant**" in md_content, "Speaker labels not in markdown"


@pytest.mark.integration
def test_view_html_format(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test viewing a conversation in HTML format."""
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

    # Execute: View conversation in HTML format (without opening browser)
    result = subprocess.run(
        [sys.executable, str(repo_root / "view_conversation.py"),
         "conv-uuid-002", "--format", "html", "--no-open"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nView HTML STDOUT:\n{result.stdout}")
    print(f"\nView HTML STDERR:\n{result.stderr}")

    # Verify: Script succeeded
    assert result.returncode == 0, f"View failed: {result.stderr}"

    # Verify: HTML file was created
    html_file = isolated_workspace / "data/local_views/claude/conv-uuid-002.html"
    assert html_file.exists(), "HTML file not created"

    # Verify: HTML content is correct
    html_content = html_file.read_text()
    assert "<html" in html_content.lower(), "Not valid HTML"
    assert "Integration Testing Discussion" in html_content, "Title not in HTML"
    assert "integration testing" in html_content.lower(), "Message content not in HTML"
    assert "<head>" in html_content.lower(), "HTML structure missing"
    assert "<body>" in html_content.lower(), "HTML structure missing"


@pytest.mark.integration
def test_view_nonexistent_conversation(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test viewing a conversation that doesn't exist."""
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

    # Execute: Try to view non-existent conversation
    result = subprocess.run(
        [sys.executable, str(repo_root / "view_conversation.py"),
         "nonexistent-uuid-999", "--no-open"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nNonexistent conversation output:\n{result.stdout}\n{result.stderr}")

    # Verify: Should fail or show error message
    # (Exact behavior depends on implementation)
    assert result.returncode != 0 or "not found" in result.stderr.lower() or "not found" in result.stdout.lower()


@pytest.mark.integration
def test_view_caching(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test that viewing the same conversation twice reuses cached file."""
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

    # Execute: View conversation first time
    result1 = subprocess.run(
        [sys.executable, str(repo_root / "view_conversation.py"),
         "conv-uuid-001", "--format", "markdown", "--no-open"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert result1.returncode == 0

    # Get file modification time
    md_file = isolated_workspace / "data/local_views/claude/conv-uuid-001.md"
    first_mtime = md_file.stat().st_mtime

    # Execute: View same conversation again
    result2 = subprocess.run(
        [sys.executable, str(repo_root / "view_conversation.py"),
         "conv-uuid-001", "--format", "markdown", "--no-open"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert result2.returncode == 0

    # Verify: File modification time hasn't changed (file was reused)
    second_mtime = md_file.stat().st_mtime
    assert first_mtime == second_mtime, "File should be reused, not regenerated"


@pytest.mark.integration
def test_view_project(isolated_workspace, sample_claude_export, repo_root, test_env_file):
    """Test viewing a Claude project."""
    # Setup: Import conversations and projects
    zip_dest = isolated_workspace / "data-2025-01-05.zip"
    shutil.copy(sample_claude_export, zip_dest)

    sync_result = subprocess.run(
        [sys.executable, str(repo_root / "sync_local_chats_archive.py"), "--claude"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )
    assert sync_result.returncode == 0

    # Execute: View project
    result = subprocess.run(
        [sys.executable, str(repo_root / "view_conversation.py"),
         "proj-uuid-001", "--format", "markdown", "--no-open"],
        cwd=isolated_workspace,
        capture_output=True,
        text=True
    )

    print(f"\nView project STDOUT:\n{result.stdout}")

    # Verify: Script succeeded
    assert result.returncode == 0, f"View project failed: {result.stderr}"

    # Verify: Markdown file created
    md_file = isolated_workspace / "data/local_views/claude/proj-uuid-001.md"
    assert md_file.exists(), "Project markdown file not created"

    # Verify: Project content included
    md_content = md_file.read_text()
    assert "Test Project" in md_content, "Project name not in output"
    # Note: Project markdown may or may not include full docs depending on implementation
    # Just verify the basic project info is there
    assert "UUID" in md_content or "Created" in md_content, "Project metadata not in output"
