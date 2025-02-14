# /flask_lms-master/app.py (REVISED)

from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session, flash, make_response
import openai
import markdown
import sqlite3
from datetime import datetime, timedelta
import os
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import html

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Replace with a secure secret key

# Database helper function
def get_db():
    db = sqlite3.connect('instance/lms.db')
    db.row_factory = sqlite3.Row
    return db

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
    db = get_db()
    try:
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

    except sqlite3.Error as e:
        flash('Error loading progress data', 'error')
        return redirect(url_for('index'))
    finally:
        db.close()

    return render_template('student_dashboard.html',
                         total_questions=total_questions,
                         total_prompts=total_prompts,
                         completed_questions=progress_stats['completed_questions'] or 0,
                         completed_prompts=progress_stats['completed_prompts'] or 0,
                         correct_answers=progress_stats['correct_answers'] or 0,
                         category_progress=category_progress,
                         upcoming_categories=upcoming_categories[:3],
                         progress_data=progress_data)

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

# Data (Questions and Prompts)
questions = [
    {"id": 1, "category": "Key Definitions", "question": "What is Artificial Intelligence (AI) in simple terms?", "options": ["A computer system that mimics human intelligence", "A process that only involves manual calculations", "A machine that can only perform manual tasks", "A type of computer virus"], "correct": 0},
    {"id": 2, "category": "Key Definitions", "question": "What are the key differences between AI, machine learning, and deep learning?", "options": ["Machine learning and deep learning are not part of AI", "Deep learning is an outdated term for AI, while machine learning is a new term", "AI is a broad field, machine learning is a method to achieve AI through data learning, and deep learning is a specialized technique using neural networks", "All three terms refer to the exact same concept with no differences"], "correct": 2},
    {"id": 3, "category": "Key Definitions", "question": "How does AI process information compared to how humans think?", "options": ["AI processes information by randomly guessing outcomes", "AI and human thought are exactly identical in every way", "Humans process information in binary code, similar to computers", "AI uses algorithms and statistical models, while human thinking involves cognitive and emotional processing"], "correct": 3},
    {"id": 4, "category": "Real-world Impact", "question": "How is AI transforming different industries (healthcare, finance, education, etc.)?", "options": ["By only replacing outdated computer systems without any added benefits", "By creating more bureaucratic hurdles in every industry", "By eliminating human jobs entirely in every sector", "By automating tasks, enhancing data analysis, personalizing services, and improving decision-making processes"], "correct": 3},
    {"id": 5, "category": "Real-world Impact", "question": "What are some surprising ways AI is being used today?", "options": ["Solely for automating simple calculations", "Exclusively for military applications", "Primarily for creative arts, wildlife conservation, and predictive maintenance", "Only for repetitive manufacturing tasks"], "correct": 2},
    {"id": 6, "category": "Real-world Impact", "question": "How can AI impact job markets in the future?", "options": ["It can create new opportunities while displacing some traditional roles", "It will only eliminate jobs without creating any new ones", "It will have no effect on job markets at all", "It will replace every human worker in all industries"], "correct": 0},
    {"id": 7, "category": "Discover Prompt Engineering", "question": "What is prompt engineering, and why is it important when using AI?", "options": ["It is a way to manually override AI outputs", "It is irrelevant to AI performance", "It involves designing input queries to guide AI responses effectively", "It is only used in programming hardware devices"], "correct": 2},
    {"id": 8, "category": "Discover Prompt Engineering", "question": "What makes a good AI prompt? Give examples of good vs. bad prompts.", "options": ["A good prompt is one that is extremely short and leaves everything open", "A good prompt is one that uses slang and informal language exclusively", "A good prompt includes random unrelated information", "A good prompt is clear, specific, and provides context; a bad prompt is vague and ambiguous"], "correct": 3},
    {"id": 9, "category": "Discover Prompt Engineering", "question": "How do small changes in prompts affect AI responses?", "options": ["They only affect the speed of processing", "They have no effect on the outputs", "Minor modifications can lead to significantly different outputs", "They result in the AI refusing to answer"], "correct": 2},
    {"id": 10, "category": "LLM Fundamentals", "question": "What is a Large Language Model (LLM), and how does it work?", "options": ["It works by randomly generating words without any training", "It is a small database of pre-written responses", "It is an AI system that predicts and generates human-like language from large text datasets", "It is a tool exclusively for translating languages without any predictive capabilities"], "correct": 2},
    {"id": 11, "category": "LLM Fundamentals", "question": "How do LLMs learn from data?", "options": ["By adjusting internal parameters through training algorithms on large datasets", "By simply copying human-written text without any processing", "By operating on pre-programmed rules without data", "By memorizing every sentence without learning any patterns"], "correct": 0},
    {"id": 12, "category": "LLM Fundamentals", "question": "What are the limitations of LLMs when answering questions?", "options": ["They always provide factually correct and context-aware answers", "They have unlimited access to all real-time data", "They may produce plausible but incorrect answers and struggle with nuanced contexts", "They only function as simple calculators"], "correct": 2},
    {"id": 13, "category": "Crafting Effective Prompts", "question": "What are three techniques for making an AI prompt clearer and more useful?", "options": ["Using as few words as possible without details", "Being specific, providing context, and using step-by-step instructions", "Writing in a confusing manner intentionally", "Being vague, avoiding context, and using random instructions"], "correct": 1},
    {"id": 14, "category": "Crafting Effective Prompts", "question": "How does adding context improve AI responses?", "options": ["It only makes the prompt longer without any benefits", "It forces the AI to generate generic responses", "It helps AI understand background information for more accurate responses", "It confuses the AI by providing too much irrelevant detail"], "correct": 2},
    {"id": 15, "category": "Crafting Effective Prompts", "question": "How can you design a prompt that helps AI generate creative answers?", "options": ["By asking very strict, yes-or-no questions", "By including open-ended questions and creative constraints", "By avoiding any form of instruction", "By limiting the prompt to factual data only"], "correct": 1},
    {"id": 16, "category": "Iterative Refinement", "question": "What is iterative refinement, and how can it improve AI-generated content?", "options": ["Ignoring initial output and starting from scratch every time", "Repeatedly revising and enhancing outputs for clarity and accuracy", "A one-time generation process with no further revisions", "Automatically deleting unsatisfactory outputs without improvement"], "correct": 1},
    {"id": 17, "category": "Iterative Refinement", "question": "How can you refine a weak AI-generated response to make it better?", "options": ["By simply copying the weak response without changes", "By reducing the amount of context provided", "By providing additional context and clarifying instructions", "By completely ignoring any user feedback"], "correct": 2},
    {"id": 18, "category": "Iterative Refinement", "question": "What are common mistakes people make when refining AI-generated content?", "options": ["Always leaving the response unchanged", "Providing too much clear direction", "Using iterative refinement only once", "Over-editing, ambiguous context, and unclear objectives"], "correct": 3},
    {"id": 19, "category": "Few-shot Prompting", "question": "What is few-shot prompting, and how does it help AI understand instructions better?", "options": ["It overloads the AI with too many examples to confuse it", "It provides a few examples to guide the AI's understanding and response", "It relies on a single example to guide AI responses", "It gives the AI no examples at all"], "correct": 1},
    {"id": 20, "category": "Few-shot Prompting", "question": "How does few-shot prompting compare to zero-shot and one-shot prompting?", "options": ["All three methods provide the same level of instruction", "One-shot provides more examples than few-shot", "Few-shot uses several examples, one-shot uses one, and zero-shot uses none", "Zero-shot provides the most detailed guidance"], "correct": 2},
    {"id": 21, "category": "Few-shot Prompting", "question": "Can you create an example of a few-shot prompt for summarizing news articles?", "options": ["A prompt that provides examples of weather reports instead of news summaries", "A prompt including multiple examples of news summaries, then asking for a summary", "A prompt that only asks 'Summarize this article'", "A prompt that instructs the AI to ignore all given examples"], "correct": 1},
    {"id": 22, "category": "Applying AI for Productivity", "question": "How can AI help professionals be more productive in their daily tasks?", "options": ["By complicating simple tasks with unnecessary steps", "By only focusing on creative tasks", "By automating repetitive tasks and assisting with scheduling", "By replacing all human input completely"], "correct": 2},
    {"id": 23, "category": "Applying AI for Productivity", "question": "What are three AI-powered tools that can help with project management?", "options": ["Manual spreadsheets with no AI features", "Only email clients and calendar apps without AI integration", "Traditional paper planners", "Task automation software, AI-based scheduling tools, and intelligent analytics platforms"], "correct": 3},
    {"id": 24, "category": "Applying AI for Productivity", "question": "How can AI assist in writing, summarizing, and editing documents?", "options": ["By only providing spell-check functionalities", "By disregarding grammar and context completely", "By completely rewriting documents without user input", "By generating drafts, summarizing content, and suggesting edits"], "correct": 3},
    {"id": 25, "category": "Types of AI Tools", "question": "What are the main categories of AI tools, and what are they used for?", "options": ["They are all generic tools with no specialized functions", "Only tools for playing games", "From natural language processing to computer vision, used for tasks like text analysis and image recognition", "They are only used for data storage"], "correct": 2},
    {"id": 26, "category": "Types of AI Tools", "question": "How do AI-powered text generators differ from AI-powered image generators?", "options": ["Text generators can create visuals, while image generators can create text", "Text generators are only used for code, and image generators for videos", "They both generate identical content in the same format", "Text generators produce written content, and image generators create visuals using specialized algorithms"], "correct": 3},
    {"id": 27, "category": "Types of AI Tools", "question": "What are some AI-powered tools for automating repetitive office tasks?", "options": ["Only manual typewriters", "Email filtering, scheduling assistants, and data entry automation software", "Paper-based filing systems", "Traditional calculators"], "correct": 1},
    {"id": 28, "category": "Integration Strategies", "question": "What are the steps to successfully integrate AI into a business workflow?", "options": ["Implementing AI without any testing or assessment", "Only purchasing the most expensive AI tool without planning", "Immediately replacing all human workers with AI", "Assessing needs, selecting tools, piloting solutions, and scaling based on feedback"], "correct": 3},
    {"id": 29, "category": "Integration Strategies", "question": "What are some common challenges when integrating AI into existing work processes?", "options": ["Only issues with the physical hardware", "There are no challenges at all", "Just the color of the AI interface", "Data quality issues, resistance to change, and lack of technical expertise"], "correct": 3},
    {"id": 30, "category": "Integration Strategies", "question": "What are some examples of companies that have successfully adopted AI?", "options": ["Firms that solely focus on manual labor", "Tech giants like Google, Amazon, and IBM along with innovative startups", "Only small local businesses with no global presence", "Companies that completely avoid using any technology"], "correct": 1},
    {"id": 31, "category": "Responsible AI", "question": "What does 'responsible AI' mean, and why is it important?", "options": ["Only focusing on AI's technical performance without transparency", "Using AI without any ethical or societal considerations", "Developing AI ethically, transparently, and with societal considerations", "Developing AI solely for profit without concern for impact"], "correct": 2},
    {"id": 32, "category": "Responsible AI", "question": "What are three ethical concerns related to AI use in the workplace?", "options": ["There are no ethical concerns with AI", "Bias, privacy invasion, and lack of accountability", "Only concerns about AI's power consumption", "Only increased productivity"], "correct": 1},
    {"id": 33, "category": "Responsible AI", "question": "How can companies ensure they use AI in a responsible and ethical way?", "options": ["Ignoring ethical guidelines in favor of rapid deployment", "Focusing only on profits without considering ethics", "Implementing ethical guidelines, conducting regular audits, and ensuring transparency", "Relying solely on automated systems without oversight"], "correct": 2},
    {"id": 34, "category": "Identifying Bias and Harms", "question": "How does bias appear in AI models, and what are the consequences?", "options": ["Bias only makes AI models more efficient", "Bias is not possible in AI models", "Bias can emerge from training data leading to unfair outcomes and discrimination", "Bias in AI has no real-world consequences"], "correct": 2},
    {"id": 35, "category": "Identifying Bias and Harms", "question": "Can you find an example where AI produced biased or harmful results?", "options": ["An algorithm that treats all candidates equally without bias", "AI systems that always provide perfect, unbiased decisions", "A hiring algorithm that favored one gender due to biased historical data", "An example where AI caused harm in traffic signal timings"], "correct": 2},
    {"id": 36, "category": "Identifying Bias and Harms", "question": "What methods can be used to detect and reduce AI bias?", "options": ["Using only one type of training data without review", "Relying on biased data to test algorithms", "Ignoring bias and hoping it resolves on its own", "Bias audits, diverse datasets, and fairness testing"], "correct": 3},
    {"id": 37, "category": "Human-in-the-loop", "question": "What does 'human-in-the-loop' AI mean, and why is it useful?", "options": ["Relying on AI without any human input", "Involving human oversight to ensure accuracy, accountability, and ethics", "Removing humans entirely from the AI process", "Using humans only for manual tasks unrelated to AI"], "correct": 1},
    {"id": 38, "category": "Human-in-the-loop", "question": "How can human oversight improve AI decision-making?", "options": ["It is unnecessary if AI is powerful enough", "It slows down the process without any benefits", "It can catch errors, provide context, and guide AI decisions", "It only interferes with AI efficiency"], "correct": 2},
    {"id": 39, "category": "Human-in-the-loop", "question": "What industries benefit most from a human-in-the-loop AI approach?", "options": ["Only small-scale local businesses benefit", "All industries work best without any human oversight", "Industries like healthcare, finance, and autonomous vehicles benefit most", "Only the entertainment industry benefits"], "correct": 2},
    {"id": 40, "category": "Data Privacy and Security", "question": "How does AI handle sensitive data, and what are the risks?", "options": ["AI does not process sensitive data at all", "AI handles sensitive data without any security measures", "AI uses encryption and access controls, but risks include data breaches", "Sensitive data is never stored by AI systems"], "correct": 2},
    {"id": 41, "category": "Data Privacy and Security", "question": "What are three best practices for ensuring AI respects user privacy?", "options": ["Sharing user data openly to ensure transparency", "Using public networks for sensitive data", "Data anonymization, strict access controls, and regular security audits", "Ignoring data protection laws"], "correct": 2},
    {"id": 42, "category": "Data Privacy and Security", "question": "What are some real-world examples of AI-related data breaches?", "options": ["Data breaches only occur in non-AI systems", "Breaches in finance or healthcare due to poorly secured AI systems", "There have been no AI-related data breaches", "Data breaches are only a concern for personal computers"], "correct": 1},
    {"id": 43, "category": "AI Documentation", "question": "Why is documenting AI system behavior and decisions important?", "options": ["Documentation is unnecessary for AI systems", "It helps with transparency, auditing, and troubleshooting", "Only the code needs to be documented", "AI systems are self-documenting"], "correct": 1},
    {"id": 44, "category": "AI Documentation", "question": "What should be included in AI system documentation?", "options": ["Only the system version number", "Model parameters, data sources, limitations, and intended use", "Just the developer's name", "The cost of the system"], "correct": 1},
    {"id": 45, "category": "Future of AI", "question": "What are emerging trends in AI development?", "options": ["AI development has stopped", "Multimodal AI, quantum AI, and edge AI", "Only text-based AI will exist", "AI will become less important"], "correct": 1},
    {"id": 46, "category": "Future of AI", "question": "How might AI evolve in the next decade?", "options": ["It will completely replace humans", "It will become more collaborative, ethical, and specialized", "It will disappear entirely", "It will stay exactly the same"], "correct": 1},
    {"id": 47, "category": "AI Implementation", "question": "What are key considerations when implementing AI in a business?", "options": ["Only the cost matters", "Technical feasibility, ROI, and organizational readiness", "The color of the UI", "The office location"], "correct": 1},
    {"id": 48, "category": "AI Implementation", "question": "How can organizations prepare for AI adoption?", "options": ["No preparation is needed", "Training staff, updating processes, and assessing infrastructure", "Just buy the most expensive system", "Ignore all current processes"], "correct": 1},
    {"id": 49, "category": "AI Success Metrics", "question": "What metrics can measure AI system success?", "options": ["Only look at the cost", "Accuracy, efficiency, user satisfaction, and ROI", "Number of employees replaced", "System color scheme"], "correct": 1},
    {"id": 50, "category": "AI Success Metrics", "question": "How can organizations track AI implementation progress?", "options": ["No tracking is necessary", "KPIs, user feedback, and performance benchmarks", "Only count the number of users", "Measure office temperature"], "correct": 1}
]

prompts = [
    {"id": 1, "prompt_text": "Craft a prompt that instructs an AI to generate a concise summary of various content types—for example, a news article, a multi‑page report, legal documents, customer feedback, research articles, and executive briefings."},
    {"id": 2, "prompt_text": "Develop a prompt that asks the AI to provide clear definitions of technical or everyday terms and to explain a simple process step‑by‑step."},
    {"id": 3, "prompt_text": "Write a prompt that guides the AI to produce internal messages—such as a polite email reply and a brief company update—in a professional tone."},
    {"id": 4, "prompt_text": "Create a prompt that directs the AI to generate a meeting agenda, convert raw meeting minutes into an actionable plan, produce a detailed to‑do list, and suggest follow‑up tasks."},
    {"id": 5, "prompt_text": "Formulate a prompt that asks you to list everyday work tasks that could be streamlined or improved with AI assistance."},
    {"id": 6, "prompt_text": "Design a prompt exercise where you compare two different prompt phrasings, reflect on their outcomes, and collaborate with peers to refine your prompts."},
    {"id": 7, "prompt_text": "Create several versions of a single prompt using varying lengths and compare how the differences affect the AI’s response detail and quality."},
    {"id": 8, "prompt_text": "Write a prompt that instructs the AI to outline clear project goals and generate a business proposal—including key objectives and strategic approaches."},
    {"id": 9, "prompt_text": "Take an intentionally vague prompt and rewrite it to be clear, specific, and actionable. Compare the AI’s outputs before and after refinement."},
    {"id": 10, "prompt_text": "Develop a prompt that asks the AI to list the advantages and disadvantages (pros and cons) of a given business decision."},
    {"id": 11, "prompt_text": "Craft a prompt that directs the AI to extract key performance metrics from raw data and highlight the most important KPIs."},
    {"id": 12, "prompt_text": "Design a multi‑step prompt that guides the AI through a sequential process where each step builds on the previous one to solve a problem."},
    {"id": 13, "prompt_text": "Write a prompt that asks the AI to generate creative content—such as advertising slogans, taglines, or short catchphrases—for a product or campaign."},
    {"id": 14, "prompt_text": "Create a prompt that can be adapted by changing contextual details and instruct the AI to generate outputs in various tones (e.g., formal, friendly, humorous)."},
    {"id": 15, "prompt_text": "Craft a prompt that directs the AI to produce a set of frequently asked questions (FAQs) for an internal process and to design a customer feedback survey."},
    {"id": 16, "prompt_text": "Develop two versions of a prompt—one that includes explicit examples and one that doesn’t—and add negative constraints to steer the AI away from unwanted outputs. Compare the differences."},
    {"id": 17, "prompt_text": "Write a prompt that instructs the AI to generate a structured outline for a training session and a detailed, step‑by‑step onboarding guide for new hires."},
    {"id": 18, "prompt_text": "Create a prompt that asks the AI to transform a set of bullet points into a cohesive, flowing narrative paragraph."},
    {"id": 19, "prompt_text": "Formulate a prompt that leverages “if‑then” conditional logic to generate different outputs based on varying scenarios."},
    {"id": 20, "prompt_text": "Craft a prompt that instructs the AI to generate a variety of creative brainstorming ideas for a new marketing campaign."},
    {"id": 21, "prompt_text": "Develop a prompt that asks the AI to produce a set of insightful interview questions tailored for a new role."},
    {"id": 22, "prompt_text": "Design a prompt that initiates a multi‑turn conversation simulating a customer support interaction, ensuring coherent follow‑up responses."},
    {"id": 23, "prompt_text": "Write a prompt that encourages the AI to explain its reasoning step‑by‑step while solving a complex technical problem."},
    {"id": 24, "prompt_text": "Create a prompt that instructs the AI to generate a complete report from raw data—including summaries and visualizations such as charts."},
    {"id": 25, "prompt_text": "Develop a prompt that directs the AI to assume a specific role (for example, a project manager or consultant) and respond as that persona in a simulated scenario."},
    {"id": 26, "prompt_text": "Write a prompt that guides the AI to conduct a brainstorming session for product innovation and then generate a strategic roadmap for product development."},
    {"id": 27, "prompt_text": "Craft a prompt that instructs the AI to develop a full‑scale project proposal complete with detailed timelines, resource allocation, and key milestones."},
    {"id": 28, "prompt_text": "Create a prompt that asks the AI to translate complex technical documentation or industry jargon into clear, accessible language."},
    {"id": 29, "prompt_text": "Develop a prompt that instructs the AI to propose multiple alternative strategies for solving a specific business challenge."},
    {"id": 30, "prompt_text": "Write a multi‑step prompt that guides the AI to integrate financial data for forecasting purposes and to analyze company data to predict future sales trends."},  # Added in previous turn
    {"id": 31, "prompt_text": "Design a series of interconnected prompts where the output of one prompt serves as the input for the next, forming a complete workflow for a complex task."},
    {"id": 32, "prompt_text": "Craft a prompt that directs the AI to analyze current market trends and perform a competitor analysis—complete with visual elements like comparison charts."},
    {"id": 33, "prompt_text": "Develop a prompt that simulates a crisis scenario, asks the AI to perform a detailed risk assessment, and then structure a comprehensive business continuity plan."},
    {"id": 34, "prompt_text": "Create a prompt that instructs the AI to design a detailed customer journey map and generate multiple scenario‑based responses for customer service situations."},
    {"id": 35, "prompt_text": "Write a prompt that asks the AI to generate several versions of a sales pitch and, based on provided KPIs, to offer strategic recommendations for improvement."},
    {"id": 36, "prompt_text": "Develop a prompt that guides the AI to outline a comprehensive internal communication strategy for an organization."},
    {"id": 37, "prompt_text": "Craft a prompt that instructs the AI to generate detailed training materials for new hires, develop a complete digital marketing strategy, and outline a plan for digital transformation initiatives (including an AI adoption training roadmap)."},
    {"id": 38, "prompt_text": "Write a prompt that simulates both a negotiation dialogue for contract discussions and a strategic leadership roundtable discussion or decision‑making scenario."},
    {"id": 39, "prompt_text": "Develop a prompt that instructs the AI to perform a comparative analysis between multiple items, ideas, or strategies."},
    {"id": 40, "prompt_text": "Craft a prompt that directs the AI to conduct a detailed SWOT analysis and synthesize industry research into actionable insights—possibly culminating in an executive briefing on emerging trends."},
    {"id": 41, "prompt_text": "Create a prompt tailored for departments by instructing the AI to generate candidate screening questions for HR and analyze budget reports for the finance team."},
    {"id": 42, "prompt_text": "Develop a prompt that assists the marketing team in generating creative campaign ideas (including a multi‑month marketing calendar) and supports the IT department in diagnosing common system issues."},
    {"id": 43, "prompt_text": "Write a prompt that simulates interdepartmental project planning and instructs the AI to synthesize cross‑departmental feedback into a unified action plan."},
    {"id": 44, "prompt_text": "Craft a prompt that directs the AI to generate detailed customer personas from survey data and to create customized training content for different teams."},
    {"id": 45, "prompt_text": "Develop a prompt that asks the AI to produce a detailed compliance checklist for regulatory requirements and to generate performance review templates for managers."},
    {"id": 46, "prompt_text": "Write a prompt that instructs the AI to identify potential solutions for process bottlenecks and to generate a detailed diagram of an operational workflow."},
    {"id": 47, "prompt_text": "Create a prompt that guides the AI to draft a press release or public communication and to develop a customized crisis communication plan."},
    {"id": 48, "prompt_text": "Develop a prompt that directs the AI to analyze customer data to produce actionable insights and to generate innovative strategies for improving customer retention."},
    {"id": 49, "prompt_text": "Write a capstone prompt that instructs the AI to produce a comprehensive market entry strategy for a new product or service and to design a full‑scale, multi‑phase project plan covering planning, execution, and review."},
    {"id": 50, "prompt_text": "Craft a prompt that asks the AI to develop an executive-level briefing that outlines digital transformation initiatives, including a strategic plan and detailed project timelines."}
]



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
            "prompt_task": prompts[index]['prompt_text'] if index < len(prompts) else None
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
    db.close()
    return student

def get_progress_for_student(user_id):
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
    db.close()
     # Convert progress to a list of dictionaries *and* decode HTML entities
    progress_dicts = []
    for row in progress:
        row_dict = dict(row)  # Convert the Row object to a dictionary
        if row_dict['generated_response']:
            row_dict['generated_response'] = html.unescape(row_dict['generated_response'])
        progress_dicts.append(row_dict)
    return progress_dicts

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