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
        if not use_existing_conn:
            conn = self.db.get_connection()
            
        try:
            with conn.cursor() as cursor:
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
                
                # Select oldest completed tasks to archive
                # Order by completed_on (NULLs first) then created_at as per design
                cursor.execute('''
                    SELECT id, task, due_date, notes, completed_on, created_at
                    FROM tasks 
                    WHERE board_id = %s AND is_completed = TRUE
                    ORDER BY 
                        completed_on IS NULL DESC,  -- NULLs first
                        completed_on ASC,           -- Then by completed_on
                        created_at ASC              -- Then by created_at
                    LIMIT %s
                ''', (board_id, overflow_count))
                
                tasks_to_archive = cursor.fetchall()
                
                if not tasks_to_archive:
                    logger.warning(f"No completed tasks found to archive on board {board_id}")
                    return 0
                
                # Archive the selected tasks
                archived_count = 0
                for task in tasks_to_archive:
                    # Insert into archived_tasks
                    cursor.execute('''
                        INSERT INTO archived_tasks 
                        (user_id, original_task_id, board_id, board_name_at_archive, 
                         task, due_date, notes, completed_on, archived_on)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        user_id,
                        task['id'],
                        board_id,
                        board_name,
                        task['task'],
                        task['due_date'],
                        task['notes'],
                        task['completed_on'],
                        datetime.now()
                    ))
                    
                    # Remove from tasks table
                    cursor.execute('DELETE FROM tasks WHERE id = %s', (task['id'],))
                    archived_count += 1
                
                if not use_existing_conn:
                    conn.commit()
                    
                logger.info(f"Archived {archived_count} tasks from board {board_id}")
                return archived_count
                
        except Exception as e:
            logger.error(f"Error during archiving for board {board_id}: {e}")
            if not use_existing_conn:
                conn.rollback()
            raise
        finally:
            if not use_existing_conn:
                conn.close()
    
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