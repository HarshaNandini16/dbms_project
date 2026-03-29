# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename
import bcrypt
import pyodbc
import os
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
Session(app)

# Allowed file extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Database configuration
DB_CONFIG = {
    'server': 'localhost',
    'database': 'BookExchange',
    'driver': '{ODBC Driver 17 for SQL Server}',
    'trusted_connection': 'yes'
}

def get_db_connection():
    """Create database connection"""
    conn_str = f"DRIVER={DB_CONFIG['driver']};SERVER={DB_CONFIG['server']};DATABASE={DB_CONFIG['database']};Trusted_Connection=yes;"
    return pyodbc.connect(conn_str)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, hashed):
    """Verify password"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
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
            # Check if user exists
            cursor.execute("SELECT user_id FROM Users WHERE username = ? OR email = ?", (username, email))
            if cursor.fetchone():
                flash('Username or email already exists!', 'danger')
                return redirect(url_for('register'))
            
            # Insert new user
            hashed_password = hash_password(password)
            cursor.execute("""
                INSERT INTO Users (username, email, password_hash, full_name, location, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, email, hashed_password, full_name, location, phone))
            conn.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id, username, password_hash FROM Users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password(password, user[2]):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """User dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user's books
    cursor.execute("""
        SELECT book_id, title, author, genre, condition, status, image_url, added_date
        FROM Books 
        WHERE user_id = ? 
        ORDER BY added_date DESC
    """, (session['user_id'],))
    user_books = cursor.fetchall()
    
    # Get incoming requests
    cursor.execute("""
        SELECT r.request_id, r.message, r.status, r.request_date,
               b.title, b.author, u.username as requester_name
        FROM ExchangeRequests r
        JOIN Books b ON r.book_id = b.book_id
        JOIN Users u ON r.requester_id = u.user_id
        WHERE b.user_id = ?
        ORDER BY r.request_date DESC
    """, (session['user_id'],))
    incoming_requests = cursor.fetchall()
    
    # Get outgoing requests
    cursor.execute("""
        SELECT r.request_id, r.message, r.status, r.request_date,
               b.title, b.author, u.username as owner_name
        FROM ExchangeRequests r
        JOIN Books b ON r.book_id = b.book_id
        JOIN Users u ON b.user_id = u.user_id
        WHERE r.requester_id = ?
        ORDER BY r.request_date DESC
    """, (session['user_id'],))
    outgoing_requests = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         user_books=user_books,
                         incoming_requests=incoming_requests,
                         outgoing_requests=outgoing_requests)

@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    """Add new book"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        isbn = request.form.get('isbn', '')
        genre = request.form.get('genre', '')
        condition = request.form['condition']
        description = request.form.get('description', '')
        
        # Handle image upload
        image_url = ''
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f"/static/uploads/{filename}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO Books (user_id, title, author, isbn, genre, condition, description, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session['user_id'], title, author, isbn, genre, condition, description, image_url))
            conn.commit()
            flash('Book added successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f'Error adding book: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('add_book.html')

@app.route('/books')
def books():
    """Browse all available books"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    search = request.args.get('search', '')
    genre = request.args.get('genre', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT b.book_id, b.title, b.author, b.genre, b.condition, b.image_url,
               u.username, u.user_id, u.location
        FROM Books b
        JOIN Users u ON b.user_id = u.user_id
        WHERE b.status = 'available' AND b.user_id != ?
    """
    params = [session['user_id']]
    
    if search:
        query += " AND (b.title LIKE ? OR b.author LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    if genre:
        query += " AND b.genre = ?"
        params.append(genre)
    
    query += " ORDER BY b.added_date DESC"
    
    cursor.execute(query, params)
    books = cursor.fetchall()
    
    # Get genres for filter
    cursor.execute("SELECT DISTINCT genre FROM Books WHERE genre IS NOT NULL AND genre != ''")
    genres = cursor.fetchall()
    
    conn.close()
    
    return render_template('books.html', books=books, genres=genres, search=search, selected_genre=genre)

@app.route('/request_book/<int:book_id>', methods=['POST'])
def request_book(book_id):
    """Request to exchange a book"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    message = request.form.get('message', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if book is available
        cursor.execute("SELECT user_id FROM Books WHERE book_id = ? AND status = 'available'", (book_id,))
        book = cursor.fetchone()
        
        if not book:
            return jsonify({'error': 'Book is not available'}), 400
        
        # Check if already requested
        cursor.execute("""
            SELECT request_id FROM ExchangeRequests 
            WHERE requester_id = ? AND book_id = ? AND status IN ('pending', 'accepted')
        """, (session['user_id'], book_id))
        
        if cursor.fetchone():
            return jsonify({'error': 'You already have a pending request for this book'}), 400
        
        # Create request
        cursor.execute("""
            INSERT INTO ExchangeRequests (requester_id, book_id, message)
            VALUES (?, ?, ?)
        """, (session['user_id'], book_id, message))
        conn.commit()
        
        return jsonify({'success': 'Request sent successfully'}), 200
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/respond_request/<int:request_id>', methods=['POST'])
def respond_request(request_id):
    """Respond to exchange request"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    action = request.form.get('action')  # accept or reject
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user is the book owner
        cursor.execute("""
            SELECT r.book_id FROM ExchangeRequests r
            JOIN Books b ON r.book_id = b.book_id
            WHERE r.request_id = ? AND b.user_id = ?
        """, (request_id, session['user_id']))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Unauthorized'}), 403
        
        if action == 'accept':
            # Update request status
            cursor.execute("""
                UPDATE ExchangeRequests 
                SET status = 'accepted', response_date = GETDATE()
                WHERE request_id = ?
            """, (request_id,))
            
            # Update book status to reserved
            cursor.execute("""
                UPDATE Books 
                SET status = 'reserved'
                WHERE book_id = (SELECT book_id FROM ExchangeRequests WHERE request_id = ?)
            """, (request_id,))
            
            conn.commit()
            return jsonify({'success': 'Request accepted'}), 200
            
        elif action == 'reject':
            cursor.execute("""
                UPDATE ExchangeRequests 
                SET status = 'rejected', response_date = GETDATE()
                WHERE request_id = ?
            """, (request_id,))
            conn.commit()
            return jsonify({'success': 'Request rejected'}), 200
            
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/profile')
def profile():
    """User profile"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user info
    cursor.execute("""
        SELECT username, email, full_name, location, phone, join_date
        FROM Users WHERE user_id = ?
    """, (session['user_id'],))
    user = cursor.fetchone()
    
    # Get user statistics
    cursor.execute("SELECT COUNT(*) FROM Books WHERE user_id = ?", (session['user_id'],))
    books_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM ExchangeRequests r
        JOIN Books b ON r.book_id = b.book_id
        WHERE b.user_id = ? AND r.status = 'accepted'
    """, (session['user_id'],))
    exchanges_count = cursor.fetchone()[0]
    
    # Get user reviews
    cursor.execute("""
        SELECT rating, comment, created_date, u.username
        FROM Reviews r
        JOIN Users u ON r.reviewer_id = u.user_id
        WHERE r.reviewed_user_id = ?
        ORDER BY r.created_date DESC
    """, (session['user_id'],))
    reviews = cursor.fetchall()
    
    conn.close()
    
    return render_template('profile.html', user=user, books_count=books_count, 
                         exchanges_count=exchanges_count, reviews=reviews)

@app.route('/send_message', methods=['POST'])
def send_message():
    """Send message to another user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    receiver_id = request.form.get('receiver_id')
    message = request.form.get('message')
    request_id = request.form.get('request_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO Messages (sender_id, receiver_id, request_id, message)
            VALUES (?, ?, ?, ?)
        """, (session['user_id'], receiver_id, request_id, message))
        conn.commit()
        
        return jsonify({'success': 'Message sent'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/get_messages/<int:user_id>')
def get_messages(user_id):
    """Get messages between users"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.message, m.sent_date, u.username, m.sender_id
        FROM Messages m
        JOIN Users u ON m.sender_id = u.user_id
        WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.sent_date ASC
    """, (session['user_id'], user_id, user_id, session['user_id']))
    
    messages = cursor.fetchall()
    conn.close()
    
    messages_list = [{
        'message': msg[0],
        'sent_date': msg[1].strftime('%Y-%m-%d %H:%M'),
        'username': msg[2],
        'is_owner': msg[3] == session['user_id']
    } for msg in messages]
    
    return jsonify(messages_list)

if __name__ == '__main__':
    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)