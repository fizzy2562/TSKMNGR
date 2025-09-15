from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from functools import wraps
import os
import re
import uuid
import secrets
from datetime import datetime, timedelta

# Import our modules
from database import Database
from templates import LOGIN_TEMPLATE, REGISTER_TEMPLATE, DASHBOARD_TEMPLATE

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Session configuration
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize database
db = Database()

# Helper functions
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

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
        
        user = db.authenticate_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error='Invalid username or password')
    
    return render_template_string(LOGIN_TEMPLATE)

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
        
        # Create new user
        user_id = db.create_user(username, password)
        
        if user_id:
            # Auto-login after registration
            session['user_id'] = user_id
            session['username'] = username
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(REGISTER_TEMPLATE, error='Username already taken')
    
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
    
    # Get boards from database
    boards = db.get_user_boards(user_id)
    
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
    
    if db.count_user_boards(user_id) < 4:
        new_board_id = str(uuid.uuid4())
        board_count = db.count_user_boards(user_id)
        db.create_board(user_id, f"Board {board_count + 1}", new_board_id)
    
    return redirect(url_for("dashboard"))

@app.route("/remove_board/<board_id>", methods=["POST"])
@login_required
def remove_board(board_id):
    user_id = session.get('user_id')
    db.delete_board(board_id, user_id)
    return redirect(url_for("dashboard"))

@app.route("/edit_header/<board_id>", methods=["POST"])
@login_required
def edit_header(board_id):
    user_id = session.get('user_id')
    new_header = request.form.get("header_text", "").strip()
    
    if new_header:
        db.update_board_header(board_id, user_id, new_header)
    
    return redirect(url_for("dashboard"))

@app.route("/add_task/<board_id>", methods=["POST"])
@login_required
def add_task(board_id):
    user_id = session.get('user_id')
    task = request.form.get("task", "").strip()
    due_date = request.form.get("date", "")
    notes = request.form.get("notes", "").strip()
    
    if task and due_date:
        db.add_task(board_id, user_id, task, due_date, notes)
    
    return redirect(url_for("dashboard"))

@app.route("/edit_task/<board_id>/<int:task_idx>", methods=["POST"])
@login_required
def edit_task(board_id, task_idx):
    user_id = session.get('user_id')
    new_task = request.form.get("edit_task", "").strip()
    new_date = request.form.get("edit_date", "").strip()
    new_notes = request.form.get("edit_notes", "").strip()
    
    if new_task and new_date:
        db.update_task(board_id, user_id, task_idx, new_task, new_date, new_notes)
    
    return redirect(url_for("dashboard"))

@app.route("/complete/<board_id>/<int:task_idx>", methods=["POST"])
@login_required
def complete(board_id, task_idx):
    user_id = session.get('user_id')
    db.complete_task(board_id, user_id, task_idx)
    return redirect(url_for("dashboard"))

@app.route("/uncomplete/<board_id>/<int:task_id>", methods=["POST"])
@login_required
def uncomplete(board_id, task_id):
    user_id = session.get('user_id')
    db.uncomplete_task(board_id, user_id, task_id)
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    # Get port from environment variable (for deployment)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=port)
