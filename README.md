![Demo gif showing searching in the terminal](demo.gif)

I wanted full-text search for my [claude.ai](https://claude.ai/) chats, so I made this.

## Features

- **Multi-provider**: currently Claude and ChatGPT.
- **Multi-account** per provider.
- **Smart search ranking**
- **Hyperlinks in the results**: easy resume when you've found *that chat*
- **JSON output** supported when searching
- **Local view**: copy chats to Markdown or HTML, open in `$EDITOR`
- **Non-destructive sync**: preserves a chat even if you deleted it on the website. Export/sync the last 30 days only and it'll preserve your older chats. 
- **Export backup**: automatic archive of your data export zipfiles
- **UUID tracking**: Correctly handles conversation renames
- **Simple**: just a folder of python scripts. Works with system python.
- **Completely offline**

## Setup

```
git clone git@github.com:marisawallace/clauding-at-home.git
cd clauding-at-home
chmod +x sync_local_chats_archive.py
chmod +x full_text_search_chats_archive.py
chmod +x view_conversation.py

# EDIT THIS IF YOU DON'T WANT TO SEARCH IN ~/Downloads
cat > .env << 'EOF'
# Where to search for export zip files (optional, defaults to current directory)
ZIP_SEARCH_DIR=~/Downloads
EOF
```

I highly recommend adding aliases to your `.bashrc` or equivalent.

```
alias ccs="cd $CODE_HOME/clauding-at-home/"
alias cs="python3 $CODE_HOME/clauding-at-home/full_text_search_chats_archive.py"
alias csscl="python3 $CODE_HOME/clauding-at-home/sync_local_chats_archive.py --claude"
alias cssch="python3 $CODE_HOME/clauding-at-home/sync_local_chats_archive.py --chatgpt"
alias csv="python3 $CODE_HOME/clauding-at-home/view_conversation.py"
alias csvh="python3 $CODE_HOME/clauding-at-home/view_conversation.py --format html"
```

Make sure you have $EDITOR set.

```
export VISUAL=subl
export EDITOR="$VISUAL"
```

### Export Your Chats

#### Claude.ai
1. [https://claude.ai/settings/data-privacy-controls](https://claude.ai/settings/data-privacy-controls)
2. Click "Export data"
3. Download the .zip file
4. `your-alias`, `csscl`, or `python3 sync_local_chats_archive.py --claude`

#### ChatGPT
1. [https://chatgpt.com/#settings/DataControls](https://chatgpt.com/#settings/DataControls)
2. Click "Export data"
3. Download the .zip file
4. `your-alias`, `cssch`, or `python3 sync_local_chats_archive.py --chatgpt`

The sync script will:
- Find all export zip files matching the provider's pattern
- Extract and organize conversations/projects by provider and user email
- Update existing conversations (matched by UUID)
- Preserve locally archived chats that were deleted from the provider
- Handle duplicate filenames with numeric suffixes
- Move processed zip files to `archived_exports/{provider}/`

The sync script includes multiple safety mechanisms:

- **Dual UUID verification**: Matches both conversation UUID and account UUID before updates
- **Cross-account protection**: Won't delete files if account UUIDs don't match
- **Collision detection**: Logs warnings if UUID conflicts are detected across accounts
- **Non-destructive by design**: Preserves files that don't match current export
- **Validation checks**: Verifies export format before processing

Then everything should just work!

## Usage (if you set up based aliases)

```
# Search
cs "hi claude"

# View (copy/paste the UUID from the search results)
# This will open that conversation in a persistent markdown file.
# You can edit this file without destroying any of the original
# export data.
csv UUID

# Directly open the top 3 results for "books" in your `$EDITOR`
cs books -o 3

# JSON output
cs books -j > results.json
```




---



## Directory Structure

```
clauding-at-home/
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

## Known Limitations

### Conversation forks (Claude.ai)

The official Claude.ai data export **does not fully preserve forked conversations**. Specifically:

- **Human messages from all branches** are included in the export (as consecutive same-sender entries in `chat_messages`).
- **Assistant responses from non-selected branches are missing.** Only the response from the branch you last had selected is exported.

This means search results may not include text from assistant responses in branches you didn't select. There is no workaround within this tool since the data simply isn't present in the export.

**Workarounds:**
- Before exporting, revisit conversations with important forks and switch to each branch you care about (the export appears to capture whichever branch is active).


## Requirements

- **Python**: 3.7 or higher
- **Dependencies**: None (uses standard library only)

## Testing

To run the test suite:

```bash
# Option 1: Virtual environment (works on all platforms)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-test.txt
pytest

# Option 2: System package manager
# Debian/Ubuntu: sudo apt install python3-pytest
# Fedora: sudo dnf install python3-pytest
# Arch: sudo pacman -S python-pytest
# macOS: brew install pytest

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/integration/test_sync_workflow.py
```

See [tests/README.md](tests/README.md) for detailed testing documentation, including test structure, fixtures, and debugging tips.

## Contributing

This tool is designed to be extensible. To add support for a new provider:

1. Create a new `Provider` subclass in `sync_local_chats_archive.py`
2. Implement the required methods (`name()`, `find_exports()`, `extract_data()`, `validate()`)
3. Add provider-specific URL generation to `SearchResult.get_provider_url()`
4. Update documentation with export format details
