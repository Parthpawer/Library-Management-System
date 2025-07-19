# /library_project/app/librarian/routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, Response, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import extract
import os
import uuid
import csv
from io import StringIO
from datetime import datetime
from app import db
from app.models import Book, UniqueBook, Purchase, BorrowHistory, User, BookType, Rating, Comment

librarian_bp = Blueprint('librarian', __name__, url_prefix='/librarian')

def is_librarian():
    return current_user.is_authenticated and current_user.role == 'librarian'

@librarian_bp.before_request
@login_required
def before_request():
    if not is_librarian():
        flash('Access denied. Librarian access required.', 'danger')
        return redirect(url_for('main.home'))

@librarian_bp.route('/dashboard')
def librarian_dashboard():
    current_month = datetime.utcnow().month
    current_year = datetime.utcnow().year
    monthly_purchases = Purchase.query.filter(extract('month', Purchase.bought_on) == current_month, extract('year', Purchase.bought_on) == current_year).all()
    total_books_sold = len(monthly_purchases)
    total_sales_amount = sum(p.price_paid for p in monthly_purchases)
    return render_template('librarian/librarian_dashboard.html', total_books_sold=total_books_sold, total_sales_amount=total_sales_amount)

@librarian_bp.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        isbn = request.form['isbn']
        if Book.query.filter_by(isbn=isbn).first():
            flash(f'A book with ISBN {isbn} already exists.', 'warning')
            return redirect(url_for('librarian.add_book'))
        
        filename = None
        image = request.files['image']
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

        new_book = Book(
            title=request.form['title'], author=request.form['author'], isbn=isbn,
            publisher=request.form['publisher'], description=request.form['description'],
            price=float(request.form['price']), cost_per_day=float(request.form['cost_per_day']),
            genre_id=int(request.form['genre_id']), book_type_id=int(request.form['book_type_id']),
            image=filename
        )
        db.session.add(new_book)
        db.session.flush() # Use flush to get the new_book.id before commit

        num_copies = int(request.form['num_copies'])
        for _ in range(num_copies):
            db.session.add(UniqueBook(book_id=new_book.id, status='available'))
        
        db.session.commit()
        flash(f'Book "{new_book.title}" added with {num_copies} copies.', 'success')
        return redirect(url_for('librarian.librarian_dashboard'))
    return render_template('librarian/add_book.html')

@librarian_bp.route('/view_available_books')
def view_available_books():
    books = Book.query.all()
    return render_template('librarian/view_available_books.html', books=books)

@librarian_bp.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        book.price = float(request.form['price'])
        book.cost_per_day = float(request.form['cost_per_day'])
        image = request.files.get('image')
        if image and image.filename != '':
            ext = os.path.splitext(image.filename)[1]
            filename = secure_filename(f"{uuid.uuid4().hex}{ext}")
            image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            book.image = filename
        db.session.commit()
        flash('Book details updated.', 'success')
        return redirect(url_for('librarian.view_available_books'))
    return render_template('librarian/edit_book.html', book=book)

@librarian_bp.route('/add_copies/<int:book_id>', methods=['POST'])
def add_copies(book_id):
    book = Book.query.get_or_404(book_id)
    try:
        num_copies = int(request.form['num_copies'])
        if num_copies < 1: raise ValueError
    except:
        flash('Invalid number of copies.', 'danger')
        return redirect(url_for('librarian.view_available_books'))
    for _ in range(num_copies):
        db.session.add(UniqueBook(book_id=book.id, status='available'))
    db.session.commit()
    flash(f'{num_copies} copies added to "{book.title}".', 'success')
    return redirect(url_for('librarian.view_available_books'))

@librarian_bp.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.image:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], book.image)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                flash(f"Failed to delete image file: {e}", 'warning')
    db.session.delete(book) # Cascading delete will handle related items
    db.session.commit()
    flash(f'Book "{book.title}" and all its data were deleted.', 'success')
    return redirect(url_for('librarian.view_available_books'))

@librarian_bp.route('/remove_copies/<int:book_id>', methods=['POST'])
def remove_copies(book_id):
    book = Book.query.get_or_404(book_id)
    try:
        num_copies = int(request.form['num_copies'])
        if num_copies < 1: raise ValueError
    except ValueError:
        flash('Invalid number of copies.', 'danger')
        return redirect(url_for('librarian.view_available_books'))
    
    available_copies = UniqueBook.query.filter_by(book_id=book.id, status='available').limit(num_copies).all()
    if len(available_copies) < num_copies:
        flash(f'Only {len(available_copies)} available copies found to remove.', 'warning')
    else:
        flash(f'{num_copies} copies removed successfully.', 'success')
    
    for copy in available_copies:
        db.session.delete(copy)
    db.session.commit()
    return redirect(url_for('librarian.view_available_books'))

@librarian_bp.route('/view_book/<int:book_id>')
def view_book_librarian(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('librarian/view_book_librarian.html', book=book, copies=book.copies, comments=book.comments)

@librarian_bp.route('/view_history/<int:copy_id>')
def view_copy_history(copy_id):
    copy = UniqueBook.query.get_or_404(copy_id)
    history = BorrowHistory.query.filter_by(copy_id=copy_id).order_by(BorrowHistory.borrowed_on.desc()).all()
    return render_template('librarian/view_history.html', copy=copy, history=history)

@librarian_bp.route('/registered_users')
def registered_users():
    users = User.query.filter_by(role='user').all()
    return render_template('librarian/registered_users.html', users=users)

@librarian_bp.route('/add_credits/<int:user_id>', methods=['POST'])
def add_credits(user_id):
    user = User.query.get_or_404(user_id)
    try:
        amount = float(request.form['amount'])
        if amount <= 0: raise ValueError
    except ValueError:
        flash('Invalid credit amount.', 'danger')
        return redirect(url_for('librarian.registered_users'))
    user.credits += amount
    db.session.commit()
    flash(f'${amount:.2f} added to {user.username}. New balance: ${user.credits:.2f}', 'success')
    return redirect(url_for('librarian.registered_users'))

@librarian_bp.route('/user_purchases/<int:user_id>')
def view_user_purchases(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('librarian/user_purchases.html', user=user, purchases=user.purchases)

@librarian_bp.route('/user_borrows/<int:user_id>')
def view_user_borrow_history(user_id):
    user = User.query.get_or_404(user_id)
    history = BorrowHistory.query.filter_by(user_id=user.id).order_by(BorrowHistory.borrowed_on.desc()).all()
    return render_template('librarian/user_borrows.html', user=user, history=history)

@librarian_bp.route('/download_purchases/<int:user_id>')
def download_purchases(user_id):
    user = User.query.get_or_404(user_id)
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Book Title', 'Author', 'Price Paid', 'Date'])
    for p in user.purchases:
        cw.writerow([p.book_title, p.book_author, f"${p.price_paid:.2f}", p.bought_on.strftime('%Y-%m-%d %H:%M')])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={user.username}_purchases.csv'})

@librarian_bp.route('/download_borrows/<int:user_id>')
def download_borrows(user_id):
    user = User.query.get_or_404(user_id)
    history = BorrowHistory.query.filter_by(user_id=user.id).order_by(BorrowHistory.borrowed_on.desc()).all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Copy ID', 'Book Title', 'Borrowed On', 'Returned On'])
    for h in history:
        returned_date = h.returned_on.strftime('%Y-%m-%d %H:%M') if h.returned_on else 'Not Returned'
        cw.writerow([h.copy.id, h.copy.book.title, h.borrowed_on.strftime('%Y-%m-%d %H:%M'), returned_date])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={user.username}_borrows.csv'})