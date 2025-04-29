from flask import Flask, render_template, url_for, flash, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re

from database import db, User, BookType, Book, UniqueBook, Rating, Comment, Purchase

# ---------------------------
# Flask App Initialization
# ---------------------------
app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'  # Using SQLite database
app.config['SECRET_KEY'] = 'your_secret_key'  # Secret key for sessions

# Initialize extensions
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Where to redirect if user tries to access @login_required page without logging in

# ---------------------------
# User Loader for Flask-Login
# ---------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------
# Routes
# ---------------------------

# Home Page (Public)
@app.route('/')
def home():
    return render_template('home.html')

# Login Page (Handles GET and POST)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Read form data
        username = request.form['username']
        password = request.form['password']

        # Find user in database
        user = User.query.filter_by(username=username).first()

        # Check if user exists and password matches
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')

            # Redirect based on user role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'librarian':
                return redirect(url_for('librarian_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

# Registration Page (Handles GET and POST)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Read form data
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Validate Email Format
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_pattern, email):
            flash('Invalid email format. Please enter a valid email address.', 'danger')
            return redirect(url_for('register'))

        # Validate Password Length
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('register'))

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Create new user with role 'user'
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            role='user'
        )

        # Save user to database
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/view_book/<int:book_id>')
@login_required
def view_book(book_id):
    book = Book.query.get_or_404(book_id)

    # Count available copies
    available_copies = [copy for copy in book.copies if copy.status == 'available']
    available_count = len(available_copies)

    return render_template('view_book.html', book=book, available_count=available_count)


@app.route('/issue_book/<int:book_id>')
@login_required
def issue_book(book_id):
    # 1. Check if current user is a 'user'
    if current_user.role != 'user':
        flash('Only regular users can issue books.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)

    # 2. Check if the user has already issued this book
    already_borrowed = UniqueBook.query.filter_by(
        book_id=book.id,
        borrower_id=current_user.id,
        status='borrowed'
    ).first()

    if already_borrowed:
        flash('You have already issued this book. Please return it before issuing again.', 'warning')
        return redirect(url_for('view_book', book_id=book.id))

    # 3. Find an available copy
    available_copy = UniqueBook.query.filter_by(
        book_id=book.id,
        status='available'
    ).first()

    if not available_copy:
        flash('Sorry, no copies available to issue.', 'danger')
        return redirect(url_for('view_book', book_id=book.id))

    # 4. Assign the copy to user
    available_copy.status = 'borrowed'
    available_copy.borrower_id = current_user.id
    available_copy.borrowed_on = datetime.utcnow()
    available_copy.due_date = datetime.utcnow() + timedelta(days=7)  # 7 days borrow period

    db.session.commit()

    flash(f'You have successfully issued "{book.title}". Please return it by {available_copy.due_date.strftime("%Y-%m-%d")}.', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/buy_book/<int:book_id>')
@login_required
def buy_book(book_id):
    # Only 'user' role can buy
    if current_user.role != 'user':
        flash('Only regular users can buy books.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)

    return render_template('buy_book_confirm.html', book=book)

from datetime import datetime

@app.route('/confirm_buy_book/<int:book_id>', methods=['POST'])
@login_required
def confirm_buy_book(book_id):
    if current_user.role != 'user':
        flash('Only regular users can buy books.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)

    # Find an available copy to buy
    available_copy = UniqueBook.query.filter_by(
        book_id=book.id,
        status='available'
    ).first()

    if not available_copy:
        flash('Sorry, this book is currently out of stock to buy.', 'danger')
        return redirect(url_for('view_book', book_id=book.id))

    # Check if user has enough credits
    if current_user.credits < book.price:
        flash(f'Not enough credits to buy "{book.title}". Please add ask librarian to add more credits.', 'danger')
        return redirect(url_for('view_book', book_id=book.id))

    # Create a Purchase record
    new_purchase = Purchase(
        user_id=current_user.id,
        book_title=book.title,
        book_author=book.author,
        price_paid=book.price
    )
    db.session.add(new_purchase)

    # Deduct price from user's credits
    current_user.credits -= book.price

    # Remove the purchased UniqueBook copy
    db.session.delete(available_copy)

    # If no more copies left, delete the Book itself
    remaining_copies = UniqueBook.query.filter_by(book_id=book.id).count()
    if remaining_copies == 0:
        db.session.delete(book)

    db.session.commit()

    flash(f'You have successfully bought "{book.title}" for ${book.price:.2f}.', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/my_books')
@login_required
def my_books():
    if current_user.role != 'user':
        flash('Only users can view borrowed or bought books.', 'danger')
        return redirect(url_for('home'))

    # Borrowed books
    borrowed_copies = UniqueBook.query.filter_by(
        borrower_id=current_user.id,
        status='borrowed'
    ).all()

    # Bought books
    purchases = Purchase.query.filter_by(user_id=current_user.id).all()

    # Calculate total payable amount for borrowed books
    total_amount_due = 0
    today = datetime.utcnow()
    for copy in borrowed_copies:
        days_borrowed = (today - copy.borrowed_on).days
        if days_borrowed < 1:
            days_borrowed = 1
        total_amount_due += days_borrowed * (copy.book.cost_per_day or 0)

    return render_template('my_books.html', borrowed_copies=borrowed_copies, purchases=purchases, total_amount_due=total_amount_due)

@app.route('/return_book/<int:copy_id>', methods=['POST'])
@login_required
def return_book(copy_id):
    if current_user.role != 'user':
        flash('Only users can return books.', 'danger')
        return redirect(url_for('home'))

    copy = UniqueBook.query.get_or_404(copy_id)

    if copy.borrower_id != current_user.id:
        flash('You can only return your own borrowed books.', 'danger')
        return redirect(url_for('my_books'))

    if copy.status != 'borrowed':
        flash('This book is not currently borrowed.', 'danger')
        return redirect(url_for('my_books'))

    today = datetime.utcnow()
    borrowed_days = (today - copy.borrowed_on).days
    if borrowed_days < 1:
        borrowed_days = 1

    # Full charge was for 7 days
    total_charge = 7 * (copy.book.cost_per_day or 0)

    # Actual charge based on real days borrowed
    per_day_charge = (copy.book.cost_per_day or 0)
    actual_charge = borrowed_days * per_day_charge

    # Refund = extra paid
    refund = total_charge - actual_charge

    if refund > 0:
        # Refund extra money
        current_user.credits += refund
        flash(f'Book returned early! ${refund:.2f} refunded back to your credits.', 'success')
    elif refund < 0:
        # Should never happen (can't borrow more than prepaid days normally)
        flash('You have borrowed for extra days. Please contact admin.', 'danger')
        return redirect(url_for('my_books'))
    else:
        flash('Book returned successfully!', 'success')

    # Reset book to available
    copy.status = 'available'
    copy.borrower_id = None
    copy.borrowed_on = None
    copy.due_date = None

    db.session.commit()

    return redirect(url_for('my_books'))

@app.route('/buy_borrowed_book/<int:copy_id>', methods=['POST'])
@login_required
def buy_borrowed_book(copy_id):
    if current_user.role != 'user':
        flash('Only users can buy borrowed books.', 'danger')
        return redirect(url_for('home'))

    copy = UniqueBook.query.get_or_404(copy_id)

    if copy.borrower_id != current_user.id:
        flash('You can only buy books you have borrowed.', 'danger')
        return redirect(url_for('my_books'))

    if copy.status != 'borrowed':
        flash('This book is not currently borrowed.', 'danger')
        return redirect(url_for('my_books'))

    book = copy.book
    book_price = book.price or 0

    # Check if user has enough credits to buy
    if current_user.credits < book_price:
        flash(f'Not enough credits to buy "{book.title}". You need ${book_price:.2f}.', 'danger')
        return redirect(url_for('my_books'))

    # Deduct price
    current_user.credits -= book_price

    # Create a Purchase record
    new_purchase = Purchase(
        user_id=current_user.id,
        book_title=book.title,
        book_author=book.author,
        price_paid=book_price
    )
    db.session.add(new_purchase)

    # Remove the borrowed copy (mark permanently gone)
    db.session.delete(copy)

    # If no more copies left, delete the book
    remaining_copies = UniqueBook.query.filter_by(book_id=book.id).count()
    if remaining_copies == 0:
        db.session.delete(book)

    db.session.commit()

    flash(f'You have successfully bought "{book.title}" for ${book_price:.2f}.', 'success')
    return redirect(url_for('my_books'))


# ---------------------------
# Dashboards for Different Roles
# ---------------------------

# User Dashboard
@app.route('/user_dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    books = Book.query.all()  # Get all books (no filtering)
    return render_template('user_dashboard.html', books=books)

# Librarian Dashboard
@app.route('/librarian_dashboard')
@login_required
def librarian_dashboard():
    if current_user.role != 'librarian' and current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    return render_template('librarian_dashboard.html')

# Admin Dashboard
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    return render_template('admin_dashboard.html')

# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))


@app.route('/test')
def test():
    return "Successfully tested"
# ---------------------------
# Application Runner
# ---------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Check if an admin already exists; if not, create one
        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin',
                email='admin@example.com',
                password=generate_password_hash('admin123', method='pbkdf2:sha256'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: username=admin, password=admin123")

    # Run the application in debug mode
    app.run(debug=True)
