from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import os
import re
import uuid
import sqlite3
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Session configuration
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create default admin user if it doesn't exist
    cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        admin_password = generate_password_hash('admin123')
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                      ('admin', admin_password))
    
    conn.commit()
    conn.close()

def get_db_connection():
    if not os.path.exists('users.db'):
        init_db()
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# User authentication functions
def authenticate_user(username, password):
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            return user
        return None
    except Exception as e:
        print(f"Authentication error: {e}")
        init_db()
        return None

# Task Manager Functions
def get_boards_file(user_id):
    return f"boards_user_{user_id}.json"

def load_boards(user_id):
    boards_file = get_boards_file(user_id)
    default_data = {
        "boards": {
            str(uuid.uuid4()): {
                "header": "Your 10 Tasks",
                "active": [],
                "completed": []
            }
        }
    }
    
    if not os.path.exists(boards_file):
        with open(boards_file, "w") as f:
            json.dump(default_data, f)
    
    with open(boards_file, "r") as f:
        data = json.load(f)
    
    # Ensure all tasks have notes field
    for board in data["boards"].values():
        for section in ["active", "completed"]:
            for task in board.get(section, []):
                if "notes" not in task:
                    task["notes"] = ""
    
    return data

def save_boards(user_id, data):
    boards_file = get_boards_file(user_id)
    with open(boards_file, "w") as f:
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

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = authenticate_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error='Invalid username or password')
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    user = authenticate_user(username, password)
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session.permanent = True
        return jsonify({
            'success': True,
            'message': 'Login successful'
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not username or not password:
            return render_template_string(REGISTER_TEMPLATE, error='Username and password are required')
        
        if len(username) < 3:
            return render_template_string(REGISTER_TEMPLATE, error='Username must be at least 3 characters')
        
        if len(password) < 6:
            return render_template_string(REGISTER_TEMPLATE, error='Password must be at least 6 characters')
        
        if password != confirm_password:
            return render_template_string(REGISTER_TEMPLATE, error='Passwords do not match')
        
        # Check if username already exists
        conn = get_db_connection()
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if existing_user:
            return render_template_string(REGISTER_TEMPLATE, error='Username already taken')
        
        # Create new user
        try:
            conn = get_db_connection()
            password_hash = generate_password_hash(password)
            cursor = conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                                 (username, password_hash))
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Auto-login after registration
            session['user_id'] = user_id
            session['username'] = username
            session.permanent = True
            
            return redirect(url_for('dashboard'))
        except Exception as e:
            return render_template_string(REGISTER_TEMPLATE, error='Registration failed. Please try again.')
    
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get('user_id')
    username = session.get('username')
    data = load_boards(user_id)
    boards = data.get("boards", {})
    
    # Add linkified notes to all tasks
    for board in boards.values():
        for task in board.get("active", []):
            task["notes_html"] = linkify(task.get("notes", ""))
        for task in board.get("completed", []):
            task["notes_html"] = linkify(task.get("notes", ""))
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                boards=boards, 
                                today_date=today_date,
                                username=username)

@app.route("/add_board", methods=["POST"])
@login_required
def add_board():
    user_id = session.get('user_id')
    data = load_boards(user_id)
    if len(data["boards"]) < 4:
        new_board_id = str(uuid.uuid4())
        data["boards"][new_board_id] = {
            "header": f"Board {len(data['boards']) + 1}",
            "active": [],
            "completed": []
        }
        save_boards(user_id, data)
    return redirect(url_for("dashboard"))

@app.route("/remove_board/<board_id>", methods=["POST"])
@login_required
def remove_board(board_id):
    user_id = session.get('user_id')
    data = load_boards(user_id)
    if board_id in data["boards"] and len(data["boards"]) > 1:
        del data["boards"][board_id]
        save_boards(user_id, data)
    return redirect(url_for("dashboard"))

@app.route("/edit_header/<board_id>", methods=["POST"])
@login_required
def edit_header(board_id):
    user_id = session.get('user_id')
    data = load_boards(user_id)
    if board_id in data["boards"]:
        new_header = request.form.get("header_text", "").strip()
        if new_header:
            data["boards"][board_id]["header"] = new_header
            save_boards(user_id, data)
    return redirect(url_for("dashboard"))

@app.route("/add_task/<board_id>", methods=["POST"])
@login_required
def add_task(board_id):
    user_id = session.get('user_id')
    data = load_boards(user_id)
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
            save_boards(user_id, data)
    return redirect(url_for("dashboard"))

@app.route("/edit_task/<board_id>/<int:task_idx>", methods=["POST"])
@login_required
def edit_task(board_id, task_idx):
    user_id = session.get('user_id')
    data = load_boards(user_id)
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
            save_boards(user_id, data)
    return redirect(url_for("dashboard"))

@app.route("/complete/<board_id>/<int:task_idx>", methods=["POST"])
@login_required
def complete(board_id, task_idx):
    user_id = session.get('user_id')
    data = load_boards(user_id)
    if board_id in data["boards"]:
        board = data["boards"][board_id]
        active_tasks = board.get("active", [])
        completed_tasks = board.get("completed", [])
        
        if 0 <= task_idx < len(active_tasks):
            task = active_tasks.pop(task_idx)
            task["completed_on"] = datetime.now().strftime("%Y-%m-%d")
            completed_tasks.insert(0, task)
            save_boards(user_id, data)
    return redirect(url_for("dashboard"))

@app.route("/uncomplete/<board_id>/<int:task_idx>", methods=["POST"])
@login_required
def uncomplete(board_id, task_idx):
    user_id = session.get('user_id')
    data = load_boards(user_id)
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
            save_boards(user_id, data)
    return redirect(url_for("dashboard"))

# Templates
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TSKMNGR - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            padding: 40px;
            width: 100%;
            max-width: 400px;
            position: relative;
            overflow: hidden;
        }

        .login-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo h1 {
            color: #333;
            font-size: 2.5rem;
            font-weight: 700;
            letter-spacing: -2px;
            margin-bottom: 8px;
        }

        .logo p {
            color: #666;
            font-size: 0.9rem;
            opacity: 0.8;
        }

        .form-group {
            margin-bottom: 25px;
            position: relative;
        }

        .form-group label {
            display: block;
            color: #333;
            font-weight: 500;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }

        .form-group input {
            width: 100%;
            padding: 15px 20px;
            border: 2px solid #e1e5e9;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }

        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .login-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
        }

        .error-message {
            background: #fee;
            color: #d63384;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            border: 1px solid #f8d7da;
        }

        .info {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>TSKMNGR</h1>
            <p>Task Management System</p>
        </div>

        {% if error %}
        <div class="error-message">{{ error }}</div>
        {% endif %}

        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" placeholder="Enter your username" required>
            </div>

            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter your password" required>
            </div>

            <button type="submit" class="login-btn">Sign In</button>
        </form>

        <div class="info">
            Default credentials: admin / admin123<br>
            <a href="{{ url_for('register') }}" style="color: #667eea;">Create new account</a>
        </div>
    </div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TSKMNGR - {{ username }}'s Tasks</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
        body { 
            font-family: system-ui, sans-serif; 
            background: #f5f5f5; 
            margin: 0; 
            padding: 20px;
        }
        .header-bar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header-bar h1 {
            margin: 0;
            font-size: 1.8rem;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .logout-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .logout-btn:hover {
            background: rgba(255,255,255,0.3);
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
        @media (max-width: 768px) {
            .boards-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header-bar">
        <h1>TSKMNGR</h1>
        <div class="user-info">
            <span>Welcome, {{ username }}!</span>
            <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
        </div>
    </div>

    <div class="main-container">
        <div class="boards-grid">
            {% for board_id, board in boards.items() %}
            <div class="board-container">
                <div class="board-header">
                    {% if request.args.get('edit_header') == board_id %}
                    <form method="post" action="{{ url_for('edit_header', board_id=board_id) }}" class="header-edit-form">
                        <input type="text" name="header_text" value="{{ board['header'] }}" maxlength="48" autofocus>
                        <button type="submit">Save</button>
                        <a href="{{ url_for('dashboard') }}"><button type="button" class="cancel-btn">Cancel</button></a>
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
                            <a href="{{ url_for('dashboard') }}"><button type="button" class="cancel-btn">Cancel</button></a>
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
    # Initialize database
    init_db()
    
    # Get port from environment variable (for deployment)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=port)
