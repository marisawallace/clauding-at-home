#!/usr/bin/env python3
"""
Full-text search for chat archives.

Searches across all conversations and projects for the specified query,
with colorful terminal output and optional JSON export.
Supports multiple LLM providers (Claude, ChatGPT, etc.).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright variants
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"


@dataclass
class Match:
    """Represents a single match within a conversation/project."""
    text: str
    score: float  # Relevance score


@dataclass
class SearchResult:
    """Represents search results for a single conversation or project."""
    type: str  # "conversation" or "project"
    uuid: str
    name: str
    created_at: str
    email: str
    provider: str  # "claude", "chatgpt", etc.
    filepath: Path
    matches: List[Match]
    total_score: float

    def get_provider_url(self) -> str:
        """Generate provider URL for this item."""
        if self.provider == "claude":
            if self.type == "conversation":
                return f"https://claude.ai/chat/{self.uuid}"
            else:  # project
                return f"https://claude.ai/project/{self.uuid}"
        elif self.provider == "chatgpt":
            # ChatGPT only has conversations, no projects
            return f"https://chatgpt.com/c/{self.uuid}"
        else:
            return f"Unknown provider: {self.provider}"


def score_match(match_text: str, query: str) -> float:
    """
    Calculate relevance score for a match.

    Scoring criteria:
    - Exact phrase match: +10
    - All words present: +5
    - Whole word match (per word): +2
    - Partial word match (per word): +1
    - Match in title/name: +5 (handled in search_item)
    """
    match_lower = match_text.lower()
    query_lower = query.lower()

    score = 0.0

    # Exact phrase match
    if query_lower in match_lower:
        score += 10

    # Check individual words
    query_words = query_lower.split()
    words_found = 0

    for word in query_words:
        # Whole word match
        if re.search(r'\b' + re.escape(word) + r'\b', match_lower):
            score += 2
            words_found += 1
        # Partial match
        elif word in match_lower:
            score += 1
            words_found += 1

    # Bonus if all query words are present
    if words_found == len(query_words) and len(query_words) > 1:
        score += 5

    return score


def extract_text_from_conversation(data: dict) -> List[str]:
    """Extract all text content from a conversation."""
    texts = []

    # Add name and summary
    if data.get("name"):
        texts.append(data["name"])
    if data.get("summary"):
        texts.append(data["summary"])

    # Extract from chat messages
    for msg in data.get("chat_messages", []):
        # Add message text
        if msg.get("text"):
            texts.append(msg["text"])

        # Add content blocks
        for content in msg.get("content", []):
            if content.get("text"):
                texts.append(content["text"])

    return texts


def extract_text_from_project(data: dict) -> List[str]:
    """Extract all text content from a project."""
    texts = []

    # Add name and description
    if data.get("name"):
        texts.append(data["name"])
    if data.get("description"):
        texts.append(data["description"])
    if data.get("prompt_template"):
        texts.append(data["prompt_template"])

    # Extract from docs
    for doc in data.get("docs", []):
        if doc.get("filename"):
            texts.append(doc["filename"])
        if doc.get("content"):
            texts.append(doc["content"])

    return texts


def search_item(filepath: Path, query: str, item_type: str, email: str, provider: str) -> Optional[SearchResult]:
    """
    Search a single conversation or project file.

    Returns SearchResult if matches found, None otherwise.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
        return None

    # Extract text based on type
    if item_type == "conversation":
        texts = extract_text_from_conversation(data)
    else:  # project
        texts = extract_text_from_project(data)

    # Search for query in all texts
    matches: List[Match] = []
    query_lower = query.lower()

    for text in texts:
        if not text:
            continue

        text_lower = text.lower()

        # Check if query matches
        if query_lower in text_lower:
            score = score_match(text, query)

            # Extract context around matches (up to 200 chars)
            # Find all occurrences
            pattern = re.compile(re.escape(query_lower), re.IGNORECASE)
            for match in pattern.finditer(text):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                # Clean up context
                context = context.replace("\n", " ").strip()
                if start > 0:
                    context = "..." + context
                if end < len(text):
                    context = context + "..."

                matches.append(Match(text=context, score=score))

    if not matches:
        return None

    # Calculate total score
    total_score = sum(m.score for m in matches)

    # Bonus score if match in name
    name = data.get("name", "")
    if name and query_lower in name.lower():
        total_score += 5

    return SearchResult(
        type=item_type,
        uuid=data["uuid"],
        name=name if name else "(untitled)",
        created_at=data["created_at"],
        email=email,
        provider=provider,
        filepath=filepath,
        matches=matches,
        total_score=total_score
    )


def search_archive(data_dir: Path, query: str) -> List[SearchResult]:
    """
    Search all conversations and projects in the archive.
    """
    results: List[SearchResult] = []

    # Search each user directory
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        return results

    # Search in both claude/ and chatgpt/ subdirectories
    for provider in ["claude", "chatgpt"]:
        provider_dir = data_dir / provider
        if not provider_dir.exists():
            continue

        for user_dir in provider_dir.iterdir():
            if not user_dir.is_dir():
                continue

            email = user_dir.name

            # Search conversations
            conversations_dir = user_dir / "conversations"
            if conversations_dir.exists():
                for conv_file in conversations_dir.glob("*.json"):
                    result = search_item(conv_file, query, "conversation", email, provider)
                    if result:
                        results.append(result)

            # Search projects
            projects_dir = user_dir / "projects"
            if projects_dir.exists():
                for proj_file in projects_dir.glob("*.json"):
                    result = search_item(proj_file, query, "project", email, provider)
                    if result:
                        results.append(result)

    # The most relevant results should display at the bottom of the list, right
    # above the new terminal prompt.
    results.sort(key=lambda r: -r.total_score)

    return results


def highlight_query(text: str, query: str) -> str:
    """Highlight query matches in text with color."""
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    def replacer(match):
        return f"{Colors.BRIGHT_YELLOW}{Colors.BOLD}{match.group()}{Colors.RESET}"

    return pattern.sub(replacer, text)


def print_results(results: List[SearchResult], query: str):
    """Print search results with colorful formatting."""
    if not results:
        print(f"{Colors.RED}No results found.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{Colors.GREEN}Found {len(results)} result(s){Colors.RESET}\n")

    # Reverse to show best results last (most visible at bottom of terminal)
    results.reverse()
    for i, result in enumerate(results, 1):
        # Header
        type_label = result.type.upper()
        type_color = Colors.BRIGHT_CYAN if result.type == "conversation" else Colors.BRIGHT_MAGENTA

        print(f"{Colors.BOLD}{type_color}[{type_label}]{Colors.RESET} {Colors.BOLD}{result.name}{Colors.RESET}")
        print(f"{Colors.DIM}UUID: {result.uuid}{Colors.RESET}")
        print(f"{Colors.DIM}Created: {result.created_at[:10]} | Account: {result.email}{Colors.RESET}")
        print(f"{Colors.BLUE}{result.get_provider_url()}{Colors.RESET}")
        print(f"{Colors.DIM}Score: {result.total_score:.1f} | Matches: {len(result.matches)}{Colors.RESET}")

        # Show matches (up to 5)
        print()
        for j, match in enumerate(result.matches[:5], 1):
            highlighted = highlight_query(match.text, query)
            print(f"  {Colors.DIM}{j}.{Colors.RESET} {highlighted}")

        if len(result.matches) > 5:
            remaining = len(result.matches) - 5
            print(f"  {Colors.DIM}... and {remaining} more match(es){Colors.RESET}")

        print()

        # Separator
        if i < len(results):
            print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}\n")


def print_json(results: List[SearchResult]):
    """Print results as JSON."""
    output = []
    for result in results:
        output.append({
            "type": result.type,
            "uuid": result.uuid,
            "name": result.name,
            "created_at": result.created_at,
            "email": result.email,
            "url": result.get_provider_url(),
            "filepath": str(result.filepath),
            "total_score": result.total_score,
            "match_count": len(result.matches),
            "matches": [{"text": m.text, "score": m.score} for m in result.matches]
        })

    print(json.dumps(output, indent=2, ensure_ascii=False))


def open_in_editor(results: List[SearchResult], count: int, config: dict):
    """Open top N results in $EDITOR as markdown files."""
    editor = os.environ.get("EDITOR", "vim")

    if count > len(results):
        count = len(results)

    if count == 0:
        print("No results to open.")
        return

    # Import view_conversation functions
    script_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(script_dir))
    try:
        from view_conversation import conversation_to_markdown, get_output_path
    except ImportError as e:
        print(f"Error: Could not import view_conversation: {e}", file=sys.stderr)
        sys.exit(1)

    # Get local_views directory from config
    local_views_dir = Path(config.get("LOCAL_VIEWS_DIR", script_dir / "local_views")).expanduser()
    local_views_dir.mkdir(parents=True, exist_ok=True)

    # Generate markdown files for each result
    # Take the last N results (highest scoring) since print_results() reverses the list
    markdown_files = []
    for result in results[-count:][::-1]:
        # Get output path for markdown file
        md_path = get_output_path(local_views_dir, result.uuid, result.provider, "markdown")

        # Check if markdown file already exists
        if md_path.exists():
            print(f"Using existing markdown: {md_path.name}")
            markdown_files.append(str(md_path))
            continue

        # Load conversation data and convert to markdown
        try:
            with open(result.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Convert to markdown
            markdown_content = conversation_to_markdown(data)

            # Write markdown file
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            print(f"Generated markdown: {md_path.name}")
            markdown_files.append(str(md_path))

        except Exception as e:
            print(f"Warning: Could not convert {result.filepath.name} to markdown: {e}", file=sys.stderr)
            # Fall back to opening the original JSON file
            markdown_files.append(str(result.filepath))

    if not markdown_files:
        print("No files to open.")
        return

    # Open markdown files in editor
    print(f"Opening {len(markdown_files)} file(s) in {editor}...")
    try:
        subprocess.run([editor] + markdown_files)
    except FileNotFoundError:
        print(f"Error: Editor '{editor}' not found. Set $EDITOR to your preferred editor.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error opening editor: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Full-text search for chat archives (Claude, ChatGPT, etc.).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "machine learning"
  %(prog)s "python code" -j > results.json
  %(prog)s "API design" -o 3
        """
    )

    parser.add_argument(
        "query",
        help="Search query (case-insensitive)"
    )

    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output results as JSON"
    )

    parser.add_argument(
        "-o", "--open",
        type=int,
        metavar="N",
        help="Open top N results in $EDITOR"
    )

    args = parser.parse_args()

    # Get data directory
    script_dir = Path(__file__).parent.resolve()

    # Load configuration from .env
    config = {}
    env_file = script_dir / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()

    # Use configured DATA_DIR or default
    data_dir = Path(config.get("DATA_DIR", script_dir / "data")).expanduser()

    # Perform search
    results = search_archive(data_dir, args.query)

    # Output results
    if args.json:
        print_json(results)
    else:
        print_results(results, args.query)

    # Open in editor if requested
    if args.open:
        if args.json:
            print("Warning: Cannot use -o/--open with -j/--json", file=sys.stderr)
        else:
            open_in_editor(results, args.open, config)


if __name__ == "__main__":
    main()
