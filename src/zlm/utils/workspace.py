from __future__ import annotations

import hashlib
import os
from pathlib import Path


CWD_OVERRIDE_ENV = "zlm_cwd_override"


def _workspace_target(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)

    override = os.environ.get(CWD_OVERRIDE_ENV)
    if override:
        return Path(override)

    return Path.cwd()


def resolve_workspace_root(path: str | Path | None = None) -> Path:
    target = _workspace_target(path)
    resolved = target.resolve()

    if resolved.exists() and resolved.is_file():
        resolved = resolved.parent

    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate

    return resolved


def derive_workspace_hash(path: str | Path | None = None) -> str:
    workspace_root = resolve_workspace_root(path)
    canonical_path = os.path.normcase(os.path.normpath(str(workspace_root)))
    return hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()