from flask import Flask, render_template_string, request, redirect, url_for
import json
import os
import re
import uuid
from datetime import datetime

app = Flask(__name__)

BOARDS_FILE = "boards.json"

def load_boards():
    default_data = {
        "boards": {
            str(uuid.uuid4()): {
                "header": "Your 10 Tasks",
                "active": [],
                "completed": []
            }
        }
    }
    if not os.path.exists(BOARDS_FILE):
        with open(BOARDS_FILE, "w") as f:
            json.dump(default_data, f)
    
    with open(BOARDS_FILE, "r") as f:
        data = json.load(f)
    
    # Migrate from old single-board format
    if "boards" not in data:
        board_id = str(uuid.uuid4())
        old_data = data
        data = {
            "boards": {
                board_id: {
                    "header": old_data.get("header", "Your 10 Tasks"),
                    "active": old_data.get("active", []),
                    "completed": old_data.get("completed", [])
                }
            }
        }
        with open(BOARDS_FILE, "w") as f:
            json.dump(data, f)
    
    # Ensure all tasks have notes field
    for board in data["boards"].values():
        for section in ["active", "completed"]:
            for task in board.get(section, []):
                if "notes" not in task:
                    task["notes"] = ""
    
    return data

def save_boards(data):
    with open(BOARDS_FILE, "w") as f:
        json.dump(data, f)

def linkify(text):
    if not text:
        return ""
    text = re.sub(
        r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
        r'<a href="mailto:\1">\1</a>', text
    )
    text = re.sub(
        r'(https?://[^\s]+)',
        r'<a href="\1" target="_blank">\1</a>', text
    )
    return text

@app.route("/", methods=["GET", "POST"])
def index():
    data = load_boards()
    boards = data.get("boards", {})
    
    # Add linkified notes to all tasks
    for board in boards.values():
        for task in board.get("active", []):
            task["notes_html"] = linkify(task.get("notes", ""))
        for task in board.get("completed", []):
            task["notes_html"] = linkify(task.get("notes", ""))
    
    # Get today's date for default date input
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    return render_template_string(TEMPLATE, boards=boards, today_date=today_date)

@app.route("/add_board", methods=["POST"])
def add_board():
    data = load_boards()
    if len(data["boards"]) < 4:
        new_board_id = str(uuid.uuid4())
        data["boards"][new_board_id] = {
            "header": f"Board {len(data['boards']) + 1}",
            "active": [],
            "completed": []
        }
        save_boards(data)
    return redirect(url_for("index"))

@app.route("/remove_board/<board_id>", methods=["POST"])
def remove_board(board_id):
    data = load_boards()
    if board_id in data["boards"] and len(data["boards"]) > 1:
        del data["boards"][board_id]
        save_boards(data)
    return redirect(url_for("index"))

@app.route("/edit_header/<board_id>", methods=["POST"])
def edit_header(board_id):
    data = load_boards()
    if board_id in data["boards"]:
        new_header = request.form.get("header_text", "").strip()
        if new_header:
            data["boards"][board_id]["header"] = new_header
            save_boards(data)
    return redirect(url_for("index"))

@app.route("/add_task/<board_id>", methods=["POST"])
def add_task(board_id):
    data = load_boards()
    if board_id in data["boards"]:
        board = data["boards"][board_id]
        new_task = request.form.get("task", "").strip()
        due_date = request.form.get("date", "")
        notes = request.form.get("notes", "").strip()
        
        if new_task and due_date and len(board["active"]) < 10:
            board["active"].append({
                "task": new_task,
                "date": due_date,
                "notes": notes
            })
            save_boards(data)
    return redirect(url_for("index"))

@app.route("/edit_task/<board_id>/<int:task_idx>", methods=["POST"])
def edit_task(board_id, task_idx):
    data = load_boards()
    if board_id in data["boards"]:
        board = data["boards"][board_id]
        active_tasks = board.get("active", [])
        
        new_name = request.form.get("edit_task", "").strip()
        new_date = request.form.get("edit_date", "").strip()
        new_notes = request.form.get("edit_notes", "").strip()
        
        if 0 <= task_idx < len(active_tasks) and new_name and new_date:
            active_tasks[task_idx]["task"] = new_name
            active_tasks[task_idx]["date"] = new_date
            active_tasks[task_idx]["notes"] = new_notes
            save_boards(data)
    return redirect(url_for("index"))

@app.route("/complete/<board_id>/<int:task_idx>", methods=["POST"])
def complete(board_id, task_idx):
    data = load_boards()
    if board_id in data["boards"]:
        board = data["boards"][board_id]
        active_tasks = board.get("active", [])
        completed_tasks = board.get("completed", [])
        
        if 0 <= task_idx < len(active_tasks):
            task = active_tasks.pop(task_idx)
            task["completed_on"] = datetime.now().strftime("%Y-%m-%d")
            completed_tasks.insert(0, task)
            save_boards(data)
    return redirect(url_for("index"))

@app.route("/uncomplete/<board_id>/<int:task_idx>", methods=["POST"])
def uncomplete(board_id, task_idx):
    data = load_boards()
    if board_id in data["boards"]:
        board = data["boards"][board_id]
        active_tasks = board.get("active", [])
        completed_tasks = board.get("completed", [])
        
        if 0 <= task_idx < len(completed_tasks):
            task = completed_tasks.pop(task_idx)
            task.pop("completed_on", None)
            if len(active_tasks) < 10:
                active_tasks.append(task)
            else:
                completed_tasks.insert(task_idx, task)
            save_boards(data)
    return redirect(url_for("index"))

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Board Task Manager</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
        body { 
            font-family: system-ui, sans-serif; 
            background: #f5f5f5; 
            margin: 0; 
            padding: 20px;
        }
        .main-container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .boards-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }
        .board-container {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
            min-height: 500px;
            position: relative;
        }
        .board-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        .board-title {
            font-size: 1.5rem;
            font-weight: bold;
            color: #333;
            margin: 0;
        }
        .board-actions {
            display: flex;
            gap: 8px;
        }
        .remove-board {
            background: #ff4757;
            color: white;
            border: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .edit-header-btn {
            background: #ffd900;
            color: #333;
            border: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .add-board-container {
            display: flex;
            justify-content: center;
            margin-top: 20px;
        }
        .add-board {
            background: #4CAF50;
            color: white;
            border: none;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            font-size: 24px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        .add-board:hover {
            background: #45a049;
        }
        .add-task-form {
            display: flex;
            gap: 6px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .add-task-form input[type="text"], .add-task-form input[type="date"] {
            flex: 1;
            min-width: 80px;
            padding: 6px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 12px;
        }
        .add-task-form input[name="notes"] {
            flex: 2;
            min-width: 100px;
        }
        button {
            background: #006cff;
            color: #fff;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }
        button.completed { background: #17be72; }
        button.uncomplete { background: #e0a900; color: #222; }
        button.edit-btn { background: #ffd900; color: #333; }
        button.cancel-btn { background: #bbb; color: #333; }
        ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        li {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            padding: 6px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 13px;
        }
        .task-num {
            color: #888;
            width: 15px;
            font-size: 12px;
        }
        .task-content {
            flex: 1;
            min-width: 0;
        }
        .task-name {
            font-weight: 500;
            margin-bottom: 2px;
        }
        .task-date {
            color: #666;
            font-size: 11px;
        }
        .task-notes {
            color: #777;
            font-size: 11px;
            margin-top: 2px;
            word-break: break-word;
        }
        .task-actions {
            display: flex;
            gap: 4px;
            margin-left: auto;
        }
        .task-actions button {
            padding: 3px 6px;
            font-size: 10px;
        }
        .section-title {
            font-size: 14px;
            font-weight: bold;
            color: #006cff;
            margin: 15px 0 8px 0;
        }
        .empty-list {
            color: #aaa;
            font-style: italic;
            padding: 10px 0;
        }
        .edit-form {
            display: flex;
            gap: 4px;
            flex: 1;
            align-items: flex-start;
        }
        .edit-form input {
            padding: 3px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 11px;
        }
        .completed-date {
            color: #1b8a4c;
            font-size: 10px;
            margin-left: 8px;
        }
        .header-edit-form {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .header-edit-form input {
            font-size: 1.2rem;
            font-weight: bold;
            padding: 4px 8px;
            border: 2px solid #ffd900;
            border-radius: 6px;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="boards-grid">
            {% for board_id, board in boards.items() %}
            <div class="board-container">
                <div class="board-header">
                    {% if request.args.get('edit_header') == board_id %}
                    <form method="post" action="{{ url_for('edit_header', board_id=board_id) }}" class="header-edit-form">
                        <input type="text" name="header_text" value="{{ board['header'] }}" maxlength="48" autofocus>
                        <button type="submit">Save</button>
                        <a href="{{ url_for('index') }}"><button type="button" class="cancel-btn">Cancel</button></a>
                    </form>
                    {% else %}
                    <h2 class="board-title">{{ board['header'] }}</h2>
                    <div class="board-actions">
                        <a href="?edit_header={{ board_id }}">
                            <button type="button" class="edit-header-btn" title="Edit header">✎</button>
                        </a>
                        {% if boards|length > 1 %}
                        <form method="post" action="{{ url_for('remove_board', board_id=board_id) }}" style="margin:0;">
                            <button type="submit" class="remove-board" title="Remove board" onclick="return confirm('Remove this board?')">×</button>
                        </form>
                        {% endif %}
                    </div>
                    {% endif %}
                </div>

                <form method="post" action="{{ url_for('add_task', board_id=board_id) }}" class="add-task-form">
                    <input type="text" name="task" placeholder="New task" required maxlength="64">
                    <input type="date" name="date" value="{{ today_date }}" required>
                    <input type="text" name="notes" placeholder="Notes" maxlength="256">
                    <button type="submit">Add</button>
                </form>

                <div class="section-title">Active Tasks</div>
                <ul>
                    {% for task in board['active'] %}
                    <li>
                        <span class="task-num">{{ loop.index }}.</span>
                        {% if request.args.get('edit') == board_id ~ '_' ~ loop.index0 %}
                        <form method="post" action="{{ url_for('edit_task', board_id=board_id, task_idx=loop.index0) }}" class="edit-form">
                            <input type="text" name="edit_task" value="{{ task['task'] }}" required maxlength="64" style="flex:2;">
                            <input type="date" name="edit_date" value="{{ task['date'] }}" required style="flex:1;">
                            <input type="text" name="edit_notes" value="{{ task['notes'] }}" maxlength="256" style="flex:2;">
                            <button type="submit" class="completed">Save</button>
                            <a href="{{ url_for('index') }}"><button type="button" class="cancel-btn">Cancel</button></a>
                        </form>
                        {% else %}
                        <div class="task-content">
                            <div class="task-name">{{ task['task'] }}</div>
                            <div class="task-date">Due: {{ task['date'] }}</div>
                            {% if task['notes'] %}
                            <div class="task-notes">{{ task['notes_html']|safe }}</div>
                            {% endif %}
                        </div>
                        <div class="task-actions">
                            <a href="?edit={{ board_id }}_{{ loop.index0 }}">
                                <button type="button" class="edit-btn">Edit</button>
                            </a>
                            <form method="post" action="{{ url_for('complete', board_id=board_id, task_idx=loop.index0) }}" style="margin:0;">
                                <button type="submit" class="completed">Done</button>
                            </form>
                        </div>
                        {% endif %}
                    </li>
                    {% endfor %}
                    {% if board['active']|length == 0 %}
                    <li class="empty-list">No active tasks.</li>
                    {% endif %}
                </ul>

                <div class="section-title">Completed Tasks</div>
                <ul>
                    {% for task in board['completed'] %}
                    <li>
                        <span class="task-num">✓</span>
                        <div class="task-content">
                            <div class="task-name">{{ task['task'] }}</div>
                            <div class="task-date">Due: {{ task['date'] }}</div>
                            {% if task['notes'] %}
                            <div class="task-notes">{{ task['notes_html']|safe }}</div>
                            {% endif %}
                            <div class="completed-date">Completed: {{ task['completed_on'] }}</div>
                        </div>
                        <div class="task-actions">
                            <form method="post" action="{{ url_for('uncomplete', board_id=board_id, task_idx=loop.index0) }}" style="margin:0;">
                                <button type="submit" class="uncomplete">Undo</button>
                            </form>
                        </div>
                    </li>
                    {% endfor %}
                    {% if board['completed']|length == 0 %}
                    <li class="empty-list">No completed tasks yet.</li>
                    {% endif %}
                </ul>
            </div>
            {% endfor %}
        </div>

        {% if boards|length < 4 %}
        <div class="add-board-container">
            <form method="post" action="{{ url_for('add_board') }}">
                <button type="submit" class="add-board" title="Add new board">+</button>
            </form>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
