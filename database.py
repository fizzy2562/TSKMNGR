import sqlite3
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Database:
    def __init__(self, db_path='tskmngr.db'):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id TEXT NOT NULL,
                task TEXT NOT NULL,
                due_date DATE NOT NULL,
                notes TEXT DEFAULT '',
                is_completed BOOLEAN DEFAULT 0,
                completed_on DATE,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_id ON tasks(board_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(is_completed)')
        
        # Create default admin user if it doesn't exist
        cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            admin_password = generate_password_hash('admin123')
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                          ('admin', admin_password))
        
        conn.commit()
        conn.close()
    
    # User methods
    def create_user(self, username, password):
        try:
            conn = self.get_connection()
            password_hash = generate_password_hash(password)
            cursor = conn.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                (username, password_hash)
            )
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Create default board for new user
            import uuid
            self.create_board(user_id, "Your Tasks", str(uuid.uuid4()))
            
            return user_id
        except sqlite3.IntegrityError:
            return None
    
    def authenticate_user(self, username, password):
        conn = self.get_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            return user
        return None
    
    # Board methods
    def get_user_boards(self, user_id):
        conn = self.get_connection()
        boards = conn.execute(
            'SELECT * FROM boards WHERE user_id = ? ORDER BY position, created_at',
            (user_id,)
        ).fetchall()
        
        result = {}
        for board in boards:
            board_data = {
                'header': board['header'],
                'active': [],
                'completed': []
            }
            
            # Get tasks for this board
            tasks = conn.execute(
                '''SELECT * FROM tasks WHERE board_id = ? 
                   ORDER BY is_completed, position, created_at''',
                (board['id'],)
            ).fetchall()
            
            for task in tasks:
                task_data = {
                    'task': task['task'],
                    'date': task['due_date'],
                    'notes': task['notes'] or ''
                }
                
                if task['is_completed']:
                    task_data['completed_on'] = task['completed_on']
                    board_data['completed'].append(task_data)
                else:
                    board_data['active'].append(task_data)
            
            result[board['id']] = board_data
        
        conn.close()
        return result
    
    def create_board(self, user_id, header, board_id):
        conn = self.get_connection()
        
        # Get the next position
        max_pos = conn.execute(
            'SELECT MAX(position) as max_pos FROM boards WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        
        position = (max_pos['max_pos'] or 0) + 1
        
        conn.execute(
            'INSERT INTO boards (id, user_id, header, position) VALUES (?, ?, ?, ?)',
            (board_id, user_id, header, position)
        )
        conn.commit()
        conn.close()
    
    def update_board_header(self, board_id, user_id, new_header):
        conn = self.get_connection()
        conn.execute(
            'UPDATE boards SET header = ? WHERE id = ? AND user_id = ?',
            (new_header, board_id, user_id)
        )
        conn.commit()
        conn.close()
    
    def delete_board(self, board_id, user_id):
        conn = self.get_connection()
        
        # Check if user owns the board and has more than one board
        board_count = conn.execute(
            'SELECT COUNT(*) as count FROM boards WHERE user_id = ?',
            (user_id,)
        ).fetchone()['count']
        
        if board_count > 1:
            conn.execute(
                'DELETE FROM boards WHERE id = ? AND user_id = ?',
                (board_id, user_id)
            )
            conn.commit()
        
        conn.close()
    
    def count_user_boards(self, user_id):
        conn = self.get_connection()
        count = conn.execute(
            'SELECT COUNT(*) as count FROM boards WHERE user_id = ?',
            (user_id,)
        ).fetchone()['count']
        conn.close()
        return count
    
    # Task methods
    def add_task(self, board_id, user_id, task, due_date, notes=''):
        conn = self.get_connection()
        
        # Verify user owns the board
        board = conn.execute(
            'SELECT id FROM boards WHERE id = ? AND user_id = ?',
            (board_id, user_id)
        ).fetchone()
        
        if board:
            # Count active tasks
            active_count = conn.execute(
                'SELECT COUNT(*) as count FROM tasks WHERE board_id = ? AND is_completed = 0',
                (board_id,)
            ).fetchone()['count']
            
            if active_count < 10:  # Limit of 10 active tasks
                # Get next position
                max_pos = conn.execute(
                    'SELECT MAX(position) as max_pos FROM tasks WHERE board_id = ? AND is_completed = 0',
                    (board_id,)
                ).fetchone()
                
                position = (max_pos['max_pos'] or 0) + 1
                
                conn.execute(
                    '''INSERT INTO tasks (board_id, task, due_date, notes, position) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (board_id, task, due_date, notes, position)
                )
                conn.commit()
        
        conn.close()
    
    def update_task(self, board_id, user_id, task_idx, new_task, new_date, new_notes):
        conn = self.get_connection()
        
        # Get the task at the specified index
        tasks = conn.execute(
            '''SELECT t.id FROM tasks t 
               JOIN boards b ON t.board_id = b.id 
               WHERE b.id = ? AND b.user_id = ? AND t.is_completed = 0 
               ORDER BY t.position, t.created_at 
               LIMIT 1 OFFSET ?''',
            (board_id, user_id, task_idx)
        ).fetchone()
        
        if tasks:
            conn.execute(
                'UPDATE tasks SET task = ?, due_date = ?, notes = ? WHERE id = ?',
                (new_task, new_date, new_notes, tasks['id'])
            )
            conn.commit()
        
        conn.close()
    
    def complete_task(self, board_id, user_id, task_idx):
        conn = self.get_connection()
        
        # Get the task at the specified index
        task = conn.execute(
            '''SELECT t.id FROM tasks t 
               JOIN boards b ON t.board_id = b.id 
               WHERE b.id = ? AND b.user_id = ? AND t.is_completed = 0 
               ORDER BY t.position, t.created_at 
               LIMIT 1 OFFSET ?''',
            (board_id, user_id, task_idx)
        ).fetchone()
        
        if task:
            conn.execute(
                'UPDATE tasks SET is_completed = 1, completed_on = ? WHERE id = ?',
                (datetime.now().strftime("%Y-%m-%d"), task['id'])
            )
            conn.commit()
        
        conn.close()
    
    def uncomplete_task(self, board_id, user_id, task_idx):
        conn = self.get_connection()
        
        # Check if we can uncomplete (less than 10 active tasks)
        active_count = conn.execute(
            'SELECT COUNT(*) as count FROM tasks WHERE board_id = ? AND is_completed = 0',
            (board_id,)
        ).fetchone()['count']
        
        if active_count < 10:
            # Get the completed task at the specified index
            task = conn.execute(
                '''SELECT t.id FROM tasks t 
                   JOIN boards b ON t.board_id = b.id 
                   WHERE b.id = ? AND b.user_id = ? AND t.is_completed = 1 
                   ORDER BY t.completed_on DESC, t.created_at DESC 
                   LIMIT 1 OFFSET ?''',
                (board_id, user_id, task_idx)
            ).fetchone()
            
            if task:
                conn.execute(
                    'UPDATE tasks SET is_completed = 0, completed_on = NULL WHERE id = ?',
                    (task['id'],)
                )
                conn.commit()
        
        conn.close()
