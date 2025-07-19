# /library_project/app/user/routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Book, Comment, UniqueBook, Purchase, BorrowHistory
from datetime import datetime, timedelta

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.home'))
    books = Book.query.all()
    return render_template('user/user_dashboard.html', books=books)

@user_bp.route('/book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def view_book(book_id):
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        comment_text = request.form.get('comment')
        if not comment_text or not comment_text.strip():
            flash('Comment cannot be empty.', 'warning')
        else:
            new_comment = Comment(content=comment_text.strip(), user_id=current_user.id, book_id=book.id)
            db.session.add(new_comment)
            db.session.commit()
            flash('Comment posted successfully!', 'success')
        return redirect(url_for('user.view_book', book_id=book_id))

    comments = Comment.query.filter_by(book_id=book.id).order_by(Comment.created_at.desc()).all()
    available_copies = [copy for copy in book.copies if copy.status == 'available']
    available_count = len(available_copies)
    return render_template('user/view_book.html', book=book, available_count=available_count, comments=comments)

@user_bp.route('/issue_book/<int:book_id>')
@login_required
def issue_book(book_id):
    if current_user.role != 'user':
        flash('Only regular users can issue books.', 'danger')
        return redirect(url_for('main.home'))
    book = Book.query.get_or_404(book_id)
    already_borrowed = UniqueBook.query.filter_by(book_id=book.id, borrower_id=current_user.id, status='borrowed').first()
    if already_borrowed:
        flash('You have already issued this book.', 'warning')
        return redirect(url_for('user.view_book', book_id=book.id))
    
    available_copy = UniqueBook.query.filter_by(book_id=book.id, status='available').first()
    if not available_copy:
        flash('Sorry, no copies available to issue.', 'danger')
        return redirect(url_for('user.view_book', book_id=book.id))

    available_copy.status = 'borrowed'
    available_copy.borrower_id = current_user.id
    available_copy.borrowed_on = datetime.utcnow()
    available_copy.due_date = datetime.utcnow() + timedelta(days=7)

    history = BorrowHistory(user_id=current_user.id, copy_id=available_copy.id, borrowed_on=datetime.utcnow())
    db.session.add(history)
    db.session.commit()

    flash(f'You have successfully issued "{book.title}". Return by {available_copy.due_date.strftime("%Y-%m-%d")}.', 'success')
    return redirect(url_for('user.user_dashboard'))

@user_bp.route('/buy_book/<int:book_id>')
@login_required
def buy_book(book_id):
    if current_user.role != 'user':
        flash('Only regular users can buy books.', 'danger')
        return redirect(url_for('main.home'))
    book = Book.query.get_or_404(book_id)
    return render_template('user/buy_book_confirm.html', book=book)

@user_bp.route('/confirm_buy_book/<int:book_id>', methods=['POST'])
@login_required
def confirm_buy_book(book_id):
    if current_user.role != 'user':
        flash('Only regular users can buy books.', 'danger')
        return redirect(url_for('main.home'))
    book = Book.query.get_or_404(book_id)
    available_copy = UniqueBook.query.filter_by(book_id=book.id, status='available').first()
    if not available_copy:
        flash('Sorry, this book is out of stock.', 'danger')
        return redirect(url_for('user.view_book', book_id=book.id))
    if current_user.credits < book.price:
        flash(f'Not enough credits to buy "{book.title}".', 'danger')
        return redirect(url_for('user.view_book', book_id=book.id))

    new_purchase = Purchase(user_id=current_user.id, book_title=book.title, book_author=book.author, price_paid=book.price)
    db.session.add(new_purchase)
    current_user.credits -= book.price
    db.session.delete(available_copy)
    db.session.commit()
    flash(f'You have successfully bought "{book.title}" for ${book.price:.2f}.', 'success')
    return redirect(url_for('user.user_dashboard'))

@user_bp.route('/my_books')
@login_required
def my_books():
    if current_user.role != 'user':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.home'))
    borrowed_copies = UniqueBook.query.filter_by(borrower_id=current_user.id, status='borrowed').all()
    purchases = Purchase.query.filter_by(user_id=current_user.id).all()
    return render_template('user/my_books.html', borrowed_copies=borrowed_copies, purchases=purchases)

@user_bp.route('/return_book/<int:copy_id>', methods=['POST'])
@login_required
def return_book(copy_id):
    copy = UniqueBook.query.get_or_404(copy_id)
    if copy.borrower_id != current_user.id:
        flash('You can only return your own borrowed books.', 'danger')
        return redirect(url_for('user.my_books'))

    copy.status = 'available'
    copy.borrower_id = None
    copy.borrowed_on = None
    copy.due_date = None
    
    last_borrow = BorrowHistory.query.filter_by(copy_id=copy.id, user_id=current_user.id).order_by(BorrowHistory.borrowed_on.desc()).first()
    if last_borrow and last_borrow.returned_on is None:
        last_borrow.returned_on = datetime.utcnow()

    db.session.commit()
    flash('Book returned successfully!', 'success')
    return redirect(url_for('user.my_books'))

@user_bp.route('/buy_borrowed_book/<int:copy_id>', methods=['POST'])
@login_required
def buy_borrowed_book(copy_id):
    copy = UniqueBook.query.get_or_404(copy_id)
    if copy.borrower_id != current_user.id:
        flash('You can only buy books you have borrowed.', 'danger')
        return redirect(url_for('user.my_books'))

    book = copy.book
    book_price = book.price or 0
    if current_user.credits < book_price:
        flash(f'Not enough credits to buy "{book.title}". You need ${book_price:.2f}.', 'danger')
        return redirect(url_for('user.my_books'))
    
    current_user.credits -= book_price
    new_purchase = Purchase(user_id=current_user.id, book_title=book.title, book_author=book.author, price_paid=book_price)
    db.session.add(new_purchase)
    db.session.delete(copy)
    db.session.commit()

    flash(f'You have successfully bought "{book.title}" for ${book_price:.2f}.', 'success')
    return redirect(url_for('user.my_books'))