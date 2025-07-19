# /library_project/app/admin/routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, Book, Comment

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def is_admin():
    return current_user.is_authenticated and current_user.role == 'admin'

@admin_bp.before_request
@login_required
def before_request():
    if not is_admin():
        flash('Access denied. Administrator access required.', 'danger')
        return redirect(url_for('main.home'))

@admin_bp.route('/dashboard')
def admin_dashboard():
    return render_template('admin/admin_dashboard.html')

@admin_bp.route('/view_users')
def admin_view_users():
    users = User.query.filter_by(role='user').all()
    librarians = User.query.filter_by(role='librarian').all()
    return render_template('admin/admin_view_users.html', users=users, librarians=librarians)

@admin_bp.route('/view_books')
def admin_view_books():
    books = Book.query.all()
    return render_template('admin/admin_view_books.html', books=books)

@admin_bp.route('/add_librarian', methods=['GET', 'POST'])
def add_librarian():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('admin.add_librarian'))
        if User.query.filter_by(username=username).first():
            flash('Username already in use.', 'danger')
            return redirect(url_for('admin.add_librarian'))

        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        librarian = User(username=username, email=email, password=hashed_password, role='librarian')
        db.session.add(librarian)
        db.session.commit()

        flash('Librarian added successfully.', 'success')
        return redirect(url_for('admin.admin_view_users'))
    return render_template('admin/add_librarian.html')

@admin_bp.route('/view_book/<int:book_id>')
def view_book_admin(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('admin/view_book_admin.html', book=book, copies=book.copies, comments=book.comments)

@admin_bp.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment_admin(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    book_id = comment.book_id
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted successfully.', 'success')
    return redirect(url_for('admin.view_book_admin', book_id=book_id))

@admin_bp.route('/delete_account/<int:user_id>', methods=['POST'])
def delete_account(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.role == 'admin':
        flash("You cannot delete an admin account.", 'danger')
        return redirect(url_for('admin.admin_view_users'))

    # Set borrowed books to available
    for copy in user_to_delete.borrowed_books:
        copy.status = 'available'
        copy.borrower_id = None
        copy.borrowed_on = None
        copy.due_date = None
    
    # Cascade delete will handle comments, ratings, purchases, etc.
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f"{user_to_delete.role.title()} '{user_to_delete.username}' deleted successfully.", 'success')
    return redirect(url_for('admin.admin_view_users'))