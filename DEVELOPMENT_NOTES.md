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

## OpenAI Codex Rollout Format

Notes on the Codex transcript format that `codex_parser.py` consumes, captured during the Codex-support build (codex-cli 0.133.0).

### Layout and storage

Codex writes one append-only JSONL "rollout" per session at `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ISO-ts>-<uuid>.jsonl` (default `$CODEX_HOME` is `~/.codex`). The date is the session start and is stable across resume; there is **no project/cwd directory** in the path — the cwd lives in the `session_meta` record. The session id is embedded in the filename, which is how `find_session_file` resolves an id to a file. Everything else under `~/.codex` (`auth.json` — sensitive, never read; `history.jsonl` — a cross-session prompt-draft log, not a transcript; `config.toml`, the `*.sqlite` state, `memories/`, `skills/`, `cache/`) is Codex's own state and is ignored.

### Record taxonomy

Every line is `{"timestamp", "type", "payload"}`; `type` is one of four, with `payload.type` discriminating the event/response streams. The load-bearing insight: **`event_msg` is the clean human-facing stream; `response_item` is the raw API stream**, and the two duplicate each turn's text.

- `session_meta` (once, line 1): `payload.id` → session_id, `payload.cwd`, `payload.timestamp` → created_at. Holds the ~21 KB `base_instructions` system prompt (ignored). No git info, no title.
- `turn_context` (one per turn): `payload.model` (e.g. `gpt-5.5`) — the **only** place the model id appears.
- `event_msg`/`user_message` and `event_msg`/`agent_message`: `payload.message` is the clean typed prompt / rendered reply → the only thing used for search text, naming, and turns.
- `response_item`/`message`: the raw, noisy model-facing stream (`user` wrapped in `<environment_context>`, `developer` boilerplate). Skipped — prefer the `event_msg` equivalents.
- `response_item`/`reasoning`: `encrypted_content` blob — **encrypted, unreadable; skipped entirely.**
- `response_item`/`function_call` and `custom_tool_call`: tool calls keyed by `call_id`; `name` (e.g. `exec_command`, `apply_patch`) feeds the tool leaderboard.
- `event_msg`/`task_started` `/task_complete` `/turn_aborted`: turn lifecycle (`turn_aborted` = interrupted). `token_count`, `patch_apply_end`: telemetry/diffs, not search text.

### Append-only across resume

Proven by a controlled two-turn resume test: `codex exec` one turn, record the rollout's inode + size + whole-file sha256, `codex exec resume` a second turn — afterward same inode, the original byte-prefix hashed identically, and the new turn appended as fresh lines. This is the assumption `mirror_engine`/`codex_sync` depend on. Auto-compaction was not exercised; `mirror_engine`'s truncation log (`codex_anomalies.log`) is the canary.

### Sync trigger

Codex has a stable lifecycle-hooks engine (v0.124.0+). `codex_sync.py` is wired as a `Stop` hook via `~/.codex/hooks.json`. Unlike Claude Code, **the Codex `Stop` payload carries no `transcript_path`** (only `session_id`, `cwd`, `hook_event_name`, `turn_id`, `stop_hook_active`, `last_assistant_message`, `permission_mode`), so `codex_sync` **sweeps** the whole `sessions/` tree each turn rather than syncing a named file. The sweep is idempotent and cheap (the archive-size shortcut in `mirror_engine.sync_transcript` skips unchanged files with one `stat()`). Codex won't run an untrusted hook — trust it once via the `/hooks` CLI command (or `codex exec --dangerously-bypass-hook-trust` for automation).
