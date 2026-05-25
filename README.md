# zlm

zack's lobe memory

A tiny SQLite-backed session cache for short-lived state.

## Install
```bash
pip install git+https://github.com/ZackaryW/zlm.git
```

## What it is

`zlm` is a small SQLite-backed append cache for short-lived session state.

It is designed for lightweight values like verdicts, flags, scores, decisions, tags, and small structured handoff state.

The identity contract is explicit: session ids are the only lookup key. There is no ambient workspace routing, cwd-derived scope, or implicit latest-session lookup in the CLI.

Retention is bounded by class-configurable defaults:

- at most 5 sessions globally by default
- at most 15 entries per session by default
- eviction happens inline on write

This makes `zlm` closer to a bounded session log/cache than a general-purpose memory system.

## CLI use

The main workflow is:

```powershell
$session = uv run zlm create-session
uv run zlm append $session verdict 'hello'
uv run zlm get $session
```

If you want the current shell to hold the active session id, `create-session` can emit a PowerShell assignment:

```powershell
uv run zlm create-session --export
$env:ZLM_SESSION_ID = '...'
uv run zlm append verdict 'hello'
uv run zlm get
```

Retention can also be overridden from the CLI when you need a larger or smaller window:

```powershell
$session = uv run zlm --max-sessions 10 --max-entries 50 create-session
uv run zlm --max-sessions 10 --max-entries 50 append $session verdict 'hello'
uv run zlm --max-sessions 10 --max-entries 50 get $session
```

You can also set `ZLM_MAX_SESSIONS` and `ZLM_MAX_ENTRIES` in the shell to avoid repeating the flags.

You can also set `ZLM_SESSION_ID` in the shell to make `append` and `get` default to that session when `SESSION_ID` is omitted.

Example output:

```json
[
{"type":"verdict","body":"hello"}
]
```

Appending again reuses the same session id when you pass it again:

```powershell
uv run zlm append $session score '{"$zlmk": 0.91}'
uv run zlm get $session
```

## Commands

`create-session`

- Creates a new session and prints the session id.
- This is the entry point for new state.
- `create-session --export` emits a PowerShell command that sets `ZLM_SESSION_ID` in the current shell.

`append SESSION_ID ENTRY_TYPE BODY_JSON`

- Appends an entry to the given session.
- `BODY_JSON` accepts normal JSON values.
- Plain text is also accepted directly and stored as a string body.
- If `ZLM_SESSION_ID` is set, you can omit `SESSION_ID` and call `append ENTRY_TYPE BODY_JSON`.

Examples:

```powershell
$session = uv run zlm create-session
uv run zlm append $session verdict 'hello'
uv run zlm append $session flag true
uv run zlm append $session decision '{"mode":"fallback","reason":"timeout"}'
uv run zlm append $session score '{"$zlmk": 0.91}'
```

`get SESSION_ID`

- Returns the retained entries for the given session.
- If `ZLM_SESSION_ID` is set, you can omit `SESSION_ID` and call `get`.

Without an explicit `SESSION_ID` or `ZLM_SESSION_ID`, the CLI raises an error.

Global options:

- `--db-path PATH`
- `--max-sessions N`
- `--max-entries N`

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

For Python code that should feel like the CLI, use `Zlm`.

```python
from zlm import Zlm

with Zlm() as zlm:
	session_id = zlm.create_session()
	zlm.append("verdict", "retry")
	zlm.append("decision", {"mode": "fallback", "reason": "timeout"})
	entries = zlm.get()

with Zlm(max_sessions=10, max_entries=50) as zlm:
	session_id = zlm.create_session()
	zlm.append("verdict", "keep more history")

with Zlm(session_id=session_id) as zlm:
	entries = zlm.get()
```

`Zlm` binds to a session id:

- `create_session()`
- `append(type, body, session_id=None)`
- `get(session_id=None)`

When a `Zlm` instance is constructed with `session_id=...`, or after `create_session()` is called on that instance, `append()` and `get()` can use the bound session implicitly. Passing `session_id=...` to `append()` or `get()` targets a specific session explicitly.

`Zlm` also accepts optional `max_sessions` and `max_entries` constructor arguments to override the default retention window.

`SQLiteMemoryContext` remains the lower-level storage API.

```python
from zlm import SQLiteMemoryContext

context = SQLiteMemoryContext()
session_id = context.create_session()
context.append(session_id, {"type": "verdict", "body": "retry"})
entries = context.get_session_memory(session_id)
context.close()
```

By default the SQLite file is stored at `{temp}/zlm-memory.db`.
Pass `db_path` to override it, for example in tests or for project-local storage. `SQLiteMemoryContext` also accepts `max_sessions` and `max_entries`.
