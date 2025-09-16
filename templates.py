LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TSKMNGR - Login</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon-32.png') }}" sizes="32x32">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon-16.png') }}" sizes="16x16">
    <link rel="shortcut icon" href="{{ url_for('static', filename='favicon.png') }}">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            padding: 40px;
            width: 100%;
            max-width: 400px;
            position: relative;
            overflow: hidden;
        }

        .login-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo img {
            width: 180px;
            height: auto;
            margin-bottom: 12px;
            transition: transform 0.3s ease;
        }

        .logo img:hover {
            transform: scale(1.05);
        }

        .logo p {
            color: #666;
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 8px;
        }

        .form-group {
            margin-bottom: 25px;
            position: relative;
        }

        .form-group label {
            display: block;
            color: #333;
            font-weight: 500;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }

        .form-group input {
            width: 100%;
            padding: 15px 20px;
            border: 2px solid #e1e5e9;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }

        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .login-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
        }

        .error-message {
            background: #fee;
            color: #d63384;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            border: 1px solid #f8d7da;
        }

        .info {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9rem;
        }

        .info a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }

        .info a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <img src="{{ url_for('static', filename='favicon.png') }}" alt="TSKMNGR Logo">
            <p>Simple Task Manager</p>
        </div>

        {% if error %}
        <div class="error-message">{{ error }}</div>
        {% endif %}

        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" placeholder="Enter your username" required>
            </div>

            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter your password" required>
            </div>

            <button type="submit" class="login-btn">Sign In</button>
        </form>

        <div class="info">
           
            <a href="{{ url_for('register') }}" style="color: #667eea;">Create new account</a>
        </div>
    </div>
</body>
</html>
'''

REGISTER_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TSKMNGR - Register</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon-32.png') }}" sizes="32x32">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon-16.png') }}" sizes="16x16">
    <link rel="shortcut icon" href="{{ url_for('static', filename='favicon.png') }}">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .register-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            padding: 40px;
            width: 100%;
            max-width: 400px;
            position: relative;
            overflow: hidden;
        }

        .register-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo img {
            width: 180px;
            height: auto;
            margin-bottom: 12px;
            transition: transform 0.3s ease;
        }

        .logo img:hover {
            transform: scale(1.05);
        }

        .logo p {
            color: #666;
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 8px;
        }

        .form-group {
            margin-bottom: 20px;
            position: relative;
        }

        .form-group label {
            display: block;
            color: #333;
            font-weight: 500;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }

        .form-group input {
            width: 100%;
            padding: 15px 20px;
            border: 2px solid #e1e5e9;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }

        .form-group input:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .register-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 10px;
        }

        .register-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
        }

        .error-message {
            background: #fee;
            color: #d63384;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            border: 1px solid #f8d7da;
        }

        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            border: 1px solid #c3e6cb;
        }

        .info {
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 0.9rem;
        }

        .info a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }

        .info a:hover {
            text-decoration: underline;
        }

        .password-requirements {
            font-size: 0.8rem;
            color: #666;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="register-container">
        <div class="logo">
            <img src="{{ url_for('static', filename='favicon.png') }}" alt="TSKMNGR Logo">
            <p>Create Your Account</p>
        </div>

        {% if error %}
        <div class="error-message">{{ error }}</div>
        {% endif %}

        {% if success %}
        <div class="success-message">{{ success }}</div>
        {% endif %}

        <form method="POST" action="{{ url_for('register') }}">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" placeholder="Choose a username" required minlength="3">
                <div class="password-requirements">At least 3 characters</div>
            </div>

            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Choose a password" required minlength="6">
                <div class="password-requirements">At least 6 characters</div>
            </div>

            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" placeholder="Confirm your password" required>
            </div>

            <button type="submit" class="register-btn">Create Account</button>
        </form>

        <div class="info">
            Already have an account? <a href="{{ url_for('login') }}">Sign in</a>
        </div>
    </div>
</body>
</html>
'''

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TSKMNGR - {{ username }}'s Tasks</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon-32.png') }}" sizes="32x32">
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon-16.png') }}" sizes="16x16">
    <link rel="shortcut icon" href="{{ url_for('static', filename='favicon.png') }}">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
        body { 
            font-family: system-ui, sans-serif; 
            background: #f5f5f5; 
            margin: 0; 
            padding: 20px;
        }
        .header-bar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header-bar h1 {
            margin: 0;
            font-size: 1.8rem;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .logout-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .logout-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        .main-container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .boards-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }
        .board-container {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
            min-height: 500px;
            position: relative;
        }
        .board-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        .board-title {
            font-size: 1.5rem;
            font-weight: bold;
            color: #333;
            margin: 0;
        }
        .board-actions {
            display: flex;
            gap: 8px;
        }
        .remove-board {
            background: #ff4757;
            color: white;
            border: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .edit-header-btn {
            background: #ffd900;
            color: #333;
            border: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .screenshot-btn {
            background: #007bff;
            color: white;
            border: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: 4px;
        }
        .screenshot-btn:hover {
            background: #0056b3;
        }
        .add-board-container {
            display: flex;
            justify-content: center;
            margin-top: 20px;
        }
        .add-board {
            background: #4CAF50;
            color: white;
            border: none;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            font-size: 24px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        .add-board:hover {
            background: #45a049;
        }
        .add-task-form {
            display: flex;
            gap: 6px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .add-task-form input[type="text"], .add-task-form input[type="date"] {
            flex: 1;
            min-width: 80px;
            padding: 6px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 12px;
        }
        .add-task-form input[name="notes"] {
            flex: 2;
            min-width: 100px;
        }
        button {
            background: #006cff;
            color: #fff;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }
        button.completed { background: #17be72; }
        button.uncomplete { background: #e0a900; color: #222; }
        button.edit-btn { background: #ffd900; color: #333; }
        button.cancel-btn { background: #bbb; color: #333; }
        ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        li {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            padding: 6px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 13px;
        }
        .task-num {
            color: #888;
            width: 15px;
            font-size: 12px;
        }
        .task-content {
            flex: 1;
            min-width: 0;
        }
        .task-name {
            font-weight: 500;
            margin-bottom: 2px;
        }
        .task-date {
            color: #666;
            font-size: 11px;
        }
        .task-notes {
            color: #777;
            font-size: 11px;
            margin-top: 2px;
            word-break: break-word;
        }
        .task-actions {
            display: flex;
            gap: 4px;
            margin-left: auto;
        }
        .task-actions button {
            padding: 3px 6px;
            font-size: 10px;
        }
        .section-title {
            font-size: 14px;
            font-weight: bold;
            color: #006cff;
            margin: 15px 0 8px 0;
        }
        .empty-list {
            color: #aaa;
            font-style: italic;
            padding: 10px 0;
        }
        .edit-form {
            display: flex;
            gap: 4px;
            flex: 1;
            align-items: flex-start;
        }
        .edit-form input {
            padding: 3px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 11px;
        }
        .completed-date {
            color: #1b8a4c;
            font-size: 10px;
            margin-left: 8px;
        }
        .header-edit-form {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .header-edit-form input {
            font-size: 1.2rem;
            font-weight: bold;
            padding: 4px 8px;
            border: 2px solid #ffd900;
            border-radius: 6px;
        }
        .task-limit-message {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 13px;
            font-weight: 500;
        }
        .task-limit-message span {
            display: inline-block;
        }
        @media (max-width: 768px) {
            .boards-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header-bar">
        <h1>TSKMNGR</h1>
        <div class="user-info">
            <span>Welcome, {{ username }}!</span>
            <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
        </div>
    </div>

    <div class="main-container">
        <div class="boards-grid">
            {% for board_id, board in boards.items() %}
            <div class="board-container" data-board-id="{{ board_id }}">
                <div class="board-header">
                    {% if request.args.get('edit_header') == board_id %}
                    <form method="post" action="{{ url_for('edit_header', board_id=board_id) }}" class="header-edit-form">
                        <input type="text" name="header_text" value="{{ board['header'] }}" maxlength="48" autofocus>
                        <button type="submit">Save</button>
                        <a href="{{ url_for('dashboard') }}"><button type="button" class="cancel-btn">Cancel</button></a>
                    </form>
                    {% else %}
                    <h2 class="board-title">{{ board['header'] }}</h2>
                    <div class="board-actions">
                        <a href="?edit_header={{ board_id }}">
                            <button type="button" class="edit-header-btn" title="Edit header">✎</button>
                        </a>
                        <button type="button" class="screenshot-btn" title="Take screenshot" onclick="takeScreenshot('{{ board_id }}')">📷</button>
                        {% if boards|length > 1 %}
                        <form method="post" action="{{ url_for('remove_board', board_id=board_id) }}" style="margin:0;">
                            <button type="submit" class="remove-board" title="Remove board" onclick="return confirm('Remove this board?')">×</button>
                        </form>
                        {% endif %}
                    </div>
                    {% endif %}
                </div>

                {% if board['active']|length < 10 %}
                <form method="post" action="{{ url_for('add_task', board_id=board_id) }}" class="add-task-form">
                    <input type="text" name="task" placeholder="New task" required maxlength="64">
                    <input type="date" name="date" value="{{ today_date }}" required>
                    <input type="text" name="notes" placeholder="Notes" maxlength="256">
                    <button type="submit">Add</button>
                </form>
                {% else %}
                <div class="task-limit-message">
                    <span id="task-limit-text"></span>
                </div>
                {% endif %}

                <div class="section-title">Active Tasks</div>
                <ul>
                    {% for task in board['active'] %}
                    <li>
                        <span class="task-num">{{ loop.index }}.</span>
                        {% if request.args.get('edit') == board_id ~ '_' ~ loop.index0 %}
                        <form method="post" action="{{ url_for('edit_task', board_id=board_id, task_idx=loop.index0) }}" class="edit-form">
                            <input type="text" name="edit_task" value="{{ task['task'] }}" required maxlength="64" style="flex:2;">
                            <input type="date" name="edit_date" value="{{ task['date'] }}" required style="flex:1;">
                            <input type="text" name="edit_notes" value="{{ task['notes'] }}" maxlength="256" style="flex:2;">
                            <button type="submit" class="completed">Save</button>
                            <a href="{{ url_for('dashboard') }}"><button type="button" class="cancel-btn">Cancel</button></a>
                        </form>
                        {% else %}
                        <div class="task-content">
                            <div class="task-name">{{ task['task'] }}</div>
                            <div class="task-date">Due: {{ task['date'] }}</div>
                            {% if task['notes'] %}
                            <div class="task-notes">{{ task['notes_html']|safe }}</div>
                            {% endif %}
                        </div>
                        <div class="task-actions">
                            <a href="?edit={{ board_id }}_{{ loop.index0 }}">
                                <button type="button" class="edit-btn">Edit</button>
                            </a>
                            <form method="post" action="{{ url_for('complete', board_id=board_id, task_idx=loop.index0) }}" style="margin:0;">
                                <button type="submit" class="completed">Done</button>
                            </form>
                        </div>
                        {% endif %}
                    </li>
                    {% endfor %}
                    {% if board['active']|length == 0 %}
                    <li class="empty-list">No active tasks.</li>
                    {% endif %}
                </ul>

                <div class="section-title">Completed Tasks</div>
                <ul>
                    {% for task in board['completed'] %}
                    <li>
                        <span class="task-num">✓</span>
                        <div class="task-content">
                            <div class="task-name">{{ task['task'] }}</div>
                            <div class="task-date">Due: {{ task['date'] }}</div>
                            {% if task['notes'] %}
                            <div class="task-notes">{{ task['notes_html']|safe }}</div>
                            {% endif %}
                            <div class="completed-date">Completed: {{ task['completed_on'] }}</div>
                        </div>
                        <div class="task-actions">
                            <form method="post" action="{{ url_for('uncomplete', board_id=board_id, task_id=task.id) }}" style="margin:0;">
                                <button type="submit" class="uncomplete">Undo</button>
                            </form>
                        </div>
                    </li>
                    {% endfor %}
                    {% if board['completed']|length == 0 %}
                    <li class="empty-list">No completed tasks yet.</li>
                    {% endif %}
                </ul>
            </div>
            {% endfor %}
        </div>

        {% if boards|length < 4 %}
        <div class="add-board-container">
            <form method="post" action="{{ url_for('add_board') }}">
                <button type="submit" class="add-board" title="Add new board">+</button>
            </form>
        </div>
        {% endif %}
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script>
        async function takeScreenshot(boardId) {
            try {
                // Find the specific board container
                const boardElement = document.querySelector(`[data-board-id="${boardId}"]`);
                
                if (!boardElement) {
                    alert('Board not found for screenshot');
                    return;
                }

                // Show loading message
                const loadingMsg = document.createElement('div');
                loadingMsg.innerHTML = '📷 Taking screenshot...';
                loadingMsg.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: #007bff;
                    color: white;
                    padding: 10px 15px;
                    border-radius: 6px;
                    z-index: 1000;
                    font-size: 14px;
                `;
                document.body.appendChild(loadingMsg);

                // Configure html2canvas options
                const canvas = await html2canvas(boardElement, {
                    backgroundColor: '#ffffff',
                    scale: 2, // Higher quality
                    useCORS: true,
                    allowTaint: true,
                    scrollX: 0,
                    scrollY: 0,
                    width: boardElement.offsetWidth,
                    height: boardElement.offsetHeight
                });

                // Remove loading message
                document.body.removeChild(loadingMsg);

                // Get board title for filename
                const boardTitle = boardElement.querySelector('.board-title')?.textContent || 'Board';
                const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
                const filename = `${boardTitle.replace(/[^a-zA-Z0-9]/g, '_')}_${timestamp}.png`;

                // Convert canvas to blob and download
                canvas.toBlob((blob) => {
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(url);
                    
                    // Show success message
                    showNotification('📷 Screenshot saved!', 'success');
                }, 'image/png');

            } catch (error) {
                console.error('Screenshot failed:', error);
                showNotification('❌ Screenshot failed. Please try again.', 'error');
            }
        }

        function showNotification(message, type) {
            const notification = document.createElement('div');
            notification.innerHTML = message;
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: ${type === 'success' ? '#28a745' : '#dc3545'};
                color: white;
                padding: 12px 18px;
                border-radius: 6px;
                z-index: 1000;
                font-size: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            `;
            document.body.appendChild(notification);
            
            setTimeout(() => {
                if (notification.parentNode) {
                    document.body.removeChild(notification);
                }
            }, 3000);
        }

        // Random humorous task limit messages
        function setRandomTaskLimitMessage() {
            const messages = [
                "⚠️ Task limit reached (10/10)—guess this \"lightweight tool\" skipped leg day.",
                "⚠️ Task limit reached (10/10)—so lightweight it can't lift one more.",
                "⚠️ Task limit reached (10/10)—the \"lightweight tool\" just tapped out.",
                "⚠️ Task limit reached (10/10)—lightweight tool; heavyweight boundaries.",
                "⚠️ Task limit reached (10/10)—so lightweight, it's allergic to tasks."
            ];
            
            const taskLimitElement = document.getElementById('task-limit-text');
            if (taskLimitElement) {
                const randomMessage = messages[Math.floor(Math.random() * messages.length)];
                taskLimitElement.textContent = randomMessage;
                console.log('Set random task limit message:', randomMessage);
            }
        }

        // Set random message on page load
        document.addEventListener('DOMContentLoaded', setRandomTaskLimitMessage);
    </script>
</body>
</html>
"""
