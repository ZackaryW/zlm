# Use zlm

Use this guide when you need to read or write lightweight workspace memory with `zlm`.

## Purpose

`zlm` is for short-lived workspace state, not long-term history.

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

- Memory is scoped to a workspace.
- Workspace identity is derived from git root when available.
- Sessions are rolling containers within that workspace.
- `append` writes to the current workspace session.
- `swap` creates a new current session.
- `get` reads the current workspace session unless a session id is passed.

Retention is bounded automatically:

- 5 sessions per workspace
- 15 entries per session

## Core commands

Append a string:

```powershell
uv run zlm append verdict 'hello'
```

Append a boolean:

```powershell
uv run zlm append flag true
```

Append a structured object:

```powershell
uv run zlm append decision '{"mode":"fallback","reason":"timeout"}'
```

Append a scalar explicitly through the reserved wrapper:

```powershell
uv run zlm append score '{"$zlmk": 0.91}'
```

Read current workspace memory:

```powershell
uv run zlm get
```

Start a new current session:

```powershell
uv run zlm swap
```

Read a specific session:

```powershell
uv run zlm get SESSION_ID
```

## Agent worktree use

When running in a worktree, you may want the agent to share the user's main workspace memory rather than creating a separate worktree-scoped memory stream.

Use `adopt` to emit a PowerShell env assignment for the target workspace:

```powershell
uv run zlm adopt ..\user-workspace
```

Example output:

```powershell
$env:zlm_cwd_override = 'D:\user-workspace'
```

After that env var is set in the current shell, `append`, `get`, and `swap` resolve against the adopted workspace root.

## Python helper surface

When using `zlm` from Python rather than the CLI, prefer the `Zlm` helper for the same workflow shape:

```python
from zlm import Zlm

with Zlm() as zlm:
	zlm.append("verdict", "retry")
	entries = zlm.get()
	zlm.swap()
	zlm.adopt("../user-workspace")
```

Use `SQLiteMemoryContext` directly only when you want low-level control over session ids and storage operations.

## Recommended usage patterns

Write a handoff verdict:

```powershell
uv run zlm append verdict 'retry'
```

Write a temporary routing decision:

```powershell
uv run zlm append decision '{"mode":"fallback","reason":"timeout"}'
```

Write a flag:

```powershell
uv run zlm append flag true
```

Read current state before acting:

```powershell
uv run zlm get
```

Start a clean session when context should roll forward without mutating the current one:

```powershell
uv run zlm swap
```

## Notes

- `append` auto-creates a session if the workspace does not have one yet.
- `get` without a session id resolves the latest session for the workspace.
- Different subdirectories in the same git repo share the same workspace basis.
- Different worktrees do not share memory unless you intentionally adopt the same workspace.