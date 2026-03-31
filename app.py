from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename
import bcrypt
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bookexchange-secret")

app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

Session(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, 'bookexchange.db')


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            full_name TEXT,
            location TEXT,
            phone TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            author TEXT,
            isbn TEXT,
            genre TEXT,
            condition TEXT,
            description TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'available',
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ExchangeRequests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER,
            book_id INTEGER,
            message TEXT,
            status TEXT DEFAULT 'pending',
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            response_date TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        full_name = request.form['full_name']
        location = request.form.get('location', '')
        phone = request.form.get('phone', '')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT user_id FROM Users WHERE username=? OR email=?", (username, email))
            if cursor.fetchone():
                flash('Username or email already exists!', 'danger')
                return redirect(url_for('register'))

            hashed_password = hash_password(password)

            cursor.execute("""
                INSERT INTO Users (username, email, password_hash, full_name, location, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, email, hashed_password, full_name, location, phone))

            conn.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()
            flash(str(e), 'danger')

        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, username, password_hash FROM Users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password(password, user['password_hash']):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid username or password!', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Books WHERE user_id=?", (session['user_id'],))
    user_books = cursor.fetchall()

    incoming_requests = []
    outgoing_requests = []

    conn.close()

    return render_template(
        'dashboard.html',
        user_books=user_books,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests
    )
    @app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')


@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        isbn = request.form.get('isbn', '')
        genre = request.form.get('genre', '')
        condition = request.form['condition']
        description = request.form.get('description', '')

        image_url = ''

        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_url = filepath

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO Books (user_id, title, author, isbn, genre, condition, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session['user_id'], title, author, isbn, genre, condition, description, image_url))

        conn.commit()
        conn.close()

        flash('Book added successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_book.html')


@app.route('/books')
def books():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM Books WHERE status='available' AND user_id != ?
    """, (session['user_id'],))

    books = cursor.fetchall()
    conn.close()

    return render_template('books.html', books=books)


@app.route('/request_book/<int:book_id>', methods=['POST'])
def request_book(book_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    message = request.form.get('message', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO ExchangeRequests (requester_id, book_id, message)
        VALUES (?, ?, ?)
    """, (session['user_id'], book_id, message))

    conn.commit()
    conn.close()

    return jsonify({'success': 'Request sent successfully'})


if __name__ == "__main__":
    init_db()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
