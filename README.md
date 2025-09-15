# TSKMNGR - Task Manager Web Application

A simple, elegant task management web application built with Flask and PostgreSQL. Create boards, manage tasks, and track your productivity with an intuitive web interface.

## Screenshots

### Login Page
![Login Page](screenshots/login-page.png)

The clean, modern login interface with a beautiful gradient background provides secure user authentication.

### Dashboard
![Dashboard](screenshots/dashboard.png)

The main dashboard shows your organized boards with active and completed tasks. Features include:
- Multiple board management (Consultant Cloud, Clyde, Home, Life stuff)
- Task creation with due dates and notes
- Edit and Done buttons for task management
- Color-coded task status indicators
- Completed tasks tracking

## Features

- **User Authentication**: Secure registration and login system
- **Board Management**: Create up to 4 custom boards per user
- **Task Organization**: Add, edit, complete, and track tasks with due dates and notes
- **Task Limitations**: Maximum 10 active tasks per board to maintain focus
- **Responsive Design**: Clean, user-friendly web interface
- **Data Persistence**: PostgreSQL database with comprehensive logging

## Tech Stack

- **Backend**: Python, Flask
- **Database**: PostgreSQL
- **Authentication**: Session-based with Werkzeug password hashing
- **Deployment**: Gunicorn WSGI server
- **Environment**: python-dotenv for configuration

## Installation

1. Clone the repository:
```bash
git clone https://github.com/fizzy2562/TSKMNGR.git
cd TSKMNGR
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file with:
```
SECRET_KEY=your_secret_key_here
DATABASE_URL=your_postgresql_connection_string
```

4. Initialize the database:
```bash
python database.py
```

5. Run the application:
```bash
python app.py
```

## Usage

1. **Register/Login**: Create an account or sign in
2. **Create Boards**: Add up to 4 boards to organize different areas of work
3. **Add Tasks**: Create tasks with titles, due dates, and detailed notes
4. **Track Progress**: Mark tasks complete and monitor your productivity
5. **Manage Workflow**: Edit, complete, or remove tasks as needed

## Database Schema

- **Users**: User accounts with authentication
- **Boards**: Organizational containers (max 4 per user)
- **Tasks**: Individual task items (max 10 active per board)

## API Endpoints

- `/` - Home/Dashboard
- `/login` - User authentication
- `/register` - Account creation
- `/dashboard` - Main task management interface
- `/add_board` - Create new board
- `/add_task` - Add new task
- `/complete_task` - Mark task as complete

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

Open source project - feel free to use and modify as needed.