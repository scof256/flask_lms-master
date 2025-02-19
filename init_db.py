# /flask_lms-master/init_db.py
import os
import sqlite3
import json
from werkzeug.security import generate_password_hash

# Create instance directory if it doesn't exist
if not os.path.exists('instance'):
    os.makedirs('instance')

# Check if database already exists
db_exists = os.path.exists('instance/lms.db')

# Ask for confirmation if database exists
if db_exists:
    response = input('Database already exists. Do you want to reset it? (y/n): ')
    if response.lower() != 'y':
        print('Database initialization cancelled.')
        exit()

# Initialize database
conn = sqlite3.connect('instance/lms.db')
c = conn.cursor()

# Create tables
c.executescript('''
DROP TABLE IF EXISTS tutor_chats;
DROP TABLE IF EXISTS student_progress;
DROP TABLE IF EXISTS prompts;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,
    approved INTEGER DEFAULT 0
);

CREATE TABLE prompts (
    id INTEGER PRIMARY KEY,
    department TEXT NOT NULL,
    prompt_text TEXT NOT NULL
);

CREATE TABLE student_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER,
    prompt_id INTEGER,
    answer TEXT,
    is_correct BOOLEAN,
    generated_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE tutor_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    prompt_id INTEGER,
    message TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (prompt_id) REFERENCES student_progress (prompt_id)
);
''')

# Create initial admin and test student accounts
admin_password = generate_password_hash('admin123')
student_password = generate_password_hash('student123')

c.execute('INSERT INTO users (username, password, email, role, approved) VALUES (?, ?, ?, ?, ?)',
         ('admin', admin_password, 'admin@example.com', 'admin', 1))
c.execute('INSERT INTO users (username, password, email, role, approved) VALUES (?, ?, ?, ?, ?)',
         ('student', student_password, 'student@example.com', 'student', 0))

# Load and insert prompts from prompts.json
with open('prompts.json', 'r') as f:
    prompts = json.load(f)

# Insert prompts into database
for prompt in prompts:
    c.execute('INSERT INTO prompts (id, department, prompt_text) VALUES (?, ?, ?)',
             (prompt['id'], prompt['department'], prompt['prompt_text']))

conn.commit()
conn.close()

print('Database initialized successfully!')
print('Default users created:')
print('Admin - username: admin, password: admin123')
print('Student - username: student, password: student123 (pending approval)')
print('Sample prompts added for Computer Science, Mathematics, and Physics departments.')