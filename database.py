import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

class Database:
    def __init__(self):
        # Get database URL from environment variable
        self.database_url = os.environ.get('DATABASE_URL')
        
        # Handle Render's postgres:// vs postgresql:// issue
        if self.database_url and self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        
        self.init_db()
    
    def get_connection(self):
        if self.database_url:
            return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
        else:
            # Fallback to SQLite for local development
            import sqlite3
            conn = sqlite3.connect('tskmngr.db')
            conn.row_factory = sqlite3.Row
            return conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Boards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS boards (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                header TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                board_id TEXT NOT NULL,
                task TEXT NOT NULL,
                due_date DATE NOT NULL,
                notes TEXT DEFAULT '',
                is_completed BOOLEAN DEFAULT FALSE,
                completed_on DATE,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_id ON tasks(board_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(is_completed)')
        
        conn.commit()
        conn.close()
    
    # User methods
    def create_user(self, username, password):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            password_hash = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id', 
                (username, password_hash)
            )
            user_id = cursor.fetchone()['id']
            conn.commit()
            conn.close()
            
            # Create default board for new user
            import uuid
            self.create_board(user_id, "Your Tasks", str(uuid.uuid4()))
            
            return user_id
        except psycopg2.IntegrityError:
            return None
    
    def authenticate_user(self, username, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            return user
        return None
    
    # Board methods
    def get_user_boards(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM boards WHERE user_id = %s ORDER BY position, created_at',
            (user_id,)
        )
        boards = cursor.fetchall()
        
        result = {}
        for board in boards:
            board_data = {
                'header': board['header'],
                'active': [],
                'completed': []
            }
            
            # Get tasks for this board
            cursor.execute(
                '''SELECT * FROM tasks WHERE board_id = %s 
                   ORDER BY is_completed, position, created_at''',
                (board['id'],)
            )
            tasks = cursor.fetchall()
            
            for task in tasks:
                task_data = {
                    'task': task['task'],
                    'date': task['due_date'].strftime('%Y-%m-%d') if hasattr(task['due_date'], 'strftime') else task['due_date'],
                    'notes': task['notes'] or ''
                }
                
                if task['is_completed']:
                    task_data['completed_on'] = task['completed_on'].strftime('%Y-%m-%d') if task['completed_on'] else ''
                    board_data['completed'].append(task_data)
                else:
                    board_data['active'].append(task_data)
            
            result[board['id']] = board_data
        
        conn.close()
        return result
    
    def create_board(self, user_id, header, board_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get the next position
        cursor.execute(
            'SELECT MAX(position) as max_pos FROM boards WHERE user_id = %s',
            (user_id,)
        )
        max_pos = cursor.fetchone()
        position = (max_pos['max_pos'] or 0) + 1 if max_pos else 1
        
        cursor.execute(
            'INSERT INTO boards (id, user_id, header, position) VALUES (%s, %s, %s, %s)',
            (board_id, user_id, header, position)
        )
        conn.commit()
        conn.close()
    
    def update_board_header(self, board_id, user_id, new_header):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE boards SET header = %s WHERE id = %s AND user_id = %s',
            (new_header, board_id, user_id)
        )
        conn.commit()
        conn.close()
    
    def delete_board(self, board_id, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if user owns the board and has more than one board
        cursor.execute(
            'SELECT COUNT(*) as count FROM boards WHERE user_id = %s',
            (user_id,)
        )
        board_count = cursor.fetchone()['count']
        
        if board_count > 1:
            cursor.execute(
                'DELETE FROM boards WHERE id = %s AND user_id = %s',
                (board_id, user_id)
            )
            conn.commit()
        
        conn.close()
    
    def count_user_boards(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) as count FROM boards WHERE user_id = %s',
            (user_id,)
        )
        count = cursor.fetchone()['count']
        conn.close()
        return count
    
    # Task methods
    def add_task(self, board_id, user_id, task, due_date, notes=''):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Verify user owns the board
        cursor.execute(
            'SELECT id FROM boards WHERE id = %s AND user_id = %s',
            (board_id, user_id)
        )
        board = cursor.fetchone()
        
        if board:
            # Count active tasks
            cursor.execute(
                'SELECT COUNT(*) as count FROM tasks WHERE board_id = %s AND is_completed = FALSE',
                (board_id,)
            )
            active_count = cursor.fetchone()['count']
            
            if active_count < 10:  # Limit of 10 active tasks
                # Get next position
                cursor.execute(
                    'SELECT MAX(position) as max_pos FROM tasks WHERE board_id = %s AND is_completed = FALSE',
                    (board_id,)
                )
                max_pos = cursor.fetchone()
                position = (max_pos['max_pos'] or 0) + 1 if max_pos else 1
                
                cursor.execute(
                    '''INSERT INTO tasks (board_id, task, due_date, notes, position) 
                       VALUES (%s, %s, %s, %s, %s)''',
                    (board_id, task, due_date, notes, position)
                )
                conn.commit()
        
        conn.close()
    
    def update_task(self, board_id, user_id, task_idx, new_task, new_date, new_notes):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get the task at the specified index
        cursor.execute(
            '''SELECT t.id FROM tasks t 
               JOIN boards b ON t.board_id = b.id 
               WHERE b.id = %s AND b.user_id = %s AND t.is_completed = FALSE 
               ORDER BY t.position, t.created_at 
               LIMIT 1 OFFSET %s''',
            (board_id, user_id, task_idx)
        )
        task = cursor.fetchone()
        
        if task:
            cursor.execute(
                'UPDATE tasks SET task = %s, due_date = %s, notes = %s WHERE id = %s',
                (new_task, new_date, new_notes, task['id'])
            )
            conn.commit()
        
        conn.close()
    
    def complete_task(self, board_id, user_id, task_idx):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get the task at the specified index
        cursor.execute(
            '''SELECT t.id FROM tasks t 
               JOIN boards b ON t.board_id = b.id 
               WHERE b.id = %s AND b.user_id = %s AND t.is_completed = FALSE 
               ORDER BY t.position, t.created_at 
               LIMIT 1 OFFSET %s''',
            (board_id, user_id, task_idx)
        )
        task = cursor.fetchone()
        
        if task:
            cursor.execute(
                'UPDATE tasks SET is_completed = TRUE, completed_on = %s WHERE id = %s',
                (datetime.now().strftime("%Y-%m-%d"), task['id'])
            )
            conn.commit()
        
        conn.close()
    
    def uncomplete_task(self, board_id, user_id, task_idx):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if we can uncomplete (less than 10 active tasks)
        cursor.execute(
            'SELECT COUNT(*) as count FROM tasks WHERE board_id = %s AND is_completed = FALSE',
            (board_id,)
        )
        active_count = cursor.fetchone()['count']
        
        if active_count < 10:
            # Get the completed task at the specified index
            cursor.execute(
                '''SELECT t.id FROM tasks t 
                   JOIN boards b ON t.board_id = b.id 
                   WHERE b.id = %s AND b.user_id = %s AND t.is_completed = TRUE 
                   ORDER BY t.completed_on DESC, t.created_at DESC 
                   LIMIT 1 OFFSET %s''',
                (board_id, user_id, task_idx)
            )
            task = cursor.fetchone()
            
            if task:
                cursor.execute(
                    'UPDATE tasks SET is_completed = FALSE, completed_on = NULL WHERE id = %s',
                    (task['id'],)
                )
                conn.commit()
        
        conn.close()
