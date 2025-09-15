import psycopg
from psycopg.rows import dict_row
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from contextlib import contextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    # Feature flag for performance optimizations
    USE_OPTIMIZED_QUERIES = True  # Set to True to enable JOIN optimization
    
    def __init__(self):
        """
        Initialize the PostgreSQL database connection using Neon.
        """
        # Get database URL from environment variable
        self.database_url = os.environ.get('DATABASE_URL')
        
        # Handle Render's postgres:// vs postgresql:// issue
        if self.database_url and self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        logger.info(f"Using PostgreSQL database: {self.database_url[:50]}...")
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for PostgreSQL connections.
        """
        conn = None
        try:
            conn = psycopg.connect(self.database_url, row_factory=dict_row)
            yield conn
        except psycopg.Error as e:
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
                with conn.cursor() as cursor:
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
                    
                    # Create indexes for better performance
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_id ON tasks(board_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(is_completed)')
                    
                    # High-performance composite indexes for faster queries
                    logger.info("Creating performance indexes...")
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_completed ON tasks(board_id, is_completed)')
                    logger.info("Created index: idx_tasks_board_completed")
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_position ON tasks(board_id, position)')
                    logger.info("Created index: idx_tasks_board_position") 
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_board_completed_position ON tasks(board_id, is_completed, position)')
                    logger.info("Created index: idx_tasks_board_completed_position")
                    
                    conn.commit()
                    logger.info("Database initialized successfully")
                    
                    # Test database functionality
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                    tables = [row['table_name'] for row in cursor.fetchall()]
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
                with conn.cursor() as cursor:
                    password_hash = generate_password_hash(password)
                    logger.debug(f"Password hashed for user: {username}")
                    
                    cursor.execute(
                        'INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id', 
                        (username, password_hash)
                    )
                    user_id = cursor.fetchone()['id']
                    conn.commit()
                    logger.info(f"Created user: {username} with ID: {user_id}")
                    
                    # Verify user was created
                    cursor.execute('SELECT COUNT(*) as count FROM users WHERE id = %s', (user_id,))
                    count = cursor.fetchone()['count']
                    logger.debug(f"User verification count: {count}")
            
            # Create default board for new user
            import uuid
            board_id = str(uuid.uuid4())
            logger.debug(f"Creating default board for user {user_id} with ID: {board_id}")
            self.create_board(user_id, "Your Tasks", board_id)
            
            return user_id
            
        except psycopg.IntegrityError as e:
            logger.warning(f"Failed to create user {username} - username already exists: {e}")
            return None
        except Exception as e:
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
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
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
        Uses feature flag to switch between original and optimized implementations.
        
        Args:
            user_id (int): The user ID
            
        Returns:
            dict: Dictionary of boards with their tasks
        """
        if self.USE_OPTIMIZED_QUERIES:
            logger.info("Using optimized JOIN query for get_user_boards")
            return self.get_user_boards_optimized(user_id)
        else:
            logger.info("Using original query method for get_user_boards")
            return self.get_user_boards_original(user_id)
    
    def get_user_boards_original(self, user_id):
        """
        BACKUP VERSION: Original implementation with separate queries.
        This is kept as a fallback in case the optimized version has issues.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
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
                            'id': task['id'],
                            'task': task['task'],
                            'date': task['due_date'].strftime('%Y-%m-%d') if hasattr(task['due_date'], 'strftime') else str(task['due_date']),
                            'notes': task['notes'] or ''
                        }
                        
                        if task['is_completed']:
                            task_data['completed_on'] = task['completed_on'].strftime('%Y-%m-%d') if task['completed_on'] else ''
                            board_data['completed'].append(task_data)
                        else:
                            board_data['active'].append(task_data)
                    
                    result[board['id']] = board_data
        
        return result

    def get_user_boards_optimized(self, user_id):
        """
        OPTIMIZED VERSION: Single JOIN query for better performance.
        Reduces database round trips from N+1 queries to just 1 query.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Single query to get all boards and their tasks
                cursor.execute('''
                    SELECT 
                        b.id as board_id,
                        b.header as board_header,
                        b.position as board_position,
                        b.created_at as board_created_at,
                        t.id as task_id,
                        t.task as task_name,
                        t.due_date as task_due_date,
                        t.notes as task_notes,
                        t.is_completed,
                        t.completed_on,
                        t.position as task_position,
                        t.created_at as task_created_at
                    FROM boards b
                    LEFT JOIN tasks t ON b.id = t.board_id
                    WHERE b.user_id = %s
                    ORDER BY b.position, b.created_at, t.is_completed, t.position, t.created_at
                ''', (user_id,))
                
                rows = cursor.fetchall()
                
                result = {}
                current_board_id = None
                
                for row in rows:
                    board_id = row['board_id']
                    
                    # Initialize new board
                    if board_id not in result:
                        result[board_id] = {
                            'header': row['board_header'],
                            'active': [],
                            'completed': []
                        }
                    
                    # Add task if it exists (LEFT JOIN can have NULL tasks for empty boards)
                    if row['task_id'] is not None:
                        task_data = {
                            'id': row['task_id'],
                            'task': row['task_name'],
                            'date': row['task_due_date'].strftime('%Y-%m-%d') if hasattr(row['task_due_date'], 'strftime') else str(row['task_due_date']),
                            'notes': row['task_notes'] or ''
                        }
                        
                        if row['is_completed']:
                            task_data['completed_on'] = row['completed_on'].strftime('%Y-%m-%d') if row['completed_on'] else ''
                            result[board_id]['completed'].append(task_data)
                        else:
                            result[board_id]['active'].append(task_data)
                
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
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Get the next position
                    cursor.execute(
                        'SELECT MAX(position) as max_pos FROM boards WHERE user_id = %s',
                        (user_id,)
                    )
                    result = cursor.fetchone()
                    max_pos = result['max_pos'] if result['max_pos'] is not None else 0
                    position = max_pos + 1
                    
                    cursor.execute(
                        'INSERT INTO boards (id, user_id, header, position) VALUES (%s, %s, %s, %s)',
                        (board_id, user_id, header, position)
                    )
                    conn.commit()
                    logger.info(f"Created board '{header}' for user {user_id}")
                    
                    # Verify board was created
                    cursor.execute('SELECT COUNT(*) as count FROM boards WHERE id = %s', (board_id,))
                    count = cursor.fetchone()['count']
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
            with conn.cursor() as cursor:
                cursor.execute(
                    'UPDATE boards SET header = %s WHERE id = %s AND user_id = %s',
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
            with conn.cursor() as cursor:
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
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT COUNT(*) as count FROM boards WHERE user_id = %s',
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
                with conn.cursor() as cursor:
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
                        logger.debug(f"Current active tasks in board {board_id}: {active_count}")
                        
                        if active_count < 10:  # Limit of 10 active tasks
                            # Get next position
                            cursor.execute(
                                'SELECT MAX(position) as max_pos FROM tasks WHERE board_id = %s AND is_completed = FALSE',
                                (board_id,)
                            )
                            result = cursor.fetchone()
                            max_pos = result['max_pos'] if result['max_pos'] is not None else 0
                            position = max_pos + 1
                            
                            cursor.execute(
                                '''INSERT INTO tasks (board_id, task, due_date, notes, position) 
                                   VALUES (%s, %s, %s, %s, %s) RETURNING id''',
                                (board_id, task, due_date, notes, position)
                            )
                            task_id = cursor.fetchone()['id']
                            conn.commit()
                            logger.info(f"Added task '{task}' to board {board_id} with ID: {task_id}")
                            
                            # Verify task was created
                            cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE id = %s', (task_id,))
                            count = cursor.fetchone()['count']
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
            with conn.cursor() as cursor:
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
            with conn.cursor() as cursor:
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
                    logger.info(f"Completed task {task['id']} in board {board_id}")
                else:
                    logger.error(f"Task at index {task_idx} not found in board {board_id}")
    
    def uncomplete_task(self, board_id, user_id, task_id):
        """
        Mark a completed task as active again.
        
        Args:
            board_id (str): The board ID
            user_id (int): The user ID (for security)
            task_id (int): The specific task ID to uncomplete
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Check if we can uncomplete (less than 10 active tasks)
                cursor.execute(
                    'SELECT COUNT(*) as count FROM tasks WHERE board_id = %s AND is_completed = FALSE',
                    (board_id,)
                )
                active_count = cursor.fetchone()['count']
                
                if active_count < 10:
                    # Verify the task exists, is completed, and belongs to the user's board
                    cursor.execute(
                        '''SELECT t.id FROM tasks t 
                           JOIN boards b ON t.board_id = b.id 
                           WHERE t.id = %s AND b.id = %s AND b.user_id = %s AND t.is_completed = TRUE''',
                        (task_id, board_id, user_id)
                    )
                    task = cursor.fetchone()
                    
                    if task:
                        cursor.execute(
                            'UPDATE tasks SET is_completed = FALSE, completed_on = NULL WHERE id = %s',
                            (task_id,)
                        )
                        conn.commit()
                        logger.info(f"Uncompleted task {task_id} in board {board_id}")
                    else:
                        logger.error(f"Completed task {task_id} not found or not accessible in board {board_id}")
                else:
                    logger.warning(f"Cannot uncomplete task - board {board_id} has maximum active tasks")
    
    def get_database_stats(self):
        """
        Get database statistics for debugging/monitoring.
        
        Returns:
            dict: Database statistics
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                
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
                cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE is_completed = FALSE')
                stats['active_tasks'] = cursor.fetchone()['count']
                
                # Count completed tasks
                cursor.execute('SELECT COUNT(*) as count FROM tasks WHERE is_completed = TRUE')
                stats['completed_tasks'] = cursor.fetchone()['count']
                
        return stats
    
    def cleanup_old_completed_tasks(self, days_old=30):
        """
        Remove completed tasks older than specified days.
        
        Args:
            days_old (int): Number of days after which to remove completed tasks
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''DELETE FROM tasks 
                       WHERE is_completed = TRUE 
                       AND completed_on < CURRENT_DATE - INTERVAL '%s days' ''',
                    (days_old,)
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
                with conn.cursor() as cursor:
                    
                    logger.info("=== DATABASE DEBUG INFO ===")
                    logger.info(f"Database URL: {self.database_url[:50]}...")
                    
                    # Check database version
                    cursor.execute('SELECT version()')
                    version = cursor.fetchone()['version']
                    logger.info(f"PostgreSQL version: {version}")
                    
                    # Check tables
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                    tables = [row['table_name'] for row in cursor.fetchall()]
                    logger.info(f"Tables: {tables}")
                    
                    # Check users
                    cursor.execute('SELECT COUNT(*) as count FROM users')
                    user_count = cursor.fetchone()['count']
                    logger.info(f"Total users: {user_count}")
                    
                    if user_count > 0:
                        cursor.execute('SELECT id, username, created_at FROM users ORDER BY id')
                        users = cursor.fetchall()
                        for user in users:
                            logger.info(f"User: ID={user['id']}, Username={user['username']}, Created={user['created_at']}")
                    
                    # Check boards
                    cursor.execute('SELECT COUNT(*) as count FROM boards')
                    board_count = cursor.fetchone()['count']
                    logger.info(f"Total boards: {board_count}")
                    
                    if board_count > 0:
                        cursor.execute('SELECT id, user_id, header FROM boards ORDER BY user_id')
                        boards = cursor.fetchall()
                        for board in boards:
                            logger.info(f"Board: ID={board['id']}, UserID={board['user_id']}, Header={board['header']}")
                    
                    # Check tasks
                    cursor.execute('SELECT COUNT(*) as count FROM tasks')
                    task_count = cursor.fetchone()['count']
                    logger.info(f"Total tasks: {task_count}")
                    
                    if task_count > 0:
                        cursor.execute('SELECT id, board_id, task, is_completed FROM tasks ORDER BY board_id')
                        tasks = cursor.fetchall()
                        for task in tasks:
                            logger.info(f"Task: ID={task['id']}, BoardID={task['board_id']}, Task={task['task']}, Completed={task['is_completed']}")
                    
                    logger.info("=== END DEBUG INFO ===")
                    
        except Exception as e:
            logger.error(f"Error during debug: {e}")
