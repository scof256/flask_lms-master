# /flask_lms-master/init_db.py
import os
import sqlite3
from werkzeug.security import generate_password_hash

# Create instance directory if it doesn't exist
if not os.path.exists('instance'):
    os.makedirs('instance')

# Initialize database
conn = sqlite3.connect('instance/lms.db')
c = conn.cursor()

# Modify CREATE TABLE users to include 'approved' column, keeping existing structure
c.executescript('''
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS student_progress;
DROP TABLE IF EXISTS tutor_chats;  -- Drop existing table if it exists

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,
    approved INTEGER DEFAULT 0
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

CREATE TABLE tutor_chats (  -- New table for tutor chats
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    prompt_id INTEGER,  -- Link to the prompt (can be NULL for general questions)
    message TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (prompt_id) REFERENCES student_progress (prompt_id) -- Corrected foreign key
);
''')

# Create initial admin and test student, now including 'approved' status
admin_password = generate_password_hash('admin123')
student_password = generate_password_hash('student123')

c.execute('INSERT INTO users (username, password, email, role, approved) VALUES (?, ?, ?, ?, ?)',
         ('admin', admin_password, 'admin@example.com', 'admin', 1))
c.execute('INSERT INTO users (username, password, email, role, approved) VALUES (?, ?, ?, ?, ?)',
         ('student', student_password, 'student@example.com', 'student', 0))

conn.commit()
conn.close()

print('Database initialized successfully!')
print('Default users created:')
print('Admin - username: admin, password: admin123')
print('Student - username: student, password: student123 (pending approval)')