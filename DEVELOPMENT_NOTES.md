# Development Notes

Internal notes on implementation details, data format quirks, and known issues.
Intended for contributors and future Claude Code sessions working on this codebase.

---

## Claude.ai Export Format: Conversation Forks

**Date investigated:** 2026-02-03

### Background

Claude.ai supports conversation forking: users can edit a previous message or retry
a response, creating branching conversation paths. The UI lets users switch between
branches and continue from any of them.

### How forks appear in the export data

The official Claude.ai data export (`conversations.json` inside the zip) stores
messages in a **flat array** under `chat_messages`. There is no tree structure,
no `parent_message_uuid` field, and no explicit branch metadata. Message keys are:

```
uuid, text, content, sender, created_at, updated_at, attachments, files
```

Forks manifest as **consecutive messages with the same `sender`**. In a linear
conversation, messages strictly alternate human/assistant. When you see two or more
consecutive `human` messages, that's a fork point -- the user edited or retried
their message.

### What's preserved and what's lost

**Preserved:**
- All human message variants from all branches (each with a unique UUID)
- The assistant response from the **currently selected** branch
- The conversation `summary` field (which may reference content from any branch)

**Lost:**
- Assistant responses from non-selected branches are completely absent
- There is no way to determine which human message each assistant response
  corresponds to (no parent references)
- There is no way to reconstruct the branch tree structure

### Concrete examples

These examples reference conversations from the maintainer's personal data archive.
The specific files won't exist in other users' data directories, but the patterns
are representative of what you'll see in any Claude.ai export with forks.

#### Example: Edited follow-up

File: `2025-12-14_Extract-Quest-Diagnostics-lab-report-to-JSON.json` (4 messages)

```
[0] human      "please write me a python script to extract..."
[1] assistant  "I'll create a Python script..."
[2] human      "Oof, this code looks really brittle, and seems to rely on coding regexes..."  ← branch A
[3] human      "Oof, this code is quite brittle-- it seems to rely on regexes..."             ← branch B (selected)
```

Two versions of the follow-up critique. No assistant response to either branch is
present in this 4-message export (the conversation may have been abandoned at the
fork, or the response was on a branch not captured).

### Impact on search

The `extract_text_from_conversation()` function in `full_text_search_chats_archive.py`
iterates over all entries in `chat_messages`, so it **does search all human message
variants** from all fork branches. The limitation is that assistant responses from
non-selected branches are not searchable because they aren't in the data.

Note that each message's text appears twice in the extracted text blocks: once from
the top-level `text` field and once from `content[0].text`. This is expected behavior
per the export format (see the docstring in `sync_local_chats_archive.py` around
line 348 for details on this duplication).

### Detection heuristic

To programmatically detect forks in exported data, look for consecutive messages
with the same `sender` value. In a fork-free conversation, senders always alternate
human/assistant. Any deviation from this pattern indicates a fork.

### External references

- The official [Claude help center article on data export](https://support.claude.com/en/articles/9450526-how-can-i-export-my-claude-data) does not mention forks or branches.
- The third-party [claude-exporter](https://github.com/agoramachina/claude-exporter) Chrome extension advertises "Branch-Aware Export" in its JSON format, implying the official export does not preserve full branch data.
- No Anthropic bug tracker or forum discussion was found specifically documenting this limitation as of 2026-02-03.

### Possible future improvements

- Add a `--warn-forks` flag to the search tool that detects and reports conversations
  with missing fork data, so users know which conversations are incomplete.
- If Anthropic updates the export format to include branch metadata or parent message
  references, update `extract_text_from_conversation()` to traverse the tree and
  ensure all branches are covered.
- Consider deduplicating identical human messages in search results (currently the
  same retry text may generate many redundant match entries).
