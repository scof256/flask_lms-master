-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('student','admin')) NOT NULL,
    department TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Questions table
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
    correct INTEGER NOT NULL
);

-- Prompts table
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY,
    department TEXT NOT NULL,
    prompt_text TEXT NOT NULL
);

-- Store student progress and answers
CREATE TABLE IF NOT EXISTS student_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER,
    prompt_id INTEGER,
    answer TEXT,
    is_correct BOOLEAN,
    generated_response TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    CHECK (question_id IS NOT NULL OR prompt_id IS NOT NULL)
);

-- Default accounts will be created by init_db.py
