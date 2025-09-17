"""
TSKMNGR Archiving Module

Handles automatic archiving of completed tasks when boards exceed 10 total tasks.
Implements the design from ARCHIVING_DESIGN.txt with feature flag control.

Phase 1 MVP Features:
- Core archiving on task completion
- Basic archived tasks viewing
- Feature flag control
- Transaction safety
"""

import logging
import os
from datetime import datetime
from contextlib import contextmanager

# Configure logging
logger = logging.getLogger(__name__)

class ArchiveManager:
    """Manages task archiving functionality with feature flag control."""
    
    # Feature flags - can be controlled via environment variables
    ENABLE_ARCHIVE_ON_COMPLETE = os.environ.get('ENABLE_ARCHIVE_ON_COMPLETE', 'False').lower() == 'true'
    MAX_TASKS_PER_BOARD = int(os.environ.get('MAX_TASKS_PER_BOARD', '10'))
    
    def __init__(self, database):
        """Initialize with database connection."""
        self.db = database
        logger.info(f"ArchiveManager initialized - Archive enabled: {self.ENABLE_ARCHIVE_ON_COMPLETE}, Max tasks: {self.MAX_TASKS_PER_BOARD}")
    
    def should_archive(self):
        """Check if archiving is enabled via feature flag."""
        return self.ENABLE_ARCHIVE_ON_COMPLETE
    
    def archive_overflow_tasks(self, board_id, user_id, conn=None):
        """
        Archive oldest completed tasks if board exceeds MAX_TASKS_PER_BOARD.
        
        Args:
            board_id (str): The board ID to check
            user_id (int): The user ID for security
            conn: Optional database connection (for transaction safety)
            
        Returns:
            int: Number of tasks archived
        """
        if not self.should_archive():
            logger.debug(f"Archiving disabled for board {board_id}")
            return 0
            
        use_existing_conn = conn is not None
        try:
            # Open a connection only if caller didn't pass one
            if not use_existing_conn:
                with self.db.get_connection() as managed_conn:
                    with managed_conn.cursor() as cursor:
                        archived = self._archive_overflow_with_cursor(cursor, board_id, user_id)
                        managed_conn.commit()
                        return archived
            else:
                # Use provided connection and its cursor; caller controls commit
                with conn.cursor() as cursor:
                    return self._archive_overflow_with_cursor(cursor, board_id, user_id)
        except Exception as e:
            logger.error(f"Error during archiving for board {board_id}: {e}")
            raise

    def _archive_overflow_with_cursor(self, cursor, board_id, user_id):
        """Internal helper that performs archiving using an existing cursor/connection."""
        # Count total tasks on the board
        cursor.execute(
            'SELECT COUNT(*) as total FROM tasks WHERE board_id = %s',
            (board_id,)
        )
        total_tasks = cursor.fetchone()['total']

        logger.debug(f"Board {board_id} has {total_tasks} total tasks (limit: {self.MAX_TASKS_PER_BOARD})")

        if total_tasks <= self.MAX_TASKS_PER_BOARD:
            logger.debug(f"Board {board_id} within limits, no archiving needed")
            return 0

        # Calculate how many tasks need to be archived
        overflow_count = total_tasks - self.MAX_TASKS_PER_BOARD
        logger.info(f"Board {board_id} has {overflow_count} overflow tasks to archive")

        # Get board name for archive record
        cursor.execute(
            'SELECT header FROM boards WHERE id = %s AND user_id = %s',
            (board_id, user_id)
        )
        board_result = cursor.fetchone()
        if not board_result:
            logger.error(f"Board {board_id} not found for user {user_id}")
            return 0

        board_name = board_result['header']

        return self._archive_oldest_completed(cursor, board_id, user_id, board_name, overflow_count)

    def archive_to_fit(self, board_id, user_id, required_additional=1, conn=None):
        """
        Archive oldest completed tasks so that adding `required_additional` items
        would not exceed MAX_TASKS_PER_BOARD.
        """
        if not self.should_archive():
            return 0
        use_existing = conn is not None
        if not use_existing:
            with self.db.get_connection() as managed_conn:
                with managed_conn.cursor() as cursor:
                    cursor.execute('SELECT COUNT(*) AS total FROM tasks WHERE board_id = %s', (board_id,))
                    total = cursor.fetchone()['total']
                    overflow = total + max(0, required_additional) - self.MAX_TASKS_PER_BOARD
                    if overflow <= 0:
                        return 0
                    # Get board name
                    cursor.execute('SELECT header FROM boards WHERE id = %s AND user_id = %s', (board_id, user_id))
                    row = cursor.fetchone()
                    if not row:
                        return 0
                    count = self._archive_oldest_completed(cursor, board_id, user_id, row['header'], overflow)
                    managed_conn.commit()
                    return count
        else:
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS total FROM tasks WHERE board_id = %s', (board_id,))
                total = cursor.fetchone()['total']
                overflow = total + max(0, required_additional) - self.MAX_TASKS_PER_BOARD
                if overflow <= 0:
                    return 0
                cursor.execute('SELECT header FROM boards WHERE id = %s AND user_id = %s', (board_id, user_id))
                row = cursor.fetchone()
                if not row:
                    return 0
                return self._archive_oldest_completed(cursor, board_id, user_id, row['header'], overflow)

    def _archive_oldest_completed(self, cursor, board_id, user_id, board_name, limit):
        """Archive up to `limit` oldest completed tasks for the board."""
        cursor.execute('''
            SELECT id, task, due_date, notes, completed_on, created_at
            FROM tasks 
            WHERE board_id = %s AND is_completed = TRUE
            ORDER BY completed_on NULLS FIRST, created_at ASC
            LIMIT %s
        ''', (board_id, limit))

        rows = cursor.fetchall()
        if not rows:
            return 0
        archived_count = 0
        for task in rows:
            cursor.execute('''
                INSERT INTO archived_tasks 
                (user_id, original_task_id, board_id, board_name_at_archive, 
                 task, due_date, notes, completed_on, archived_on)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                user_id, task['id'], board_id, board_name,
                task['task'], task['due_date'], task['notes'], task['completed_on'], datetime.now()
            ))
            cursor.execute('DELETE FROM tasks WHERE id = %s', (task['id'],))
            archived_count += 1
        logger.info(f"Archived {archived_count} tasks from board {board_id}")
        return archived_count
    
    # (Removed duplicate _archive_overflow_with_cursor)
    
    def get_archived_tasks(self, user_id, limit=50, offset=0):
        """
        Get archived tasks for a user.
        
        Args:
            user_id (int): The user ID
            limit (int): Max number of tasks to return
            offset (int): Offset for pagination
            
        Returns:
            list: List of archived task dictionaries
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        board_name_at_archive,
                        task,
                        due_date,
                        notes,
                        completed_on,
                        archived_on
                    FROM archived_tasks
                    WHERE user_id = %s
                    ORDER BY archived_on DESC
                    LIMIT %s OFFSET %s
                ''', (user_id, limit, offset))
                
                return cursor.fetchall()
    
    def get_archived_tasks_count(self, user_id):
        """Get total count of archived tasks for pagination."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT COUNT(*) as count FROM archived_tasks WHERE user_id = %s',
                    (user_id,)
                )
                return cursor.fetchone()['count']
