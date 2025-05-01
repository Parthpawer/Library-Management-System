from flask import Flask, render_template, url_for, flash, request, redirect, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import re
import csv
from io import StringIO
import os
import uuid


from database import db, User, BookType, Book, UniqueBook, Rating, Comment, Purchase, BorrowHistory

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


@app.route('/view_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def view_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        comment_text = request.form.get('comment')
        if not comment_text.strip():
            flash('Comment cannot be empty.', 'warning')
        else:
            new_comment = Comment(
                content=comment_text.strip(),
                user_id=current_user.id,
                book_id=book.id
            )
            db.session.add(new_comment)
            db.session.commit()
            flash('Comment posted successfully!', 'success')
        return redirect(url_for('view_book', book_id=book_id))

    # For GET
    comments = Comment.query.filter_by(book_id=book.id).order_by(Comment.created_at.desc()).all()
    available_copies = [copy for copy in book.copies if copy.status == 'available']
    available_count = len(available_copies)

    return render_template('view_book.html', book=book, available_count=available_count, comments=comments)



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

    history = BorrowHistory(
        user_id=current_user.id,
        copy_id=available_copy.id,
        borrowed_on=datetime.utcnow()
    )
    db.session.add(history)
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

    last_borrow = BorrowHistory.query.filter_by(copy_id=copy.id, user_id=current_user.id).order_by(
    BorrowHistory.borrowed_on.desc()).first()

    if last_borrow and last_borrow.returned_on is None:
        last_borrow.returned_on = datetime.utcnow()

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

@app.route('/librarian/view_history/<int:copy_id>')
@login_required
def view_copy_history(copy_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    copy = UniqueBook.query.get_or_404(copy_id)
    history = BorrowHistory.query.filter_by(copy_id=copy_id).order_by(BorrowHistory.borrowed_on.desc()).all()

    return render_template('view_history.html', copy=copy, history=history)

@app.route('/registered_users')
@login_required
def registered_users():
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    users = User.query.filter_by(role='user').all()
    return render_template('registered_users.html', users=users)

@app.route('/add_credits/<int:user_id>', methods=['POST'])
@login_required
def add_credits(user_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)
    try:
        amount = float(request.form['amount'])
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash('Invalid credit amount.', 'danger')
        return redirect(url_for('registered_users'))

    user.credits += amount
    db.session.commit()

    flash(f'${amount:.2f} added to {user.username}.', 'success')
    return redirect(url_for('registered_users'))

@app.route('/user_purchases/<int:user_id>')
@login_required
def view_user_purchases(user_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)
    purchases = Purchase.query.filter_by(user_id=user.id).all()

    return render_template('user_purchases.html', user=user, purchases=purchases)


@app.route('/user_borrows/<int:user_id>')
@login_required
def view_user_borrow_history(user_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)
    history = BorrowHistory.query.filter_by(user_id=user.id).order_by(BorrowHistory.borrowed_on.desc()).all()

    return render_template('user_borrows.html', user=user, history=history)

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
    if current_user.role != 'librarian':
        flash('Access denied: Only librarians can view this dashboard.', 'danger')
        return redirect(url_for('home'))

    # Monthly sales summary (for current month)
    current_month = datetime.utcnow().month
    current_year = datetime.utcnow().year

    monthly_purchases = Purchase.query.filter(
        extract('month', Purchase.bought_on) == current_month,
        extract('year', Purchase.bought_on) == current_year
    ).all()

    total_books_sold = len(monthly_purchases)
    total_sales_amount = sum(p.price_paid for p in monthly_purchases)

    return render_template(
        'librarian_dashboard.html',
        total_books_sold=total_books_sold,
        total_sales_amount=total_sales_amount
    )

@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    if current_user.role != 'librarian':
        flash('Access denied. Only librarians can add books.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        isbn = request.form['isbn']
        publisher = request.form['publisher']
        description = request.form['description']
        price = float(request.form['price'])
        cost_per_day = float(request.form['cost_per_day'])
        genre_id = int(request.form['genre_id'])
        book_type_id = int(request.form['book_type_id'])
        num_copies = int(request.form['num_copies'])
        image = request.files['image']

        # Check if ISBN already exists
        existing_book = Book.query.filter_by(isbn=isbn).first()
        if existing_book:
            flash(f'A book with ISBN {isbn} already exists: "{existing_book.title}".', 'warning')
            return redirect(url_for('add_book'))

        # Save image to static/book_images/
        filename = None
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            os.makedirs('static/uploads', exist_ok=True)
            image_path = os.path.join('static/uploads', filename)
            image.save(image_path)

        # Create Book record
        new_book = Book(
            title=title,
            author=author,
            isbn=isbn,
            publisher=publisher,
            description=description,
            price=price,
            cost_per_day=cost_per_day,
            genre_id=genre_id,
            book_type_id=book_type_id,
            image=filename
        )
        db.session.add(new_book)
        db.session.commit()

        # Add physical copies
        for _ in range(num_copies):
            copy = UniqueBook(book_id=new_book.id, status='available')
            db.session.add(copy)

        db.session.commit()

        flash(f'Book "{title}" added successfully with {num_copies} copies.', 'success')
        return redirect(url_for('librarian_dashboard'))

    return render_template('add_book.html')

@app.route('/view_available_books')
@login_required
def view_available_books():
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    books = Book.query.all()
    return render_template('view_available_books.html', books=books)

@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        # Get updated values
        book.price = float(request.form['price'])
        book.cost_per_day = float(request.form['cost_per_day'])

        # Handle new image upload if provided
        image = request.files.get('image')
        if image and image.filename != '':
            ext = os.path.splitext(image.filename)[1]  # e.g. .jpg, .png
            filename = secure_filename(f"{uuid.uuid4().hex}{ext}")

            upload_folder = 'static/book_images'
            os.makedirs(upload_folder, exist_ok=True)
            image_path = os.path.join(upload_folder, filename)
            image.save(image_path)
            book.image = filename  # Update image filename

        db.session.commit()
        flash('Book details updated successfully.', 'success')
        return redirect(url_for('view_available_books'))

    return render_template('edit_book.html', book=book)

@app.route('/add_copies/<int:book_id>', methods=['POST'])
@login_required
def add_copies(book_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)
    try:
        num_copies = int(request.form['num_copies'])
        if num_copies < 1:
            raise ValueError
    except:
        flash('Invalid number of copies.', 'danger')
        return redirect(url_for('view_available_books'))

    for _ in range(num_copies):
        new_copy = UniqueBook(book_id=book.id, status='available')
        db.session.add(new_copy)

    db.session.commit()

    flash(f'{num_copies} copies added to "{book.title}".', 'success')
    return redirect(url_for('view_available_books'))

import os

@app.route('/delete_book/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)

    # Delete image file if exists
    if book.image:
        image_path = os.path.join('static/book_images', book.image)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                flash(f"Failed to delete image: {e}", 'warning')

    # Delete related data
    UniqueBook.query.filter_by(book_id=book.id).delete()
    Rating.query.filter_by(book_id=book.id).delete()
    Comment.query.filter_by(book_id=book.id).delete()
    # Optionally: Purchase.query.filter_by(book_title=book.title).delete()

    db.session.delete(book)
    db.session.commit()

    flash(f'Book "{book.title}" and all its data were deleted.', 'success')
    return redirect(url_for('view_available_books'))


@app.route('/remove_copies/<int:book_id>', methods=['POST'])
@login_required
def remove_copies(book_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)

    try:
        num_copies = int(request.form['num_copies'])
        if num_copies < 1:
            raise ValueError
    except ValueError:
        flash('Invalid number of copies to remove.', 'danger')
        return redirect(url_for('view_available_books'))

    # Get available copies
    available_copies = UniqueBook.query.filter_by(book_id=book.id, status='available').limit(num_copies).all()

    if len(available_copies) < num_copies:
        flash(f'Only {len(available_copies)} available copies could be removed.', 'warning')
    else:
        flash(f'{num_copies} copies removed successfully.', 'success')

    for copy in available_copies:
        db.session.delete(copy)

    db.session.commit()
    return redirect(url_for('view_available_books'))

@app.route('/librarian/view_book/<int:book_id>')
@login_required
def view_book_librarian(book_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)
    copies = UniqueBook.query.filter_by(book_id=book.id).all()
    comments = Comment.query.filter_by(book_id=book.id).order_by(Comment.created_at.desc()).all()

    return render_template('view_book_librarian.html', book=book, copies=copies, comments=comments)

@app.route('/admin/view_book/<int:book_id>')
@login_required
def view_book_admin(book_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    book = Book.query.get_or_404(book_id)
    copies = UniqueBook.query.filter_by(book_id=book.id).all()
    comments = Comment.query.filter_by(book_id=book.id).order_by(Comment.created_at.desc()).all()

    return render_template('view_book_admin.html', book=book, copies=copies, comments=comments)


@app.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment_admin(comment_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    comment = Comment.query.get_or_404(comment_id)
    book_id = comment.book_id  # To redirect back to the same book view

    db.session.delete(comment)
    db.session.commit()

    flash('Comment deleted successfully.', 'success')
    return redirect(url_for('view_book_admin', book_id=book_id))

@app.route('/admin/delete_account/<int:user_id>', methods=['POST'])
@login_required
def delete_account(user_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)

    if user.role == 'admin':
        flash("You can't delete an admin account.", 'danger')
        return redirect(url_for('admin_view_users'))

    # Clean related data
    Comment.query.filter_by(user_id=user.id).delete()
    Rating.query.filter_by(user_id=user.id).delete()
    Purchase.query.filter_by(user_id=user.id).delete()
    BorrowHistory.query.filter_by(user_id=user.id).delete()

    borrowed_copies = UniqueBook.query.filter_by(borrower_id=user.id).all()
    for copy in borrowed_copies:
        copy.status = 'available'
        copy.borrower_id = None
        copy.borrowed_on = None
        copy.due_date = None

    db.session.delete(user)
    db.session.commit()

    flash(f"{user.role.title()} '{user.username}' deleted successfully.", 'success')
    return redirect(url_for('admin_view_users'))


@app.route('/download_purchases/<int:user_id>')
@login_required
def download_purchases(user_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)
    purchases = Purchase.query.filter_by(user_id=user.id).all()

    # Create in-memory CSV
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Book Title', 'Author', 'Price Paid', 'Date'])

    for p in purchases:
        cw.writerow([p.book_title, p.book_author, f"${p.price_paid:.2f}", p.bought_on.strftime('%Y-%m-%d %H:%M')])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={user.username}_purchases.csv'
        }
    )

@app.route('/download_borrows/<int:user_id>')
@login_required
def download_borrows(user_id):
    if current_user.role != 'librarian':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)
    history = BorrowHistory.query.filter_by(user_id=user.id).order_by(BorrowHistory.borrowed_on.desc()).all()

    # Create in-memory CSV
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Copy ID', 'Book Title', 'Borrowed On', 'Returned On'])

    for h in history:
        cw.writerow([
            h.copy.id,
            h.copy.book.title,
            h.borrowed_on.strftime('%Y-%m-%d %H:%M'),
            h.returned_on.strftime('%Y-%m-%d %H:%M') if h.returned_on else 'Not Returned'
        ])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={user.username}_borrows.csv'
        }
    )

# Admin Dashboard
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    return render_template('admin_dashboard.html')

@app.route('/admin/view_users')
@login_required
def admin_view_users():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    users = User.query.filter_by(role='user').all()
    librarians = User.query.filter_by(role='librarian').all()
    return render_template('admin_view_users.html', users=users, librarians=librarians)



@app.route('/admin/view_librarians')
@login_required
def admin_view_librarians():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    librarians = User.query.filter_by(role='librarian').all()
    return render_template('admin_view_librarians.html', librarians=librarians)

# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home'))

@app.route('/admin/view_books')
@login_required
def admin_view_books():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    books = Book.query.all()
    return render_template('admin_view_books.html', books=books)


@app.route('/admin/add_librarian', methods=['GET', 'POST'])
@login_required
def add_librarian():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('add_librarian'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        librarian = User(
            username=username,
            email=email,
            password=hashed_password,
            role='librarian',
            credits=0  # optional field for consistency
        )
        db.session.add(librarian)
        db.session.commit()

        flash('Librarian added successfully.', 'success')
        return redirect(url_for('admin_view_users'))

    return render_template('add_librarian.html')

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

        if not User.query.filter_by(role='librarian').first():
            librarian = User(
                username='librarian1',
                email='librarian@example.com',
                password=generate_password_hash('librarian123', method='pbkdf2:sha256'),
                role='librarian',
                credits=0  # Optional, won't be used by librarian
            )
            db.session.add(librarian)
            db.session.commit()
            print("✅ Dummy librarian created: librarian@example.com / librarian123")
        else:
            print("ℹ️ Librarian already exists.")
    # Run the application in debug mode
    app.run(debug=True)
