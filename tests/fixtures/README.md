# Test Fixtures

Test fixtures for integration tests are generated programmatically in `tests/conftest.py`.

## Available Fixtures

- `sample_claude_export`: Creates a valid Claude export zip with 2 conversations and 1 project
- `sample_chatgpt_export`: Creates a valid ChatGPT export zip with 1 conversation
- `prepopulated_archive`: Creates a workspace with existing conversation data for update testing
- `isolated_workspace`: Creates a clean temporary workspace with proper directory structure

## Adding Custom Static Fixtures

If you need static test data (e.g., corrupted zips, specific edge cases), place them in this directory and reference them in tests using the `fixtures_dir` fixture:

```python
def test_with_static_fixture(fixtures_dir, isolated_workspace):
    corrupt_zip = fixtures_dir / "corrupt_export.zip"
    shutil.copy(corrupt_zip, isolated_workspace)
    # ... test code
```
