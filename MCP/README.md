# TSKMNGR MCP Server

<div align="center">
  <img src="../logo.png" alt="TSKMNGR Logo" width="150"/>

  **Model Context Protocol Integration for TSKMNGR**

  Drive your TSKMNGR task management from any MCP-compatible client
</div>

## Overview

The TSKMNGR MCP Server provides a Model Context Protocol interface to the TSKMNGR task management system. This allows you to manage your boards and tasks from MCP-compatible clients like Claude Desktop, VS Code with MCP extensions, and other AI development tools.

## Features

- **Session-based Authentication** - Secure login with persistent session state
- **Full Task Management** - Create, complete, and organize tasks across boards
- **Board Management** - Create and manage up to 4 boards per user
- **Archive Integration** - Access your completed task history
- **Real-time Validation** - Enforces the same limits as the web application (4 boards, 10 active tasks per board)
- **Multiple Transport Options** - stdio, SSE, and HTTP transport protocols

## Available Tools

### Authentication
- `login(username, password)` - Authenticate and create persistent session
- `logout()` - Clear active session
- `current_user()` - Get current authenticated user info

### Board Operations
- `list_boards()` - View all boards with task counts
- `create_board(name)` - Create new board (respects 4-board limit)

### Task Operations
- `list_tasks(board_id, include_completed=True)` - Get tasks for a specific board
- `add_task(board_id, task, due_date, notes=None)` - Add new task (YYYY-MM-DD format)
- `complete_task(board_id, task_id)` - Mark task complete and trigger archiving

### Archive Operations
- `list_archived_tasks(limit=20, offset=0)` - Browse completed task history

## Installation & Setup

### Prerequisites

1. **TSKMNGR Database**: You need a running TSKMNGR instance with PostgreSQL database
2. **Environment Variables**:
   ```bash
   export DATABASE_URL="your_postgresql_connection_string"
   export SECRET_KEY="your_secret_key"  # optional
   ```

### Python Environment Setup

1. **Create and activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r ../requirements.txt
   ```

### Running the Server

#### Stdio Transport (recommended for most clients)
```bash
python -m mcp_server.tsk_mcp_server --transport stdio
```

#### HTTP/SSE Transport (for web-based clients)
```bash
python -m mcp_server.tsk_mcp_server --transport sse --host 0.0.0.0 --port 8765
```

## Client Configuration

### VS Code MCP Extension

Add to your `.vscode/mcp.json`:

```json
{
  "servers": {
    "tskmngr": {
      "type": "stdio",
      "command": "/path/to/your/tskmngr/.venv/bin/python",
      "args": [
        "-m",
        "mcp_server.tsk_mcp_server",
        "--transport",
        "stdio"
      ],
      "cwd": "/path/to/your/tskmngr",
      "env": {
        "DATABASE_URL": "${DATABASE_URL}",
        "SECRET_KEY": "${SECRET_KEY}"
      },
      "description": "TSKMNGR Task Management MCP Server"
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "tskmngr": {
      "command": "/path/to/your/tskmngr/.venv/bin/python",
      "args": [
        "-m",
        "mcp_server.tsk_mcp_server",
        "--transport",
        "stdio"
      ],
      "cwd": "/path/to/your/tskmngr",
      "env": {
        "DATABASE_URL": "your_database_url_here",
        "SECRET_KEY": "your_secret_key_here"
      }
    }
  }
}
```

## Usage Examples

### Basic Workflow

1. **Login to start session**:
   ```
   login("your_username", "your_password")
   ```

2. **View your boards**:
   ```
   list_boards()
   ```

3. **Check tasks on a board**:
   ```
   list_tasks("board-uuid-here")
   ```

4. **Add a new task**:
   ```
   add_task("board-uuid-here", "Complete project documentation", "2024-01-15", "Need to finish API docs")
   ```

5. **Complete a task**:
   ```
   complete_task("board-uuid-here", 123)
   ```

6. **View completed work**:
   ```
   list_archived_tasks(limit=10)
   ```

## Architecture

The MCP server is built using FastMCP and integrates directly with the existing TSKMNGR database and archiving systems:

- **Lazy Service Loading** - Database connections are created only when needed
- **Async/Await Support** - Non-blocking database operations using `anyio.to_thread`
- **Session Management** - Persistent authentication across tool calls
- **Error Handling** - Comprehensive validation and informative error messages
- **Business Logic Enforcement** - Same constraints as the web application

## Development

### File Structure
```
MCP/
├── README.md              # This file
└── mcp_server/
    ├── __init__.py
    └── tsk_mcp_server.py   # Main MCP server implementation
```

### Testing
```bash
# Validate server compiles correctly
python -m compileall mcp_server/tsk_mcp_server.py

# Test server help
python -m mcp_server.tsk_mcp_server --help
```

## Troubleshooting

### Common Issues

**Module not found errors**: Ensure all dependencies are installed in your virtual environment:
```bash
pip install -r ../requirements.txt
```

**Database connection errors**: Verify your `DATABASE_URL` environment variable is set and accessible.

**Authentication failures**: Check that your username/password are correct and that the user exists in the TSKMNGR database.

**Import errors**: Make sure you're running the server from the correct directory (the parent directory containing both `database.py` and `mcp_server/`).

### Logging

The server includes comprehensive logging. Set log level for debugging:
```bash
export PYTHONPATH=.
python -m mcp_server.tsk_mcp_server --transport stdio
```

## Integration with Main TSKMNGR

This MCP server shares the same database and business logic as the main TSKMNGR web application:

- **Shared User Accounts** - Use the same login credentials
- **Synchronized Data** - Changes made via MCP are immediately reflected in the web UI
- **Same Constraints** - 4-board limit, 10 active tasks per board, task archiving rules
- **Consistent Behavior** - Identical validation and error handling

## Contributing

This MCP integration is part of the main TSKMNGR project. See the [main README](../README.md) for contribution guidelines.

## License

Open source - same license as the main TSKMNGR project.