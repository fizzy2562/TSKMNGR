from __future__ import annotations

import argparse
import functools
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

import anyio
from mcp.server.fastmcp import Context, FastMCP

from archiving import ArchiveManager
from database import Database

INSTRUCTIONS = (
    "Interact with the TSKMNGR task database to review boards and manage tasks for the authenticated user."
)


@dataclass
class Services:
    db: Database
    archive: ArchiveManager


_services: Services | None = None
_services_error: Exception | None = None


def get_services() -> Services:
    """Lazy-load shared services so the module can import without a database."""
    global _services, _services_error
    if _services is None and _services_error is None:
        try:
            database = Database()
            archive = ArchiveManager(database)
            _services = Services(database, archive)
        except Exception as exc:  # pragma: no cover - surfaced via tool errors
            _services_error = exc
    if _services is None:
        raise RuntimeError(f"TSKMNGR MCP server failed to initialize: {_services_error}")
    return _services


async def _run_db(func, /, *args, **kwargs):
    """Execute blocking database work in a worker thread."""
    return await anyio.to_thread.run_sync(functools.partial(func, *args, **kwargs))


SESSION_KEY = "tsk_mngr"


def _get_session_store(ctx: Context) -> Dict[str, Any]:
    session = ctx.session
    store = getattr(session, SESSION_KEY, None)
    if store is None:
        store = {}
        setattr(session, SESSION_KEY, store)
    return store


def _require_user(ctx: Context) -> tuple[int, str]:
    store = _get_session_store(ctx)
    user_id = store.get("user_id")
    username = store.get("username")
    if user_id is None or username is None:
        raise ValueError("Not authenticated. Call login(username, password) first.")
    return int(user_id), str(username)


def _validate_due_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Due date must be YYYY-MM-DD.") from exc
    return parsed.date().isoformat()


server = FastMCP(
    name="TSKMNGR MCP Server",
    instructions=INSTRUCTIONS,
    host="127.0.0.1",
    port=8765,
)


@server.tool()
async def login(username: str, password: str, ctx: Context) -> Dict[str, Any]:
    """Authenticate a user and persist their session for subsequent calls."""
    services = get_services()
    user = await _run_db(services.db.authenticate_user, username, password)
    store = _get_session_store(ctx)
    if not user:
        store.clear()
        raise ValueError("Invalid username or password.")
    store["user_id"] = user["id"]
    store["username"] = user["username"]
    await ctx.info(f"Logged in as {user['username']}")
    return {"user_id": user["id"], "username": user["username"]}


@server.tool()
async def logout(ctx: Context) -> str:
    """Clear the active MCP session."""
    store = _get_session_store(ctx)
    store.clear()
    await ctx.info("Cleared TSKMNGR session state")
    return "Logged out."


@server.tool()
async def current_user(ctx: Context) -> Dict[str, Any]:
    """Return the currently authenticated user."""
    user_id, username = _require_user(ctx)
    return {"user_id": user_id, "username": username}


@server.tool()
async def list_boards(ctx: Context) -> List[Dict[str, Any]]:
    """List boards for the authenticated user with task counts."""
    user_id, _ = _require_user(ctx)
    services = get_services()
    boards = await _run_db(services.db.get_user_boards, user_id)
    result: List[Dict[str, Any]] = []
    for board_id, data in boards.items():
        result.append(
            {
                "board_id": board_id,
                "name": data["header"],
                "active_count": len(data.get("active", [])),
                "completed_count": len(data.get("completed", [])),
            }
        )
    return result


@server.tool()
async def list_tasks(board_id: str, include_completed: bool = True, ctx: Context = None) -> Dict[str, Any]:
    """Return tasks for a specific board."""
    if ctx is None:
        raise ValueError("Context is required.")
    user_id, _ = _require_user(ctx)
    services = get_services()
    boards = await _run_db(services.db.get_user_boards, user_id)
    board = boards.get(board_id)
    if not board:
        raise ValueError("Board not found for the current user.")
    payload: Dict[str, Any] = {
        "board_id": board_id,
        "name": board["header"],
        "active": board.get("active", []),
    }
    if include_completed:
        payload["completed"] = board.get("completed", [])
    return payload


@server.tool()
async def add_task(
    board_id: str,
    task: str,
    due_date: str,
    notes: str | None = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """Add a task to a board, respecting task caps."""
    if ctx is None:
        raise ValueError("Context is required.")
    description = task.strip()
    if not description:
        raise ValueError("Task description cannot be empty.")
    due = _validate_due_date(due_date)
    note_text = (notes or "").strip()
    user_id, username = _require_user(ctx)
    services = get_services()
    success = await _run_db(
        services.db.add_task_with_archiving,
        board_id,
        user_id,
        description,
        due,
        note_text,
        services.archive,
    )
    if not success:
        raise ValueError("Unable to add task. Check board ownership or task limits.")
    await ctx.info(f"Added task for {username}: {description}")
    return {"status": "created", "board_id": board_id, "task": description, "due_date": due}


@server.tool()
async def complete_task(board_id: str, task_id: int, ctx: Context = None) -> Dict[str, Any]:
    """Mark a task as complete by id."""
    if ctx is None:
        raise ValueError("Context is required.")
    user_id, _ = _require_user(ctx)
    services = get_services()

    def _complete() -> Dict[str, Any]:
        boards = services.db.get_user_boards(user_id)
        board = boards.get(board_id)
        if not board:
            raise ValueError("Board not found for the current user.")
        for index, task in enumerate(board.get("active", [])):
            if int(task.get("id")) == task_id:
                archived = services.db.complete_task_with_archiving(board_id, user_id, index, services.archive)
                return {"status": "completed", "archived": archived}
        raise ValueError("Active task not found on this board.")

    return await _run_db(_complete)


@server.tool()
async def create_board(name: str, ctx: Context = None) -> Dict[str, Any]:
    """Create a new board when under the four-board cap."""
    if ctx is None:
        raise ValueError("Context is required.")
    header = name.strip()
    if not header:
        raise ValueError("Board name cannot be empty.")
    user_id, _ = _require_user(ctx)
    services = get_services()

    def _create() -> Dict[str, Any]:
        current = services.db.count_user_boards(user_id)
        if current >= 4:
            raise ValueError("Board limit reached (4 per user).")
        board_id = str(uuid.uuid4())
        services.db.create_board(user_id, header, board_id)
        return {"status": "created", "board_id": board_id, "name": header}

    return await _run_db(_create)


@server.tool()
async def list_archived_tasks(limit: int = 20, offset: int = 0, ctx: Context = None) -> Dict[str, Any]:
    """Return archived tasks for the authenticated user."""
    if ctx is None:
        raise ValueError("Context is required.")
    user_id, _ = _require_user(ctx)
    services = get_services()

    def _list() -> Dict[str, Any]:
        items = services.archive.get_archived_tasks(user_id, limit=max(1, limit), offset=max(0, offset))
        payload = []
        for row in items:
            payload.append(
                {
                    "board": row.get("board_name_at_archive"),
                    "task": row.get("task"),
                    "due_date": row.get("due_date"),
                    "notes": row.get("notes"),
                    "completed_on": row.get("completed_on"),
                    "archived_on": row.get("archived_on"),
                }
            )
        return {"items": payload, "limit": limit, "offset": offset}

    return await _run_db(_list)


def main() -> None:
    parser = argparse.ArgumentParser(description="TSKMNGR MCP server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="Transport protocol to use.",
    )
    parser.add_argument("--host", help="Host for SSE or HTTP transports.")
    parser.add_argument("--port", type=int, help="Port for SSE or HTTP transports.")
    parser.add_argument("--mount-path", default="/", help="Mount path for SSE transport.")
    args = parser.parse_args()

    if args.host:
        server.settings.host = args.host
    if args.port:
        server.settings.port = args.port

    mount = args.mount_path if args.transport == "sse" else None
    server.run(args.transport, mount_path=mount)


if __name__ == "__main__":
    main()
