# zlm

zack's lite memory

## What it is

`zlm` is a small SQLite-backed rolling memory tool for short-lived workspace state.

It is designed for lightweight values like verdicts, flags, scores, decisions, and tags. Memory is scoped to the current workspace, with workspace identity derived from git root when available.

Retention is bounded:

- at most 5 sessions per workspace
- at most 15 entries per session
- eviction happens inline on write

## CLI use

The main workflow is:

```powershell
uv run zlm append verdict 'hello'
uv run zlm get
```

Example output:

```json
[
{"type":"verdict","body":"hello"}
]
```

Appending again reuses the current workspace session until you explicitly start a new one:

```powershell
uv run zlm append score '{"$zlmk": 0.91}'
uv run zlm get
```

## Commands

`append ENTRY_TYPE BODY_JSON`

- Appends an entry to the current workspace session.
- If no session exists yet for the current workspace, one is created automatically.
- `BODY_JSON` accepts normal JSON values.
- Plain text is also accepted directly and stored as a string body.

Examples:

```powershell
uv run zlm append verdict 'hello'
uv run zlm append flag true
uv run zlm append decision '{"mode":"fallback","reason":"timeout"}'
uv run zlm append score '{"$zlmk": 0.91}'
```

`get [SESSION_ID]`

- Returns the retained entries for the current workspace session.
- If `SESSION_ID` is omitted, `zlm` resolves the latest session for the current workspace.

`swap`

- Creates a new session for the current workspace.
- Later `append` and `get` calls resolve to that new session because it becomes the latest workspace session.

`adopt PATH`

- Emits a PowerShell command that sets `zlm_cwd_override` to the resolved workspace root for `PATH`.
- This is useful for agent worktrees that need to inherit the user's workspace memory scope.

Example:

```powershell
uv run zlm adopt ..\user-workspace
$env:zlm_cwd_override = 'D:\user-workspace'
```

After setting the override in the current shell, later `append`, `get`, and `swap` calls resolve against the adopted workspace instead of the shell's literal cwd.

## Input rules

Entries are stored with this logical shape:

```json
{"type":"verdict","body":"retry"}
```

The CLI derives `type` from the first positional argument and parses `body` from the second.

Supported body forms:

- raw string shorthand: `hello`
- JSON string: `"hello"`
- JSON boolean: `true`
- JSON number: `0.91`
- JSON object or list
- reserved scalar wrapper: `{"$zlmk": value}`

The reserved wrapper is useful when you want to pass a scalar through a structured JSON shape explicitly.

## Python use

`SQLiteMemoryContext` provides the underlying API.

```python
from zlm import SQLiteMemoryContext

context = SQLiteMemoryContext()
session_id = context.create_session()
context.append(session_id, {"type": "verdict", "body": "retry"})
entries = context.get_session_memory(session_id)
context.close()
```

By default the SQLite file is stored at `{temp}/zlm-memory.db`.
Pass `db_path` to override it, for example in tests or for workspace-local storage.
