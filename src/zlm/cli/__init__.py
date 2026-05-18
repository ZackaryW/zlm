from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import orjson

from zlm.core import SQLiteMemoryContext
from zlm.utils import CWD_OVERRIDE_ENV, ensure_session_id, resolve_session_id, resolve_workspace_root


_RESERVED_LITERAL_KEY = "$zlmk"


def _dump_json(value: Any) -> str:
	if isinstance(value, list):
		if not value:
			return "[]"

		items = [orjson.dumps(item).decode("utf-8") for item in value]
		return "[\n" + ",\n".join(items) + "\n]"

	return orjson.dumps(value).decode("utf-8")



def _unwrap_reserved_literal(value: Any) -> Any:
	if isinstance(value, dict) and set(value) == {_RESERVED_LITERAL_KEY}:
		return value[_RESERVED_LITERAL_KEY]

	return value


def _load_json(value: str) -> Any:
	try:
		return _unwrap_reserved_literal(orjson.loads(value))
	except orjson.JSONDecodeError as exc:
		if value[:1] in {"{", "["}:
			raise click.ClickException(f"body must be valid JSON: {exc}") from exc

		return _unwrap_reserved_literal({_RESERVED_LITERAL_KEY: value})


def _with_context(db_path: str | None) -> SQLiteMemoryContext:
	return SQLiteMemoryContext(Path(db_path) if db_path is not None else None)


def _quote_powershell_string(value: str) -> str:
	return value.replace("'", "''")


@click.group()
@click.option("--db-path", type=click.Path(path_type=str), default=None, help="Path to the SQLite database file.")
@click.option("--workspace-hash", default=None, help="Override the derived workspace hash.")
@click.pass_context
def cli(ctx: click.Context, db_path: str | None, workspace_hash: str | None) -> None:
	ctx.ensure_object(dict)
	ctx.obj["db_path"] = db_path
	ctx.obj["workspace_hash"] = workspace_hash


@cli.command(
	"append",
	help=(
		"Append an entry to the current workspace session. "
		"Pass raw text for string bodies or use {\"$zlmk\": ...} to unwrap a scalar value explicitly."
	),
)
@click.argument("entry_type")
@click.argument("body_json")
@click.pass_context
def append_entry(ctx: click.Context, entry_type: str, body_json: str) -> None:
	entry = {"type": entry_type, "body": _load_json(body_json)}
	try:
		with _with_context(ctx.obj["db_path"]) as memory_context:
			resolved_session_id = ensure_session_id(
				memory_context,
				workspace_hash=ctx.obj["workspace_hash"],
			)
			memory_context.append(
				resolved_session_id,
				entry,
				workspace_hash=ctx.obj["workspace_hash"],
			)
	except ValueError as exc:
		raise click.ClickException(str(exc)) from exc


@cli.command(
	"adopt",
	help=(
		"Emit a PowerShell command that sets the workspace override so the current shell adopts another path's session scope."
	),
)
@click.argument("path", type=click.Path(path_type=Path))
def adopt_workspace(path: Path) -> None:
	workspace_root = resolve_workspace_root(path)
	quoted_root = _quote_powershell_string(str(workspace_root))
	click.echo(f"$env:{CWD_OVERRIDE_ENV} = '{quoted_root}'")


@cli.command("swap", help="Create and switch to a new current workspace session.")
@click.pass_context
def swap_session(ctx: click.Context) -> None:
	with _with_context(ctx.obj["db_path"]) as memory_context:
		session_id = memory_context.create_session(workspace_hash=ctx.obj["workspace_hash"])

	click.echo(session_id)


@cli.command("get", help="Get retained memory for the current workspace session.")
@click.argument("session_id", required=False)
@click.pass_context
def get_session_memory(ctx: click.Context, session_id: str | None) -> None:
	try:
		with _with_context(ctx.obj["db_path"]) as memory_context:
			resolved_session_id = resolve_session_id(
				memory_context,
				session_id=session_id,
				workspace_hash=ctx.obj["workspace_hash"],
			)
			entries = memory_context.get_session_memory(
				resolved_session_id,
				workspace_hash=ctx.obj["workspace_hash"],
			)
	except ValueError as exc:
		raise click.ClickException(str(exc)) from exc

	click.echo(_dump_json(entries))
main = cli

__all__ = ["cli", "main"]
