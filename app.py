from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets
from datetime import datetime, timedelta
import jwt
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Session configuration
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SECURE'] = True  # Use HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS
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
    # Ensure database exists before connecting
    if not os.path.exists('users.db'):
        init_db()
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

# JWT token functions
def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24)  # Token expires in 24 hours
    }
    return jwt.encode(payload, app.secret_key, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session first
        if 'user_id' in session and session.get('user_id'):
            return f(*args, **kwargs)
        
        # Check Authorization header for API requests
        token = request.headers.get('Authorization')
        if token:
            token = token.replace('Bearer ', '')
            user_id = verify_token(token)
            if user_id:
                return f(*args, **kwargs)
        
        # If it's an API request, return JSON error
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Authentication required'}), 401
        
        # Otherwise redirect to login
        return redirect(url_for('login'))
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
        # Try to reinitialize database if there's an error
        init_db()
        return None

def create_user(username, password):
    try:
        conn = get_db_connection()
        password_hash = generate_password_hash(password)
        cursor = conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                             (username, password_hash))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"User creation error: {e}")
        # Try to reinitialize database if there's an error
        init_db()
        return None

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if request.is_json:
            # API endpoint for AJAX requests
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            
            user = authenticate_user(username, password)
            if user:
                # Set session data
                session['user_id'] = user['id']
                session['username'] = user['username']
                session.permanent = True  # Make session permanent
                
                token = generate_token(user['id'])
                return jsonify({
                    'success': True,
                    'token': token,
                    'message': 'Login successful',
                    'redirect': '/dashboard'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Invalid username or password'
                }), 401
        else:
            # Form submission
            username = request.form['username']
            password = request.form['password']
            
            user = authenticate_user(username, password)
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session.permanent = True  # Make session permanent
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    user = authenticate_user(username, password)
    if user:
        token = generate_token(user['id'])
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username']
            }
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/register', methods=['POST'])
def register():
    if request.is_json:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password required'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
        
        user_id = create_user(username, password)
        if user_id:
            token = generate_token(user_id)
            return jsonify({
                'success': True,
                'token': token,
                'message': 'User created successfully'
            })
        else:
            return jsonify({'success': False, 'message': 'Username already exists'}), 400

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # This would be your main task manager interface
    user_id = session.get('user_id')
    username = session.get('username', 'User')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TSKMNGR Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
            .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .logout-btn {{ background: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Welcome to TSKMNGR Dashboard</h1>
            <p>Hello, {username}! (User ID: {user_id})</p>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
        
        <div>
            <h2>Your Task Manager</h2>
            <p>Your task manager interface would go here.</p>
            <p>Session data: {dict(session)}</p>
        </div>
    </body>
    </html>
    """

@app.route('/api/user')
@login_required
def api_user():
    return jsonify({
        'user_id': session.get('user_id'),
        'username': session.get('username')
    })

# Template for login page (save as templates/login.html)
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>TSKMNGR Login</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
        input { width: 100%; padding: 10px; margin: 10px 0; }
        button { width: 100%; padding: 10px; background: #007bff; color: white; border: none; }
        .error { color: red; margin: 10px 0; }
    </style>
</head>
<body>
    <h2>TSKMNGR Login</h2>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    <form method="post">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>
    <p>Default credentials: admin / admin123</p>
</body>
</html>
'''

if __name__ == '__main__':
    # Create templates directory and login.html if they don't exist
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    with open('templates/login.html', 'w') as f:
        f.write(LOGIN_TEMPLATE)
    
    # Initialize database
    init_db()
    
    # Get port from environment variable (for Render deployment)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=port)

# Initialize database when app starts (for production)
try:
    init_db()
except Exception as e:
    print(f"Database initialization error: {e}")
    # Database will be initialized on first connection attempt
