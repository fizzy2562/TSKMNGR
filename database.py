import sqlite3
import psycopg
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from contextlib import contextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path='tskmngr.db'):
        """
        Initialize the hybrid database (PostgreSQL for production, SQLite for local).
        
        Args:
            db_path (str): Path to the SQLite database file (used only if no DATABASE_URL)
        """
        # Get database URL from environment variable
        self.database_url = os.environ.get('DATABASE_URL')
        
        # Handle Render's postgres:// vs postgresql:// issue
        if self.database_url and self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        
        if self.database_url:
            logger.info(f"Using PostgreSQL database: {self.database_url[:30]}...")
            self.db_type = 'postgresql'
        else:
            # Ensure the database path is absolute for SQLite
            self.db_path = os.path.abspath(db_path)
            logger.info(f"Using SQLite database: {self.db_path}")
            self.db_type = 'sqlite'
            
            # Create directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
        
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Handles both PostgreSQL and SQLite connections automatically.
        """
        conn = None
        try:
            if self.db_type == 'postgresql':
                # PostgreSQL connection
                conn = psycopg.connect(self.database_url)
                conn.autocommit = False  # Use transactions
            else:
                # SQLite connection
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
                # Enable foreign key constraints for SQLite
                conn.execute('PRAGMA foreign_keys = ON')
            
            yield conn
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def init_db(self):
        """Initialize the database with required tables."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db_type == 'postgresql':
                    # PostgreSQL table creation
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
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
                    
                    # Create indexes for PostgreSQL
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_id ON tasks(board_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(is_completed)')
                    
                else:
                    # SQLite table creation
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
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
                    
                    # Create indexes for SQLite
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_id ON tasks(board_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(is_completed)')
                
                conn.commit()
                logger.info(f"Database initialized successfully ({self.db_type})")
                
                # Test database functionality
                if self.db_type == 'postgresql':
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                else:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Database tables created: {tables}")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
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
            logger.debug(f"Attempting to create user: {username}")
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                password_hash = generate_password_hash(password)
                logger.debug(f"Password hashed for user: {username}")
                
                if self.db_type == 'postgresql':
                    cursor.execute(
                        'INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id', 
                        (username, password_hash)
                    )
                    user_id = cursor.fetchone()[0]
                else:
                    cursor.execute(
                        'INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                        (username, password_hash)
                    )
                    user_id = cursor.lastrowid
                
                conn.commit()
                logger.info(f"Created user: {username} with ID: {user_id}")
                
                # Verify user was created
                if self.db_type == 'postgresql':
                    cursor.execute('SELECT COUNT(*) FROM users WHERE id = %s', (user_id,))
                else:
                    cursor.execute('SELECT COUNT(*) FROM users WHERE id = ?', (user_id,))
                count = cursor.fetchone()[0]
                logger.debug(f"User verification count: {count}")
            
            # Create default board for new user
            import uuid
            board_id = str(uuid.uuid4())
            logger.debug(f"Creating default board for user {user_id} with ID: {board_id}")
            self.create_board(user_id, "Your Tasks", board_id)
            
            return user_id
            
        except Exception as e:
            if "unique constraint" in str(e).lower() or "already exists" in str(e).lower():
                logger.warning(f"Failed to create user {username} - username already exists: {e}")
                return None
            logger.error(f"Unexpected error creating user {username}: {e}")
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
            if self.db_type == 'postgresql':
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            else:
                cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'] if self.db_type == 'sqlite' else user[2], password):
            logger.info(f"User {username} authenticated successfully")
            return dict(user) if self.db_type == 'sqlite' else {
                'id': user[0],
                'username': user[1],
                'password_hash': user[2],
                'created_at': user[3]
            }
        
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
        param_style = '%s' if self.db_type == 'postgresql' else '?'
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'SELECT * FROM boards WHERE user_id = {param_style} ORDER BY position, created_at',
                (user_id,)
            )
            boards = cursor.fetchall()
            
            result = {}
            for board in boards:
                if self.db_type == 'postgresql':
                    board_data = {
                        'header': board[2],  # header is 3rd column
                        'active': [],
                        'completed': []
                    }
                    board_id = board[0]  # id is 1st column
                else:
                    board_data = {
                        'header': board['header'],
                        'active': [],
                        'completed': []
                    }
                    board_id = board['id']
                
                # Get tasks for this board
                cursor.execute(
                    f'''SELECT * FROM tasks WHERE board_id = {param_style} 
                       ORDER BY is_completed, position, created_at''',
                    (board_id,)
                )
                tasks = cursor.fetchall()
                
                for task in tasks:
                    if self.db_type == 'postgresql':
                        task_data = {
                            'task': task[2],  # task column
                            'date': task[3].strftime('%Y-%m-%d') if hasattr(task[3], 'strftime') else str(task[3]),  # due_date
                            'notes': task[4] or ''  # notes
                        }
                        is_completed = task[5]  # is_completed
                        completed_on = task[6]  # completed_on
                    else:
                        task_data = {
                            'task': task['task'],
                            'date': task['due_date'],
                            'notes': task['notes'] or ''
                        }
                        is_completed = task['is_completed']
                        completed_on = task['completed_on']
                    
                    if is_completed:
                        task_data['completed_on'] = completed_on or ''
                        board_data['completed'].append(task_data)
                    else:
                        board_data['active'].append(task_data)
                
                result[board_id] = board_data
        
        return result
    
    def create_board(self, user_id, header, board_id):
        """
        Create a new board for a user.
        
        Args:
            user_id (int): The user ID
            header (str): Board title/header
            board_id (str): Unique board identifier
        """
        try:
            logger.debug(f"Creating board '{header}' for user {user_id} with ID: {board_id}")
            param_style = '%s' if self.db_type == 'postgresql' else '?'
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Get the next position
                cursor.execute(
                    f'SELECT MAX(position) as max_pos FROM boards WHERE user_id = {param_style}',
                    (user_id,)
                )
                result = cursor.fetchone()
                max_pos = result[0] if result[0] is not None else 0
                position = max_pos + 1
                
                cursor.execute(
                    f'INSERT INTO boards (id, user_id, header, position) VALUES ({param_style}, {param_style}, {param_style}, {param_style})',
                    (board_id, user_id, header, position)
                )
                conn.commit()
                logger.info(f"Created board '{header}' for user {user_id}")
                
                # Verify board was created
                cursor.execute(f'SELECT COUNT(*) FROM boards WHERE id = {param_style}', (board_id,))
                count = cursor.fetchone()[0]
                logger.debug(f"Board verification count: {count}")
                
        except Exception as e:
            logger.error(f"Failed to create board '{header}' for user {user_id}: {e}")
            raise
    
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
        try:
            logger.debug(f"Adding task '{task}' to board {board_id} for user {user_id}")
            
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
                    logger.debug(f"Current active tasks in board {board_id}: {active_count}")
                    
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
                        task_id = cursor.lastrowid
                        conn.commit()
                        logger.info(f"Added task '{task}' to board {board_id} with ID: {task_id}")
                        
                        # Verify task was created
                        cursor.execute('SELECT COUNT(*) FROM tasks WHERE id = ?', (task_id,))
                        count = cursor.fetchone()[0]
                        logger.debug(f"Task verification count: {count}")
                        
                    else:
                        logger.warning(f"Cannot add task - board {board_id} has maximum active tasks")
                else:
                    logger.error(f"Board {board_id} not found or user {user_id} doesn't own it")
                    
        except Exception as e:
            logger.error(f"Failed to add task '{task}' to board {board_id}: {e}")
            raise
    
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

    def debug_database_state(self):
        """
        Debug method to check the current state of the database.
        Useful for troubleshooting.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                logger.info("=== DATABASE DEBUG INFO ===")
                logger.info(f"Database file: {self.db_path}")
                logger.info(f"Database exists: {os.path.exists(self.db_path)}")
                
                if os.path.exists(self.db_path):
                    logger.info(f"Database size: {os.path.getsize(self.db_path)} bytes")
                
                # Check tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"Tables: {tables}")
                
                # Check users
                cursor.execute('SELECT COUNT(*) FROM users')
                user_count = cursor.fetchone()[0]
                logger.info(f"Total users: {user_count}")
                
                if user_count > 0:
                    cursor.execute('SELECT id, username, created_at FROM users ORDER BY id')
                    users = cursor.fetchall()
                    for user in users:
                        logger.info(f"User: ID={user[0]}, Username={user[1]}, Created={user[2]}")
                
                # Check boards
                cursor.execute('SELECT COUNT(*) FROM boards')
                board_count = cursor.fetchone()[0]
                logger.info(f"Total boards: {board_count}")
                
                if board_count > 0:
                    cursor.execute('SELECT id, user_id, header FROM boards ORDER BY user_id')
                    boards = cursor.fetchall()
                    for board in boards:
                        logger.info(f"Board: ID={board[0]}, UserID={board[1]}, Header={board[2]}")
                
                # Check tasks
                cursor.execute('SELECT COUNT(*) FROM tasks')
                task_count = cursor.fetchone()[0]
                logger.info(f"Total tasks: {task_count}")
                
                if task_count > 0:
                    cursor.execute('SELECT id, board_id, task, is_completed FROM tasks ORDER BY board_id')
                    tasks = cursor.fetchall()
                    for task in tasks:
                        logger.info(f"Task: ID={task[0]}, BoardID={task[1]}, Task={task[2]}, Completed={task[3]}")
                
                logger.info("=== END DEBUG INFO ===")
                
        except Exception as e:
            logger.error(f"Error during debug: {e}")

    def check_database_permissions(self):
        """
        Check if we have proper read/write permissions for the database.
        """
        try:
            # Check if we can write to the directory
            db_dir = os.path.dirname(self.db_path) or '.'
            if not os.access(db_dir, os.W_OK):
                logger.error(f"No write permission for directory: {db_dir}")
                return False
            
            # Check if database file exists and is writable
            if os.path.exists(self.db_path):
                if not os.access(self.db_path, os.R_OK | os.W_OK):
                    logger.error(f"No read/write permission for database file: {self.db_path}")
                    return False
            
            logger.info("Database permissions check passed")
            return True
            
        except Exception as e:
            logger.error(f"Error checking database permissions: {e}")
            return False
