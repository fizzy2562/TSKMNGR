import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from contextlib import contextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path='tskmngr.db'):
        """
        Initialize the SQLite database.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Ensures proper connection handling and automatic cleanup.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
            # Enable foreign key constraints
            conn.execute('PRAGMA foreign_keys = ON')
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def init_db(self):
        """Initialize the database with required tables."""
        with self.get_connection() as conn:
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
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    # User methods
    def create_user(self, username, password):
        """
        Create a new user with username and password.
        
        Args:
            username (str): The username
            password (str): Plain text password (will be hashed)
            
        Returns:
            int: User ID if successful, None if username already exists
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                password_hash = generate_password_hash(password)
                cursor.execute(
                    'INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                    (username, password_hash)
                )
                user_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Created user: {username} with ID: {user_id}")
            
            # Create default board for new user
            import uuid
            self.create_board(user_id, "Your Tasks", str(uuid.uuid4()))
            
            return user_id
        except sqlite3.IntegrityError as e:
            logger.warning(f"Failed to create user {username}: {e}")
            return None
    
    def authenticate_user(self, username, password):
        """
        Authenticate a user with username and password.
        
        Args:
            username (str): The username
            password (str): Plain text password
            
        Returns:
            dict: User data if authentication successful, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            logger.info(f"User {username} authenticated successfully")
            return dict(user)
        
        logger.warning(f"Authentication failed for user: {username}")
        return None
    
    # Board methods
    def get_user_boards(self, user_id):
        """
        Get all boards and their tasks for a specific user.
        
        Args:
            user_id (int): The user ID
            
        Returns:
            dict: Dictionary of boards with their tasks
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM boards WHERE user_id = ? ORDER BY position, created_at',
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
                    '''SELECT * FROM tasks WHERE board_id = ? 
                       ORDER BY is_completed, position, created_at''',
                    (board['id'],)
                )
                tasks = cursor.fetchall()
                
                for task in tasks:
                    task_data = {
                        'task': task['task'],
                        'date': task['due_date'],
                        'notes': task['notes'] or ''
                    }
                    
                    if task['is_completed']:
                        task_data['completed_on'] = task['completed_on'] or ''
                        board_data['completed'].append(task_data)
                    else:
                        board_data['active'].append(task_data)
                
                result[board['id']] = board_data
        
        return result
    
    def create_board(self, user_id, header, board_id):
        """
        Create a new board for a user.
        
        Args:
            user_id (int): The user ID
            header (str): Board title/header
            board_id (str): Unique board identifier
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get the next position
            cursor.execute(
                'SELECT MAX(position) as max_pos FROM boards WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            max_pos = result['max_pos'] if result['max_pos'] is not None else 0
            position = max_pos + 1
            
            cursor.execute(
                'INSERT INTO boards (id, user_id, header, position) VALUES (?, ?, ?, ?)',
                (board_id, user_id, header, position)
            )
            conn.commit()
            logger.info(f"Created board '{header}' for user {user_id}")
    
    def update_board_header(self, board_id, user_id, new_header):
        """
        Update a board's header/title.
        
        Args:
            board_id (str): The board ID
            user_id (int): The user ID (for security)
            new_header (str): New header text
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE boards SET header = ? WHERE id = ? AND user_id = ?',
                (new_header, board_id, user_id)
            )
            conn.commit()
            logger.info(f"Updated board {board_id} header to '{new_header}'")
    
    def delete_board(self, board_id, user_id):
        """
        Delete a board (only if user has more than one board).
        
        Args:
            board_id (str): The board ID
            user_id (int): The user ID (for security)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check if user owns the board and has more than one board
            cursor.execute(
                'SELECT COUNT(*) as count FROM boards WHERE user_id = ?',
                (user_id,)
            )
            board_count = cursor.fetchone()['count']
            
            if board_count > 1:
                cursor.execute(
                    'DELETE FROM boards WHERE id = ? AND user_id = ?',
                    (board_id, user_id)
                )
                conn.commit()
                logger.info(f"Deleted board {board_id} for user {user_id}")
            else:
                logger.warning(f"Cannot delete last board for user {user_id}")
    
    def count_user_boards(self, user_id):
        """
        Count the number of boards for a user.
        
        Args:
            user_id (int): The user ID
            
        Returns:
            int: Number of boards
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) as count FROM boards WHERE user_id = ?',
                (user_id,)
            )
            count = cursor.fetchone()['count']
        return count
    
    # Task methods
    def add_task(self, board_id, user_id, task, due_date, notes=''):
        """
        Add a new task to a board.
        
        Args:
            board_id (str): The board ID
            user_id (int): The user ID (for security)
            task (str): Task description
            due_date (str): Due date in YYYY-MM-DD format
            notes (str): Optional notes
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Verify user owns the board
            cursor.execute(
                'SELECT id FROM boards WHERE id = ? AND user_id = ?',
                (board_id, user_id)
            )
            board = cursor.fetchone()
            
            if board:
                # Count active tasks
                cursor.execute(
                    'SELECT COUNT(*) as count FROM tasks WHERE board_id = ? AND is_completed = 0',
                    (board_id,)
                )
                active_count = cursor.fetchone()['count']
                
                if active_count < 10:  # Limit of 10 active tasks
                    # Get next position
                    cursor.execute(
                        'SELECT MAX(position) as max_pos FROM tasks WHERE board_id = ? AND is_completed = 0',
                        (board_id,)
                    )
                    result = cursor.fetchone()
                    max_pos = result['max_pos'] if result['max_pos'] is not None else 0
                    position = max_pos + 1
                    
                    cursor.execute(
                        '''INSERT INTO tasks (board_id, task, due_date, notes, position) 
                           VALUES (?, ?, ?, ?, ?)''',
                        (board_id, task, due_date, notes, position)
                    )
                    conn.commit()
                    logger.info(f"Added task '{task}' to board {board_id}")
                else:
                    logger.warning(f"Cannot add task - board {board_id} has maximum active tasks")
            else:
                logger.error(f"Board {board_id} not found or user {user_id} doesn't own it")
    
    def update_task(self, board_id, user_id, task_idx, new_task, new_date, new_notes):
        """
        Update an existing task.
        
        Args:
            board_id (str): The board ID
            user_id (int): The user ID (for security)
            task_idx (int): Task index in the active tasks list
            new_task (str): New task description
            new_date (str): New due date
            new_notes (str): New notes
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get the task at the specified index
            cursor.execute(
                '''SELECT t.id FROM tasks t 
                   JOIN boards b ON t.board_id = b.id 
                   WHERE b.id = ? AND b.user_id = ? AND t.is_completed = 0 
                   ORDER BY t.position, t.created_at 
                   LIMIT 1 OFFSET ?''',
                (board_id, user_id, task_idx)
            )
            task = cursor.fetchone()
            
            if task:
                cursor.execute(
                    'UPDATE tasks SET task = ?, due_date = ?, notes = ? WHERE id = ?',
                    (new_task, new_date, new_notes, task['id'])
                )
                conn.commit()
                logger.info(f"Updated task {task['id']} in board {board_id}")
            else:
                logger.error(f"Task at index {task_idx} not found in board {board_id}")
    
    def complete_task(self, board_id, user_id, task_idx):
        """
        Mark a task as completed.
        
        Args:
            board_id (str): The board ID
            user_id (int): The user ID (for security)
            task_idx (int): Task index in the active tasks list
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get the task at the specified index
            cursor.execute(
                '''SELECT t.id FROM tasks t 
                   JOIN boards b ON t.board_id = b.id 
                   WHERE b.id = ? AND b.user_id = ? AND t.is_completed = 0 
                   ORDER BY t.position, t.created_at 
                   LIMIT 1 OFFSET ?''',
                (board_id, user_id, task_idx)
            )
            task = cursor.fetchone()
            
            if task:
                cursor.execute(
                    'UPDATE tasks SET is_completed = 1, completed_on = ? WHERE id = ?',
                    (datetime.now().strftime("%Y-%m-%d"), task['id'])
                )
                conn.commit()
                logger.info(f"Completed task {task['id']} in board {board_id}")
            else:
                logger.error(f"Task at index {task_idx} not found in board {board_id}")
    
    def uncomplete_task(self, board_id, user_id, task_idx):
        """
        Mark a completed task as active again.
        
        Args:
            board_id (str): The board ID
            user_id (int): The user ID (for security)
            task_idx (int): Task index in the completed tasks list
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check if we can uncomplete (less than 10 active tasks)
            cursor.execute(
                'SELECT COUNT(*) as count FROM tasks WHERE board_id = ? AND is_completed = 0',
                (board_id,)
            )
            active_count = cursor.fetchone()['count']
            
            if active_count < 10:
                # Get the completed task at the specified index
                cursor.execute(
                    '''SELECT t.id FROM tasks t 
                       JOIN boards b ON t.board_id = b.id 
                       WHERE b.id = ? AND b.user_id = ? AND t.is_completed = 1 
                       ORDER BY t.completed_on DESC, t.created_at DESC 
                       LIMIT 1 OFFSET ?''',
                    (board_id, user_id, task_idx)
                )
                task = cursor.fetchone()
                
                if task:
                    cursor.execute(
                        'UPDATE tasks SET is_completed = 0, completed_on = NULL WHERE id = ?',
                        (task['id'],)
                    )
                    conn.commit()
                    logger.info(f"Uncompleted task {task['id']} in board {board_id}")
                else:
                    logger.error(f"Completed task at index {task_idx} not found in board {board_id}")
            else:
                logger.warning(f"Cannot uncomplete task - board {board_id} has maximum active tasks")
    
    def get_database_stats(self):
        """
        Get database statistics for debugging/monitoring.
        
        Returns:
            dict: Database statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Count users
            cursor.execute('SELECT COUNT(*) as count FROM users')
            stats['total_users'] = cursor.fetchone()['count']
            
            # Count boards
            cursor.execute('SELECT COUNT(*) as count FROM boards')
            stats['total_boards'] = cursor.fetchone()['count']
            
            # Count tasks
            cursor.execute('SELECT COUNT(*) as count FROM tasks')
            stats['total_tasks'] = cursor.fetchone()['count']
            
            # Count active tasks
            cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE is_completed = 0')
            stats['active_tasks'] = cursor.fetchone()['count']
            
            # Count completed tasks
            cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE is_completed = 1')
            stats['completed_tasks'] = cursor.fetchone()['count']
            
        return stats
    
    def cleanup_old_completed_tasks(self, days_old=30):
        """
        Remove completed tasks older than specified days.
        
        Args:
            days_old (int): Number of days after which to remove completed tasks
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''DELETE FROM tasks 
                   WHERE is_completed = 1 
                   AND completed_on < date('now', '-{} days')'''.format(days_old)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Cleaned up {deleted_count} old completed tasks")
            return deleted_count
