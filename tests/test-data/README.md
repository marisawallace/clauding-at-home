# Test Data

This directory contains sample Claude.ai export data for testing and development purposes.

## Contents

- `users.json` - Sample user data (1 user)
- `conversations.json` - Sample conversations (minimal examples)
- `projects.json` - Sample projects (minimal examples)

## Purpose

This test data serves multiple purposes:

1. **Format Validation** - Demonstrates the expected structure of Claude.ai exports
2. **Testing** - Used by `test_data_structure.py` to validate the sync scripts
3. **Examples** - Helps developers understand the export format

## Data Structure

### users.json
```json
[
  {
    "uuid": "user-uuid-here",
    "email_address": "user@example.com",
    ...
  }
]
```

### conversations.json
```json
[
  {
    "uuid": "conversation-uuid",
    "name": "Conversation title",
    "summary": "Optional summary",
    "created_at": "2025-10-18T04:06:56.628672Z",
    "updated_at": "2025-10-18T04:58:28.886997Z",
    "account": {
      "uuid": "user-uuid-here"
    },
    "chat_messages": [
      {
        "uuid": "message-uuid",
        "text": "Message content",
        "content": [...],
        "sender": "human" | "assistant",
        "created_at": "...",
        ...
      }
    ]
  }
]
```

### projects.json
```json
[
  {
    "uuid": "project-uuid",
    "name": "Project name",
    "description": "Project description",
    "created_at": "...",
    "creator": {
      "uuid": "user-uuid-here"
    },
    "docs": [
      {
        "uuid": "doc-uuid",
        "filename": "document.txt",
        "content": "Document content",
        ...
      }
    ]
  }
]
```

## Creating Test Zips

To create a test zip file that can be processed by the sync scripts:

```bash
cd test-data
zip -r ../data-2025-01-05-00-00-00-batch-0000.zip users.json conversations.json projects.json
```

Then run the sync script to test:

```bash
cd ..
./sync_local_chats_archive.py --claude
```

## Notes

- The test data contains minimal/sanitized examples
- UUIDs are synthetic and won't match real Claude.ai data
- Timestamps use ISO 8601 format with 'Z' suffix (UTC)
- The data structure mirrors actual Claude.ai exports as of January 2025
