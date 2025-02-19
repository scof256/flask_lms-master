# /flask_lms-master/app.py (REVISED)

from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, flash, make_response, g
import openai
import markdown
import sqlite3
from datetime import datetime, timedelta
import os
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import html
import json

# Load questions and prompts from JSON files
def load_json_data():
    with open('questions.json', 'r') as f:
        questions = json.load(f)
    with open('prompts.json', 'r') as f:
        prompts = json.load(f)
    return questions, prompts

# Initialize questions and prompts
questions, prompts = load_json_data()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Replace with a secure secret key

# Database helper function
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('instance/lms.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Initialize Flask application context
@app.before_request
def before_request():
    g.db = get_db()

@app.teardown_appcontext
def teardown_db(error):
    close_db()

# Login required decorator
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped_view(*args, **kwargs):
            if not session.get('user_id'):
                flash('Please log in first.', 'warning')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Access denied.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapped_view
    return decorator

# Root route
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    elif session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        db = get_db()
        hashed_password = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, email, password, role, approved) VALUES (?, ?, ?, ?, ?)",
                       (username, email, hashed_password, 'student', 0))
            db.commit()
            flash('Account created! Await admin approval.', 'info')
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'danger')
        finally:
            db.close()
        return redirect(url_for('login'))

    return render_template('signup.html')

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db.close()

        if user and check_password_hash(user['password'], password):
            if not user['approved']:
                flash('Your account is pending admin approval.', 'warning')
                return redirect(url_for('login'))

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))

        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Student dashboard
@app.route('/student/dashboard')
@login_required(role='student')
def student_dashboard():
    try:
        db = get_db()
        total_questions = len(questions)
        total_prompts = len(prompts)

        category_progress = db.execute('''
            SELECT q.category,
                   COUNT(DISTINCT sp.question_id) as completed,
                   COUNT(DISTINCT q.id) as total,
                   COUNT(DISTINCT CASE WHEN sp.is_correct = 1 THEN sp.question_id END) as correct
            FROM questions q
            LEFT JOIN student_progress sp ON sp.question_id = q.id
                AND sp.user_id = ?
            GROUP BY q.category
        ''', (session['user_id'],)).fetchall()

        progress_stats = db.execute('''
            SELECT
                COUNT(DISTINCT question_id) as completed_questions,
                COUNT(DISTINCT CASE WHEN is_correct = 1 THEN question_id END) as correct_answers,
                COUNT(DISTINCT prompt_id) as completed_prompts
            FROM student_progress
            WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()

        upcoming_categories = []
        for cat in category_progress:
            if cat['completed'] < cat['total']:
                color = 'primary' if cat['category'].startswith('Key') else \
                        'info' if cat['category'].startswith('Real') else \
                        'warning' if cat['category'].startswith('Discover') else 'success'
                icon = 'book' if cat['category'].startswith('Key') else \
                       'chart-line' if cat['category'].startswith('Real') else \
                       'lightbulb' if cat['category'].startswith('Discover') else 'cog'
                upcoming_categories.append({
                    'name': cat['category'],
                    'completed': cat['completed'],
                    'total': cat['total'],
                    'color': color,
                    'icon': icon
                })

        daily_progress = db.execute('''
            SELECT
                DATE(created_at) as date,
                COUNT(DISTINCT question_id) + COUNT(DISTINCT prompt_id) as completed_items
            FROM student_progress
            WHERE user_id = ?
            AND created_at >= DATE('now', '-6 days')
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (session['user_id'],)).fetchall()

        today = datetime.now().date()
        dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
        progress_data = {
            'labels': ['Day ' + str(i+1) for i in range(7)],
            'data': [0] * 7
        }

        for prog in daily_progress:
            try:
                day_index = dates.index(prog['date'])
                progress_data['data'][day_index] = prog['completed_items']
            except ValueError:
                continue

        # Get current prompt for the student with department information in a single query
        current_prompt = db.execute("""
            SELECT p.id, p.department, p.prompt_text, COUNT(sp.id) as attempts
            FROM prompts p
            LEFT JOIN student_progress sp ON sp.prompt_id = p.id AND sp.user_id = ?
            GROUP BY p.id
            HAVING attempts = 0 OR attempts IS NULL
            ORDER BY p.id
            LIMIT 1
        """, (session['user_id'],)).fetchone()

        return render_template('student_dashboard.html',
                             total_questions=total_questions,
                             total_prompts=total_prompts,
                             completed_questions=progress_stats['completed_questions'] or 0,
                             completed_prompts=progress_stats['completed_prompts'] or 0,
                             correct_answers=progress_stats['correct_answers'] or 0,
                             category_progress=category_progress,
                             upcoming_categories=upcoming_categories[:3],
                             progress_data=progress_data,
                             current_prompt=current_prompt)

    except sqlite3.Error as e:
        flash('Error loading progress data', 'error')
        return redirect(url_for('index'))
    finally:
        db.close()

# Admin dashboard
@app.route('/admin/dashboard')
@login_required(role='admin')
def admin_dashboard():
    db = get_db()
    students = db.execute('''
        SELECT u.id, u.username, u.email, u.approved,
               COUNT(DISTINCT sp.question_id) as questions_completed,
               COUNT(DISTINCT sp.prompt_id) as prompts_completed
        FROM users u
        LEFT JOIN student_progress sp ON sp.user_id = u.id
        WHERE u.role = 'student'
        GROUP BY u.id
    ''').fetchall()
    pending_users = [student for student in students if not student['approved']]
    approved_users = [student for student in students if student['approved']]

    db.close()
    return render_template('admin_dashboard.html', students=approved_users, pending_users=pending_users)


@app.route('/admin/student/<int:student_id>')
@login_required(role='admin')
def student_detail(student_id):
    db = get_db()
    student = db.execute('SELECT * FROM users WHERE id = ? AND role = "student"',
                        (student_id,)).fetchone()
    if not student:
        db.close()
        flash('Student not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    progress = db.execute('''
        SELECT
            sp.*,
            q.question,
            q.category,
            datetime(sp.created_at) as created_at,
            p.prompt_text
        FROM student_progress sp
        LEFT JOIN questions q ON q.id = sp.question_id
        LEFT JOIN prompts p ON p.id = sp.prompt_id
        WHERE sp.user_id = ?
        ORDER BY sp.created_at DESC
    ''', (student_id,)).fetchall()

    tutor_history = db.execute('''
        SELECT *
        FROM tutor_chats
        WHERE user_id = ?
        ORDER BY created_at ASC
    ''', (student_id,)).fetchall()

    db.close()

    # Convert tutor_history to a list of dictionaries
    tutor_history_dicts = [dict(row) for row in tutor_history]

    # --- CORRECTED SECTION ---
    # Convert progress to a list of dictionaries *and* decode HTML entities
    progress_dicts = []
    for row in progress:
        row_dict = dict(row)  # Convert the Row object to a dictionary
        if row_dict['generated_response']:
            row_dict['generated_response'] = html.unescape(row_dict['generated_response'])
        progress_dicts.append(row_dict)
    # --- END CORRECTED SECTION ---

    return render_template('admin/student_detail.html',
                         student=student,
                         progress=progress_dicts,  # Pass the list of dictionaries
                         tutor_history=tutor_history_dicts)


# Route for admin to approve a pending user
@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required(role='admin')
def approve_user(user_id):
    db = get_db()
    db.execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    flash('User approved successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# LLM Setup (Gemini)
OPENAI_API_KEY = "AIzaSyB67xwYbaD7vUCVYoJoRxG6FlFT5dEq-DQ"  # Replace
model = "gemini-2.0-flash-exp"

openai_client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Load questions and prompts from JSON files
def load_json_data():
    with open('questions.json', 'r') as f:
        questions = json.load(f)
    with open('prompts.json', 'r') as f:
        prompts = json.load(f)
    return questions, prompts

# Routes for progress tracking
@app.route('/submit_answer', methods=['POST'])
@login_required(role='student')
def submit_answer():
    data = request.get_json()
    question_id = data.get('question_id')
    selected_answer = data.get('selected_answer')
    is_correct = data.get('is_correct')

    db = get_db()
    try:
        db.execute('''
            INSERT INTO student_progress
            (user_id, question_id, answer, is_correct)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], question_id, str(selected_answer), is_correct))
        db.commit()
        return jsonify({"success": True})
    except sqlite3.Error as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()

@app.route('/submit_prompt_response', methods=['POST'])
@login_required(role='student')
def submit_prompt_response():
    data = request.get_json()
    prompt_id = data.get('prompt_id')
    response = data.get('response')

    db = get_db()
    try:
        db.execute('''
            INSERT INTO student_progress
            (user_id, prompt_id, generated_response)
            VALUES (?, ?, ?)
        ''', (session['user_id'], prompt_id, response))
        db.commit()
        return jsonify({"success": True})
    except sqlite3.Error as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()

@app.route('/get_progress')
@login_required(role='student')
def get_progress():
    db = get_db()
    try:
        completed_questions = db.execute('''
            SELECT question_id
            FROM student_progress
            WHERE user_id = ? AND question_id IS NOT NULL AND is_correct = 1
        ''', (session['user_id'],)).fetchall()

        completed_prompts = db.execute('''
            SELECT prompt_id
            FROM student_progress
            WHERE user_id = ? AND prompt_id IS NOT NULL
        ''', (session['user_id'],)).fetchall()

        questions_progress = db.execute('''
            SELECT COUNT(DISTINCT question_id) as completed,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM student_progress
            WHERE user_id = ? AND question_id IS NOT NULL
        ''', (session['user_id'],)).fetchone()

        prompts_count = db.execute('''
            SELECT COUNT(DISTINCT prompt_id) as completed
            FROM student_progress
            WHERE user_id = ? AND prompt_id IS NOT NULL
        ''', (session['user_id'],)).fetchone()

        return jsonify({
            "success": True,
            "questions_completed": [q['question_id'] for q in completed_questions],
            "questions_correct": questions_progress['correct'],
            "prompts_completed": [p['prompt_id'] for p in completed_prompts],
            "total_completed_questions": questions_progress['completed'],
            "total_completed_prompts": prompts_count['completed']
        })
    except sqlite3.Error as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()

# For consistent state management across sessions
def get_user_progress_index():
    if 'user_id' not in session:
        return 0, 0

    db = get_db()
    try:
        question_progress = db.execute('''
            SELECT MAX(question_id) as last_question
            FROM student_progress
            WHERE user_id = ? AND question_id IS NOT NULL
        ''', (session['user_id'],)).fetchone()

        prompt_progress = db.execute('''
            SELECT MAX(prompt_id) as last_prompt
            FROM student_progress
            WHERE user_id = ? AND prompt_id IS NOT NULL
        ''', (session['user_id'],)).fetchone()

        return (
            (question_progress['last_question'] or 0) + 1,
            (prompt_progress['last_prompt'] or 0) + 1
        )
    except sqlite3.Error as e:
        print(f"Error getting progress index: {e}")
        return 0, 0
    finally:
        db.close()

# Route for getting current question
@app.route('/get_question')
@login_required(role='student')
def get_question():
    index = int(request.args.get('index', 0))
    if 0 <= index < len(questions):
        return jsonify({
            "success": True,
            "question": questions[index],
            "total": len(questions),
            "prompt_task": prompts[index]['prompt_text'] if index < len(prompts) else None,
            "department": prompts[index]['department'] if index < len(prompts) else None
        })
    return jsonify({"success": False, "message": "Question not found"})

# Route for generating responses from prompts
@app.route('/generate_from_prompt', methods=['POST'])
@login_required(role='student')
def generate_from_prompt():
    data = request.get_json()
    user_request = data.get("prompt", "")
    is_advanced = data.get("advanced", False)

    if not user_request:
        return jsonify({"success": False, "message": "Prompt cannot be empty."})

    if is_advanced:
        prompt_for_llm = f"""
Generate an short advanced prompt templates based on the user_request, optimized for expert-level AI use.
The prompt should be mildly detailed but understandable for new AI users to learn how to created short advanced prompts, immediately usable, without any titles like 'Prompt:'etc, no introductory or explanatory text. Return only the prompt with nothing else.

user_request:
{user_request}

Improved Expert Prompt:
"""
    else:
        prompt_for_llm = f"""
Generate an simple concise prompt based on the user_request, to be easily understood and used by beginners in AI.
The prompt should be understandable and immediately usable for someone new to AI, without any introductory or explanatory text.

user_request:
{user_request}

Simplified Beginner Prompt:
"""

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt_for_llm}]
        )
        answer = response.choices[0].message.content.strip()
        formatted_answer = markdown.markdown(answer)
    except Exception as e:
        error_message = f"Error generating response from LLM: {str(e)}"
        app.logger.error(error_message)
        return jsonify({"success": False, "message": error_message}), 500

    return jsonify({"success": True, "answer": formatted_answer})


# Route for tutor chat
@app.route('/tutor', methods=['POST'])
@login_required(role='student')
def tutor_chat():
    data = request.get_json()
    conversation = data.get('conversation', [])
    current_prompt_id = data.get('prompt_id')

    db = get_db()
    try:
        # Store the user's message
        for message in conversation:
            if message['role'] == 'user':
                db.execute('''
                    INSERT INTO tutor_chats (user_id, prompt_id, message, role)
                    VALUES (?, ?, ?, ?)
                ''', (session['user_id'], current_prompt_id, message['content'], message['role']))
        db.commit()

        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful AI tutor specializing in AI and prompt engineering. End by inquiring if student has understood or needs further explanation or assistance to keep the conversation flowing. Please use markdown formatting in your responses."},
                *[{"role": msg["role"], "content": msg["content"]} for msg in conversation]
            ]
        )
        markdown_content = markdown.markdown(response.choices[0].message.content)

        # Store the assistant's response
        db.execute('''
            INSERT INTO tutor_chats (user_id, prompt_id, message, role)
            VALUES (?, ?, ?, ?)
        ''', (session['user_id'], current_prompt_id, markdown_content, 'assistant'))
        db.commit()


        return jsonify({
            "success": True,
            "answer": markdown_content
        })
    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "message": f"Error getting tutor response: {str(e)}"
        }), 500
    finally:
        db.close()

# Routes for getting all questions and prompts
@app.route('/get_all_questions')
@login_required(role='student')
def get_all_questions():
    return jsonify({
        "success": True,
        "questions": questions
    })

@app.route('/get_all_prompts')
@login_required(role='student')
def get_all_prompts():
    return jsonify({
        "success": True,
        "prompts": prompts
    })

# Helper functions to fetch data
def get_student_by_id(user_id):
    db = get_db()
    student = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    return student  # Remove db.close() to let Flask handle connection lifecycle

def get_progress_for_student(user_id):
    try:
        db = get_db()
        progress = db.execute('''
            SELECT
                sp.*,
                q.question,
                q.category,
                datetime(sp.created_at) as created_at,
                p.prompt_text
            FROM student_progress sp
            LEFT JOIN questions q ON q.id = sp.question_id
            LEFT JOIN prompts p ON p.id = sp.prompt_id
            WHERE sp.user_id = ?
            ORDER BY sp.created_at DESC
        ''', (user_id,)).fetchall()
        # Convert progress to a list of dictionaries *and* decode HTML entities
        progress_dicts = []
        for row in progress:
            row_dict = dict(row)  # Convert the Row object to a dictionary
            if row_dict['generated_response']:
                row_dict['generated_response'] = html.unescape(row_dict['generated_response'])
            progress_dicts.append(row_dict)
        return progress_dicts
    except Exception as e:
        app.logger.error(f"Database error in get_progress_for_student: {str(e)}")
        raise

def get_tutor_history_for_student(user_id):
    db = get_db()
    tutor_history = db.execute('''
        SELECT *
        FROM tutor_chats
        WHERE user_id = ?
        ORDER BY created_at ASC
    ''', (user_id,)).fetchall()
    db.close()
    return [dict(row) for row in tutor_history]  # Convert to list of dicts


@app.route('/student_detail')
@login_required(role='student')  # Add login_required decorator
def student_detail_student():
    # Verify the user is a student
    if session.get('role') != 'student':
        return redirect(url_for('index'))

    # Fetch the student details
    student = get_student_by_id(session['user_id'])
    if not student:  # Add a check if student is not found
        flash('Student not found.', 'danger')
        return redirect(url_for('student_dashboard'))

    # Get progress and tutor_history data for the student
    progress = get_progress_for_student(session['user_id'])
    tutor_history = get_tutor_history_for_student(session['user_id'])
    return render_template('student_detail.html', student=student, progress=progress, tutor_history=tutor_history)



# Context processor to make 'prompts' available to all templates
@app.context_processor
def inject_prompts():
    """Makes the 'prompts' data available to all templates."""
    return dict(prompts=prompts)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)