# LLM Chat Archive Search

A local, offline full-text search tool for LLM chat exports. Works with multiple providers including Claude.ai, ChatGPT, and more.

## Features

- **Multi-provider support**: Works with Claude, ChatGPT, and other LLM providers
- **Multi-account support**: Organize chats from multiple accounts per provider
- **Full-text search**: Fast, local search across all conversations and projects
- **Smart ranking**: Results ranked by relevance with configurable scoring
- **Rich terminal output**: Colorful, easy-to-read results with syntax highlighting
- **JSON export**: Machine-readable output for scripting and automation
- **Editor integration**: Open search results directly in your `$EDITOR`
- **Conversation viewing**: Convert conversations to Markdown or HTML
- **Non-destructive sync**: Preserves locally archived chats even if deleted from provider
- **UUID-based tracking**: Correctly handles conversation renames
- **Completely offline**: No API calls, no internet required

## Supported Providers

| Provider | Conversations | Projects | Export Format |
|----------|---------------|----------|---------------|
| Claude.ai | ✓ | ✓ | `data-*.zip` |
| ChatGPT | ✓ | ✗ | `[hex]-YYYY-MM-DD-HH-MM-SS-[hex].zip` |
| Gemini | Coming soon | Coming soon | TBD |

## Directory Structure

```
llm-chat-archive/
├── data/                           # Organized chat archives
│   ├── claude/
│   │   └── user@example.com/
│   │       ├── conversations/
│   │       │   └── YYYY-MM-DD_Title.json
│   │       ├── projects/
│   │       │   └── YYYY-MM-DD_Project.json
│   │       └── user.json
│   ├── chatgpt/
│   │   └── user@example.com/
│   │       ├── conversations/
│   │       │   └── YYYY-MM-DD_Title.json
│   │       └── user.json
│   └── gemini/
│       └── (future support)
├── archived_exports/               # Processed export files
│   ├── claude/
│   │   └── data-YYYY-MM-DD-*.zip
│   └── chatgpt/
│       └── [hex]-YYYY-MM-DD-*.zip
├── local_views/                    # Generated Markdown/HTML views
│   ├── claude/
│   │   ├── {uuid}.md
│   │   └── {uuid}.html
│   └── chatgpt/
│       ├── {uuid}.md
│       └── {uuid}.html
├── sync_local_chats_archive.py     # Import and sync exports
├── full_text_search_chats_archive.py  # Search conversations
└── view_conversation.py            # View conversations as MD/HTML
```

## Setup

### 1. Make Scripts Executable

```bash
chmod +x sync_local_chats_archive.py
chmod +x full_text_search_chats_archive.py
chmod +x view_conversation.py
```

### 2. Configure Environment (Optional)

Create a `.env` file:

```bash
# Where to search for export zip files (optional, defaults to current directory)
ZIP_SEARCH_DIR=~/Downloads
```

### 3. Export Your Chats

#### Claude.ai
1. Go to https://claude.ai/settings
2. Click "Export data"
3. Download the `data-YYYY-MM-DD-HH-MM-SS-batch-NNNN.zip` file

#### ChatGPT
1. Go to https://chatgpt.com/settings/data-controls
2. Click "Export data"
3. Wait for the email with download link
4. Download the `[hex]-YYYY-MM-DD-HH-MM-SS-[hex].zip` file

### 4. Place Exports

Put the downloaded zip files in your `ZIP_SEARCH_DIR` (or the same directory as the scripts).

## Usage

### Syncing Archives

Import your chat exports into the local archive:

```bash
# Sync Claude exports
./sync_local_chats_archive.py --claude

# Sync ChatGPT exports
./sync_local_chats_archive.py --chatgpt
```

The sync script will:
- Find all export zip files matching the provider's pattern
- Extract and organize conversations/projects by provider and user email
- Update existing conversations (matched by UUID)
- Preserve locally archived chats that were deleted from the provider
- Handle duplicate filenames with numeric suffixes
- Move processed zip files to `archived_exports/{provider}/`

### Searching

Search across all archived conversations and projects:

```bash
# Basic search
./full_text_search_chats_archive.py "search query"

# Export results as JSON
./full_text_search_chats_archive.py "python" --json > results.json

# Open top 3 results in your editor
./full_text_search_chats_archive.py "machine learning" --open 3
```

**Search Options:**
```
positional arguments:
  query              Search query (case-insensitive)

optional arguments:
  -h, --help         Show help message
  -j, --json         Output results as JSON
  -o N, --open N     Open top N results in $EDITOR
```

### Viewing Conversations

Convert conversations to Markdown or HTML for easier reading:

```bash
# View as Markdown (default)
./view_conversation.py {uuid}

# View as HTML
./view_conversation.py {uuid} --format html
```

The script will generate the file in `local_views/{provider}/` and open it automatically.

## How It Works

### Sync Script

The sync script processes chat exports and organizes them locally:

1. **Find exports**: Scans for zip files matching the provider's naming pattern
2. **Extract data**: Reads conversations, projects, and user information from the export
3. **Validate format**: Ensures the export matches expected structure
4. **Organize by user**: Creates directories per provider and user email
5. **Individual files**: Saves each conversation/project as a separate JSON file
6. **UUID tracking**: Uses UUIDs to match conversations across syncs
7. **Safe updates**: Verifies both conversation UUID and account UUID before replacing files
8. **Archive exports**: Moves processed zip files to `archived_exports/` for record-keeping

**Filename Format**: `YYYY-MM-DD_Sanitized-Title.json`

If multiple items have the same name and date, numeric suffixes are added: `YYYY-MM-DD_untitled.json`, `YYYY-MM-DD_untitled-1.json`, etc.

### Search Script

The search script performs full-text search across all archived chats:

1. **Scan archive**: Recursively searches all conversation/project files
2. **Extract text**: Pulls text from names, summaries, messages, and documents
3. **Score matches**: Ranks results based on multiple criteria:
   - Exact phrase match: +10 points
   - All query words present: +5 points
   - Whole word match: +2 points per word
   - Partial word match: +1 point per word
   - Match in title/name: +5 point bonus
4. **Sort by relevance**: Orders results by total score
5. **Generate URLs**: Creates provider-specific URLs for web access
6. **Display results**: Shows matches with highlighted context

### View Script

The view script converts conversation JSON to human-readable formats:

1. **Find conversation**: Searches across all providers for the UUID
2. **Parse structure**: Extracts messages, metadata, and formatting
3. **Generate output**: Creates Markdown or HTML with proper styling
4. **Cache locally**: Saves output to `local_views/{provider}/` for reuse
5. **Open automatically**: Launches the file in your default viewer

## Safety Features

The sync script includes multiple safety mechanisms:

- **Dual UUID verification**: Matches both conversation UUID and account UUID before updates
- **Cross-account protection**: Won't delete files if account UUIDs don't match
- **Collision detection**: Logs warnings if UUID conflicts are detected across accounts
- **Non-destructive by design**: Preserves files that don't match current export
- **Validation checks**: Verifies export format before processing

These features make the tool safe for multi-account use and protect against data loss.

## Requirements

- **Python**: 3.7 or higher
- **Dependencies**: None (uses standard library only)
- **Storage**: Depends on archive size (each conversation is a separate JSON file)

## Notes

- All processing happens locally - no internet connection required after downloading exports
- Search is performed on-demand (no pre-built index)
- All data is stored as human-readable JSON
- Provider URLs in search results enable quick web access to original conversations
- The `data/` directory can be version controlled or backed up separately
- Each provider's data is isolated in its own directory

## Contributing

This tool is designed to be extensible. To add support for a new provider:

1. Create a new `Provider` subclass in `sync_local_chats_archive.py`
2. Implement the required methods (`name()`, `find_exports()`, `extract_data()`, `validate()`)
3. Add provider-specific URL generation to `SearchResult.get_provider_url()`
4. Update documentation with export format details

## License

MIT License - feel free to use and modify as needed.
