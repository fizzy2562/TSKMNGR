from __future__ import annotations

import argparse
import csv
import functools
import io
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


def _parse_date(value: Any) -> Optional[date]:
    """Best-effort parsing of a YYYY-MM-DD string into a date object."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _format_board_ascii(board_payload: Dict[str, Any]) -> str:
    """Render a lightweight ASCII representation of a board."""
    lines: List[str] = [f"Board: {board_payload.get('name', 'Unknown')}".strip(), "", "Active Tasks:"]
    active_tasks = board_payload.get("active", []) or []
    completed_tasks = board_payload.get("completed", []) or []

    if not active_tasks:
        lines.append("  (none)")
    else:
        for task in active_tasks:
            due = task.get("date") or "—"
            notes = task.get("notes") or ""
            summary = f"  • [{due}] {task.get('task', 'Untitled')}"
            if notes:
                summary += f" — {notes}"
            lines.append(summary)

    lines.extend(["", "Completed Tasks:"])
    if not completed_tasks:
        lines.append("  (none)")
    else:
        for task in completed_tasks[:10]:
            completed_on = task.get("completed_on") or "—"
            lines.append(f"  • [{completed_on}] {task.get('task', 'Untitled')}")
        if len(completed_tasks) > 10:
            lines.append(f"  … {len(completed_tasks) - 10} more completed tasks")

    return "\n".join(lines)


def _build_board_csv(board_payload: Dict[str, Any]) -> str:
    """Generate a CSV string representing board tasks."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "status", "task", "due_date", "notes", "completed_on"])

    for task in board_payload.get("active", []) or []:
        writer.writerow([task.get("id"), "active", task.get("task"), task.get("date"), task.get("notes", ""), ""])
    for task in board_payload.get("completed", []) or []:
        writer.writerow([task.get("id"), "completed", task.get("task"), task.get("date"), task.get("notes", ""), task.get("completed_on", "")])

    return output.getvalue()


def _summarize_board(board_payload: Dict[str, Any]) -> str:
    """Create a human-readable summary of board health."""
    active = board_payload.get("active", []) or []
    completed = board_payload.get("completed", []) or []
    total = len(active) + len(completed)
    today = datetime.now().date()
    overdue = [task for task in active if (_parse_date(task.get("date")) or today) < today]
    upcoming = [task for task in active if 0 <= (( _parse_date(task.get("date")) or today) - today).days <= 7]

    lines = [
        f"Board '{board_payload.get('name', 'Unknown')}' overview:",
        f"- Active tasks: {len(active)}",
        f"- Completed tasks: {len(completed)}",
        f"- Total tasks (active + completed): {total}",
        f"- Overdue tasks: {len(overdue)}",
        f"- Due within 7 days: {len(upcoming)}",
    ]

    if active:
        next_due = min(active, key=lambda task: _parse_date(task.get("date")) or today)
        next_due_date = next_due.get("date", "N/A")
        lines.append(f"- Next due task: '{next_due.get('task', 'Untitled')}' on {next_due_date}")

    return "\n".join(lines)


def _normalize_date_output(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


server = FastMCP(
    name="TSKMNGR MCP Server",
    instructions=INSTRUCTIONS,
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
async def list_tasks(ctx: Context, board_id: str, include_completed: bool = True) -> Dict[str, Any]:
    """Return tasks for a specific board."""
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
    ctx: Context,
    board_id: str,
    task: str,
    due_date: str,
    notes: str | None = None,
) -> Dict[str, Any]:
    """Add a task to a board, respecting task caps."""
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
async def complete_task(ctx: Context, board_id: str, task_id: int) -> Dict[str, Any]:
    """Mark a task as complete by id."""
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
async def create_board(ctx: Context, name: str) -> Dict[str, Any]:
    """Create a new board when under the four-board cap."""
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
async def delete_board(ctx: Context, board_id: str) -> Dict[str, Any]:
    """Delete a board when more than one board exists."""
    user_id, username = _require_user(ctx)
    services = get_services()

    def _delete() -> Dict[str, Any]:
        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT id FROM boards WHERE id = %s AND user_id = %s',
                    (board_id, user_id),
                )
                if cursor.fetchone() is None:
                    raise ValueError("Board not found for the current user.")

                cursor.execute('SELECT COUNT(*) AS count FROM boards WHERE user_id = %s', (user_id,))
                if cursor.fetchone()["count"] <= 1:
                    raise ValueError("Cannot delete the last remaining board.")

                cursor.execute('DELETE FROM boards WHERE id = %s AND user_id = %s', (board_id, user_id))
                conn.commit()

        return {"status": "deleted", "board_id": board_id}

    result = await _run_db(_delete)
    await ctx.info(f"Deleted board {board_id} for {username}")
    return result


@server.tool()
async def update_board_name(ctx: Context, board_id: str, name: str) -> Dict[str, Any]:
    """Rename a board."""
    new_name = name.strip()
    if not new_name:
        raise ValueError("Board name cannot be empty.")
    user_id, username = _require_user(ctx)
    services = get_services()

    def _rename() -> Dict[str, Any]:
        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT id FROM boards WHERE id = %s AND user_id = %s',
                    (board_id, user_id),
                )
                if cursor.fetchone() is None:
                    raise ValueError("Board not found for the current user.")

                cursor.execute(
                    'UPDATE boards SET header = %s WHERE id = %s AND user_id = %s',
                    (new_name, board_id, user_id),
                )
                conn.commit()

        return {"status": "renamed", "board_id": board_id, "name": new_name}

    result = await _run_db(_rename)
    await ctx.info(f"Renamed board {board_id} to '{new_name}' for {username}")
    return result


@server.tool()
async def get_board_stats(ctx: Context, board_id: str) -> Dict[str, Any]:
    """Return aggregate statistics for a board."""
    user_id, _ = _require_user(ctx)
    services = get_services()
    boards = await _run_db(services.db.get_user_boards, user_id)
    board = boards.get(board_id)
    if not board:
        raise ValueError("Board not found for the current user.")

    active = board.get("active", []) or []
    completed = board.get("completed", []) or []
    today = datetime.now().date()

    overdue = [task for task in active if (_parse_date(task.get("date")) or today) < today]
    due_soon = [
        task
        for task in active
        if 0 <= ((_parse_date(task.get("date")) or today) - today).days <= 7
    ]

    first_completed = min(
        (task for task in completed if task.get("completed_on")),
        default=None,
        key=lambda task: _parse_date(task.get("completed_on")) or today,
    )
    most_recent_completion = max(
        (task for task in completed if task.get("completed_on")),
        default=None,
        key=lambda task: _parse_date(task.get("completed_on")) or today,
    )

    stats = {
        "board_id": board_id,
        "name": board.get("header"),
        "active_count": len(active),
        "completed_count": len(completed),
        "total_count": len(active) + len(completed),
        "overdue_count": len(overdue),
        "due_within_7_days": len(due_soon),
        "oldest_completion": first_completed.get("completed_on") if first_completed else None,
        "latest_completion": most_recent_completion.get("completed_on") if most_recent_completion else None,
    }

    return stats


@server.tool()
async def list_archived_tasks(ctx: Context, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """Return archived tasks for the authenticated user."""
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


@server.tool()
async def update_task(
    ctx: Context,
    task_id: int,
    new_task: Optional[str] = None,
    new_due_date: Optional[str] = None,
    new_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the core fields for a task owned by the user."""
    if not any(value is not None for value in (new_task, new_due_date, new_notes)):
        raise ValueError("Provide at least one field to update.")

    updates: Dict[str, Any] = {}
    if new_task is not None:
        stripped = new_task.strip()
        if not stripped:
            raise ValueError("Task description cannot be empty.")
        updates["task"] = stripped
    if new_due_date is not None:
        updates["due_date"] = _validate_due_date(new_due_date)
    if new_notes is not None:
        updates["notes"] = new_notes.strip()

    user_id, username = _require_user(ctx)
    services = get_services()

    def _update() -> Dict[str, Any]:
        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT t.id, t.board_id, t.task, t.due_date, t.notes, t.is_completed, t.completed_on
                       FROM tasks t
                       JOIN boards b ON t.board_id = b.id
                       WHERE t.id = %s AND b.user_id = %s''',
                    (task_id, user_id),
                )
                original = cursor.fetchone()
                if original is None:
                    raise ValueError("Task not found for the current user.")

                if updates:
                    set_clause = ", ".join(f"{column} = %s" for column in updates.keys())
                    cursor.execute(
                        f"UPDATE tasks SET {set_clause} WHERE id = %s",
                        (*updates.values(), task_id),
                    )
                conn.commit()

                cursor.execute(
                    'SELECT id, board_id, task, due_date, notes, is_completed, completed_on FROM tasks WHERE id = %s',
                    (task_id,),
                )
                refreshed = cursor.fetchone()

        return {
            "status": "updated",
            "task": {
                "id": refreshed["id"],
                "board_id": refreshed["board_id"],
                "task": refreshed["task"],
                "due_date": _normalize_date_output(refreshed["due_date"]),
                "notes": refreshed.get("notes", ""),
                "is_completed": refreshed["is_completed"],
                "completed_on": _normalize_date_output(refreshed.get("completed_on")),
            },
        }

    result = await _run_db(_update)
    await ctx.info(f"Updated task {task_id} for {username}")
    return result


@server.tool()
async def delete_task(ctx: Context, task_id: int) -> Dict[str, Any]:
    """Delete a task regardless of completion state."""
    user_id, username = _require_user(ctx)
    services = get_services()

    def _delete() -> Dict[str, Any]:
        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT t.id, t.board_id
                       FROM tasks t
                       JOIN boards b ON t.board_id = b.id
                       WHERE t.id = %s AND b.user_id = %s''',
                    (task_id, user_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Task not found for the current user.")

                cursor.execute('DELETE FROM tasks WHERE id = %s', (task_id,))
                conn.commit()

        return {"status": "deleted", "task_id": task_id, "board_id": row["board_id"]}

    result = await _run_db(_delete)
    await ctx.info(f"Deleted task {task_id} for {username}")
    return result


@server.tool()
async def reorder_tasks(
    ctx: Context,
    board_id: str,
    ordered_task_ids: Sequence[int],
    section: str = "active",
) -> Dict[str, Any]:
    """Reorder tasks within a board section (active or completed)."""
    if section not in {"active", "completed"}:
        raise ValueError("Section must be 'active' or 'completed'.")
    if not ordered_task_ids:
        raise ValueError("ordered_task_ids cannot be empty.")

    user_id, username = _require_user(ctx)
    services = get_services()
    is_completed = section == "completed"

    def _reorder() -> Dict[str, Any]:
        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT id FROM boards WHERE id = %s AND user_id = %s',
                    (board_id, user_id),
                )
                if cursor.fetchone() is None:
                    raise ValueError("Board not found for the current user.")

                cursor.execute(
                    '''SELECT t.id
                       FROM tasks t
                       JOIN boards b ON t.board_id = b.id
                       WHERE t.board_id = %s AND b.user_id = %s AND t.is_completed = %s
                       ORDER BY t.position, t.created_at''',
                    (board_id, user_id, is_completed),
                )
                existing_ids = [row["id"] for row in cursor.fetchall()]

                if set(existing_ids) != set(int(tid) for tid in ordered_task_ids):
                    raise ValueError("Ordered IDs must match the current set of tasks in that section.")

                for position, task_id in enumerate(ordered_task_ids, start=1):
                    cursor.execute('UPDATE tasks SET position = %s WHERE id = %s', (position, task_id))

                conn.commit()

        return {"status": "reordered", "board_id": board_id, "section": section, "count": len(ordered_task_ids)}

    result = await _run_db(_reorder)
    await ctx.info(f"Reordered {len(ordered_task_ids)} {section} tasks on board {board_id} for {username}")
    return result


@server.tool()
async def restore_archived_task(ctx: Context, archived_task_id: int) -> Dict[str, Any]:
    """Restore an archived task back into its original board as an active task."""
    user_id, username = _require_user(ctx)
    services = get_services()

    def _restore() -> Dict[str, Any]:
        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT * FROM archived_tasks WHERE id = %s AND user_id = %s',
                    (archived_task_id, user_id),
                )
                archived = cursor.fetchone()
                if archived is None:
                    raise ValueError("Archived task not found for the current user.")

                board_id = archived["board_id"]

                cursor.execute('SELECT id FROM boards WHERE id = %s AND user_id = %s', (board_id, user_id))
                if cursor.fetchone() is None:
                    raise ValueError("The archived task references a board that no longer exists.")

                cursor.execute(
                    'SELECT COUNT(*) AS count FROM tasks WHERE board_id = %s AND is_completed = FALSE',
                    (board_id,),
                )
                if cursor.fetchone()["count"] >= ArchiveManager.MAX_TASKS_PER_BOARD:
                    raise ValueError("Board already has the maximum number of active tasks.")

                cursor.execute(
                    'SELECT COALESCE(MAX(position), 0) AS pos FROM tasks WHERE board_id = %s AND is_completed = FALSE',
                    (board_id,),
                )
                next_position = (cursor.fetchone()["pos"] or 0) + 1

                cursor.execute(
                    '''INSERT INTO tasks (board_id, task, due_date, notes, position, is_completed, completed_on)
                       VALUES (%s, %s, %s, %s, %s, FALSE, NULL)
                       RETURNING id''',
                    (
                        board_id,
                        archived.get("task"),
                        archived.get("due_date"),
                        archived.get("notes", ""),
                        next_position,
                    ),
                )
                new_task_id = cursor.fetchone()["id"]

                cursor.execute('DELETE FROM archived_tasks WHERE id = %s', (archived_task_id,))
                conn.commit()

        return {"status": "restored", "task_id": new_task_id, "board_id": board_id}

    result = await _run_db(_restore)
    await ctx.info(f"Restored archived task {archived_task_id} for {username}")
    return result


@server.tool()
async def bulk_complete_tasks(ctx: Context, board_id: str, task_ids: Sequence[int]) -> Dict[str, Any]:
    """Complete multiple tasks in a single request."""
    if not task_ids:
        raise ValueError("task_ids cannot be empty.")

    user_id, username = _require_user(ctx)
    services = get_services()

    def _bulk() -> Dict[str, Any]:
        completed = 0
        skipped: List[int] = []
        archived_total = 0
        today_str = datetime.now().strftime("%Y-%m-%d")

        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id FROM boards WHERE id = %s AND user_id = %s', (board_id, user_id))
                if cursor.fetchone() is None:
                    raise ValueError("Board not found for the current user.")

                for task_id in task_ids:
                    cursor.execute(
                        '''SELECT t.id FROM tasks t
                           JOIN boards b ON t.board_id = b.id
                           WHERE t.id = %s AND t.board_id = %s AND b.user_id = %s AND t.is_completed = FALSE''',
                        (task_id, board_id, user_id),
                    )
                    if cursor.fetchone() is None:
                        skipped.append(int(task_id))
                        continue

                    cursor.execute(
                        'UPDATE tasks SET is_completed = TRUE, completed_on = %s WHERE id = %s',
                        (today_str, task_id),
                    )
                    completed += 1

                archived_total = services.archive.archive_overflow_tasks(board_id, user_id, conn=conn)
                conn.commit()

        return {
            "status": "completed",
            "board_id": board_id,
            "requested": len(task_ids),
            "completed": completed,
            "archived": archived_total,
            "skipped": skipped,
        }

    result = await _run_db(_bulk)
    await ctx.info(
        f"Bulk-completed {result['completed']} tasks on board {board_id} for {username}; skipped {len(result['skipped'])}."
    )
    return result


@server.tool()
async def bulk_delete_tasks(ctx: Context, board_id: str, task_ids: Sequence[int]) -> Dict[str, Any]:
    """Delete multiple tasks from a board."""
    if not task_ids:
        raise ValueError("task_ids cannot be empty.")

    user_id, username = _require_user(ctx)
    services = get_services()

    def _bulk_delete() -> Dict[str, Any]:
        deleted = 0
        skipped: List[int] = []

        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id FROM boards WHERE id = %s AND user_id = %s', (board_id, user_id))
                if cursor.fetchone() is None:
                    raise ValueError("Board not found for the current user.")

                for task_id in task_ids:
                    cursor.execute(
                        '''SELECT t.id FROM tasks t
                           JOIN boards b ON t.board_id = b.id
                           WHERE t.id = %s AND t.board_id = %s AND b.user_id = %s''',
                        (task_id, board_id, user_id),
                    )
                    if cursor.fetchone() is None:
                        skipped.append(int(task_id))
                        continue

                    cursor.execute('DELETE FROM tasks WHERE id = %s', (task_id,))
                    deleted += 1

                conn.commit()

        return {
            "status": "deleted",
            "board_id": board_id,
            "requested": len(task_ids),
            "deleted": deleted,
            "skipped": skipped,
        }

    result = await _run_db(_bulk_delete)
    await ctx.info(
        f"Bulk-deleted {result['deleted']} tasks on board {board_id} for {username}; skipped {len(result['skipped'])}."
    )
    return result


@server.tool()
async def move_task_between_boards(ctx: Context, task_id: int, target_board_id: str) -> Dict[str, Any]:
    """Move a task to another board, preserving completion state."""
    user_id, username = _require_user(ctx)
    services = get_services()

    def _move() -> Dict[str, Any]:
        with services.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''SELECT t.id, t.board_id, t.is_completed
                       FROM tasks t
                       JOIN boards b ON t.board_id = b.id
                       WHERE t.id = %s AND b.user_id = %s''',
                    (task_id, user_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Task not found for the current user.")

                source_board = row["board_id"]
                if source_board == target_board_id:
                    return {"status": "unchanged", "task_id": task_id, "board_id": target_board_id}

                cursor.execute('SELECT id FROM boards WHERE id = %s AND user_id = %s', (target_board_id, user_id))
                if cursor.fetchone() is None:
                    raise ValueError("Target board not found for the current user.")

                if not row["is_completed"]:
                    cursor.execute(
                        'SELECT COUNT(*) AS count FROM tasks WHERE board_id = %s AND is_completed = FALSE',
                        (target_board_id,),
                    )
                    if cursor.fetchone()["count"] >= 10:
                        raise ValueError("Target board already has 10 active tasks.")

                cursor.execute(
                    'SELECT COALESCE(MAX(position), 0) AS pos FROM tasks WHERE board_id = %s AND is_completed = %s',
                    (target_board_id, row["is_completed"]),
                )
                next_position = (cursor.fetchone()["pos"] or 0) + 1

                cursor.execute(
                    'UPDATE tasks SET board_id = %s, position = %s WHERE id = %s',
                    (target_board_id, next_position, task_id),
                )
                conn.commit()

        return {
            "status": "moved",
            "task_id": task_id,
            "from": source_board,
            "to": target_board_id,
            "is_completed": row["is_completed"],
        }

    result = await _run_db(_move)
    await ctx.info(
        f"Moved task {task_id} from board {result['from']} to {result['to']} for {username}"
    )
    return result


@server.tool()
async def generate_board_screenshot(ctx: Context, board_id: str) -> Dict[str, Any]:
    """Produce an ASCII representation of a board."""
    payload = await list_tasks(ctx=ctx, board_id=board_id, include_completed=True)
    ascii_art = _format_board_ascii(payload)
    return {"board_id": board_id, "ascii": ascii_art}


@server.tool()
async def export_board_data(ctx: Context, board_id: str) -> Dict[str, Any]:
    """Export board data as JSON and CSV strings."""
    payload = await list_tasks(ctx=ctx, board_id=board_id, include_completed=True)
    json_data = json.dumps(payload, indent=2, default=str)
    csv_data = _build_board_csv(payload)
    return {"board_id": board_id, "json": json_data, "csv": csv_data}


@server.tool()
async def generate_board_summary(ctx: Context, board_id: str) -> Dict[str, Any]:
    """Produce a textual summary describing board health."""
    payload = await list_tasks(ctx=ctx, board_id=board_id, include_completed=True)
    summary = _summarize_board(payload)
    return {"board_id": board_id, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description="TSKMNGR MCP server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="Transport protocol to use.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE or HTTP transports.")
    parser.add_argument("--port", type=int, default=8765, help="Port for SSE or HTTP transports.")
    parser.add_argument("--mount-path", default="/", help="Mount path for SSE transport.")
    args = parser.parse_args()

    # Configure server for non-stdio transports
    if args.transport != "stdio":
        server.settings.host = args.host
        server.settings.port = args.port

    mount = args.mount_path if args.transport == "sse" else None
    server.run(args.transport, mount_path=mount)


if __name__ == "__main__":
    main()
