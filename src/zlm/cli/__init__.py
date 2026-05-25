from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import orjson

from zlm.helper import Zlm


_RESERVED_LITERAL_KEY = "$zlmk"
_SESSION_ENV_VAR = "ZLM_SESSION_ID"


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


def _with_zlm(
	db_path: str | None,
	max_sessions: int,
	max_entries: int,
) -> Zlm:
	return Zlm(
		db_path=Path(db_path) if db_path is not None else None,
		max_sessions=max_sessions,
		max_entries=max_entries,
	)


def _create_zlm_for_session(
	db_path: str | None,
	session_id: str | None,
	max_sessions: int,
	max_entries: int,
) -> Zlm:
	return Zlm(
		db_path=Path(db_path) if db_path is not None else None,
		session_id=session_id,
		max_sessions=max_sessions,
		max_entries=max_entries,
	)


def _quote_powershell_string(value: str) -> str:
	return value.replace("'", "''")


def _resolve_cli_session_id(session_id: str | None) -> str:
	if session_id is None:
		raise click.ClickException(f"session_id is required; pass SESSION_ID or set {_SESSION_ENV_VAR}")

	return session_id


@click.group()
@click.option("--db-path", type=click.Path(path_type=str), default=None, help="Path to the SQLite database file.")
@click.option("--zlm-session-id", "env_session_id", envvar=_SESSION_ENV_VAR, default=None, help="Default session id when SESSION_ID is omitted.")
@click.option(
	"--max-sessions",
	type=click.IntRange(min=1),
	default=5,
	show_default=True,
	envvar="ZLM_MAX_SESSIONS",
	help="Maximum retained sessions.",
)
@click.option(
	"--max-entries",
	type=click.IntRange(min=1),
	default=15,
	show_default=True,
	envvar="ZLM_MAX_ENTRIES",
	help="Maximum retained entries per session.",
)
@click.pass_context
def cli(
	ctx: click.Context,
	db_path: str | None,
	env_session_id: str | None,
	max_sessions: int,
	max_entries: int,
) -> None:
	ctx.ensure_object(dict)
	ctx.obj["db_path"] = db_path
	ctx.obj["env_session_id"] = env_session_id
	ctx.obj["max_sessions"] = max_sessions
	ctx.obj["max_entries"] = max_entries


@cli.command(
	"append",
	help=(
		"Append an entry to a session. "
		"Pass SESSION_ID explicitly or set ZLM_SESSION_ID. "
		"Pass raw text for string bodies or use {\"$zlmk\": ...} to unwrap a scalar value explicitly."
	),
)
@click.argument("args", nargs=-1)
@click.pass_context
def append_entry(ctx: click.Context, args: tuple[str, ...]) -> None:
	if len(args) == 3:
		session_id, entry_type, body_json = args
	elif len(args) == 2:
		session_id = ctx.obj["env_session_id"]
		entry_type, body_json = args
	else:
		raise click.UsageError("append expects SESSION_ID ENTRY_TYPE BODY_JSON or ENTRY_TYPE BODY_JSON when ZLM_SESSION_ID is set")

	try:
		with _create_zlm_for_session(
			ctx.obj["db_path"],
			_resolve_cli_session_id(session_id),
			ctx.obj["max_sessions"],
			ctx.obj["max_entries"],
		) as zlm:
			zlm.append(entry_type, _load_json(body_json))
	except ValueError as exc:
		raise click.ClickException(str(exc)) from exc


@cli.command("create-session", help="Create a new session and print its session id.")
@click.option("--export", "export_session", is_flag=True, help="Emit a PowerShell command that sets ZLM_SESSION_ID.")
@click.pass_context
def create_session(ctx: click.Context, export_session: bool) -> None:
	with _with_zlm(
		ctx.obj["db_path"],
		ctx.obj["max_sessions"],
		ctx.obj["max_entries"],
	) as zlm:
		session_id = zlm.create_session()

	if export_session:
		quoted_session_id = _quote_powershell_string(session_id)
		click.echo(f"$env:{_SESSION_ENV_VAR} = '{quoted_session_id}'")
		return

	click.echo(session_id)


@cli.command("adopt", help="Validate SESSION_ID and emit a PowerShell command that sets ZLM_SESSION_ID.")
@click.argument("session_id")
@click.pass_context
def adopt_session(ctx: click.Context, session_id: str) -> None:
	try:
		with _with_zlm(
			ctx.obj["db_path"],
			ctx.obj["max_sessions"],
			ctx.obj["max_entries"],
		) as zlm:
			resolved_session_id = zlm.adopt(session_id)
	except ValueError as exc:
		raise click.ClickException(str(exc)) from exc

	quoted_session_id = _quote_powershell_string(resolved_session_id)
	click.echo(f"$env:{_SESSION_ENV_VAR} = '{quoted_session_id}'")


@cli.command("get", help="Get retained memory for a session. Pass SESSION_ID explicitly or set ZLM_SESSION_ID.")
@click.argument("session_id", required=False)
@click.pass_context
def get_session_memory(ctx: click.Context, session_id: str | None) -> None:
	try:
		with _create_zlm_for_session(
			ctx.obj["db_path"],
			_resolve_cli_session_id(session_id or ctx.obj["env_session_id"]),
			ctx.obj["max_sessions"],
			ctx.obj["max_entries"],
		) as zlm:
			entries = zlm.get()
	except ValueError as exc:
		raise click.ClickException(str(exc)) from exc

	click.echo(_dump_json(entries))
main = cli

__all__ = ["cli", "main"]
