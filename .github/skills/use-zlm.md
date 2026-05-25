# Use zlm

Use this guide when you need to read or write lightweight session memory with `zlm`.

## Purpose

`zlm` is for short-lived session state, not long-term history.

Use it for:

- verdicts
- flags
- temporary decisions
- scores
- tags
- small structured handoff state

Avoid using it for:

- large transcripts
- historical archives
- lineage graphs
- durable audit logs

## Mental model

- Memory is scoped to an explicit session id.
- Sessions are rolling containers.
- `create-session` creates a new session id.
- `append` writes to the given session.
- `get` reads the given session.
- `ZLM_SESSION_ID` can act as the shell-local default session.

Retention is bounded automatically:

- 5 sessions globally
- 15 entries per session

## Core commands

Create a session:

```powershell
$session = uv run zlm create-session
```

Load the current shell session automatically:

```powershell
uv run zlm create-session --export
$env:ZLM_SESSION_ID = '...'
```

Append a string:

```powershell
uv run zlm append $session verdict 'hello'
```

If `ZLM_SESSION_ID` is already set in the shell:

```powershell
uv run zlm append verdict 'hello'
```

Append a boolean:

```powershell
uv run zlm append $session flag true
```

Append a structured object:

```powershell
uv run zlm append $session decision '{"mode":"fallback","reason":"timeout"}'
```

Append a scalar explicitly through the reserved wrapper:

```powershell
uv run zlm append $session score '{"$zlmk": 0.91}'
```

Read session memory:

```powershell
uv run zlm get $session
```

If `ZLM_SESSION_ID` is already set in the shell:

```powershell
uv run zlm get
```

Read a specific session:

```powershell
uv run zlm get SESSION_ID
```

## Python helper surface

When using `zlm` from Python rather than the CLI, prefer the `Zlm` helper for the same workflow shape:

```python
from zlm import Zlm

with Zlm() as zlm:
	session_id = zlm.create_session()
	zlm.append("verdict", "retry")
	entries = zlm.get()
```

You can also bind an existing session explicitly:

```python
from zlm import Zlm

with Zlm(session_id=session_id) as zlm:
	entries = zlm.get()
```

Use `SQLiteMemoryContext` directly only when you want low-level control over session ids and storage operations.

## Recommended usage patterns

Write a handoff verdict:

```powershell
$session = uv run zlm create-session
uv run zlm append $session verdict 'retry'
```

Write a temporary routing decision:

```powershell
uv run zlm append $session decision '{"mode":"fallback","reason":"timeout"}'
```

Write a flag:

```powershell
uv run zlm append $session flag true
```

Read current state before acting:

```powershell
uv run zlm get $session
```

## Notes

- `create-session` is the explicit entry point for new memory.
- `create-session --export` emits a PowerShell command that sets `ZLM_SESSION_ID`.
- `append` requires a session id unless `ZLM_SESSION_ID` is set.
- `get` requires a session id unless `ZLM_SESSION_ID` is set.
- Session ids are the only identity contract.