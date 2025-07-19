from . import db
from flask_login import UserMixin
from datetime import datetime

class BookType(db.Model):
    __tablename__ = 'booktype'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    books = db.relationship('Book', backref='type', lazy=True)
    
    def __repr__(self):
        return f'<BookType {self.name}>'

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False)
    credits = db.Column(db.Float, default=0)
    
    # "One" side of the relationships. Cascades are defined here.
    ratings = db.relationship('Rating', backref='user', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='user', lazy=True, cascade="all, delete-orphan")
    purchases = db.relationship('Purchase', backref='user', lazy=True, cascade="all, delete-orphan")
    borrow_history = db.relationship('BorrowHistory', backref='user', lazy=True, cascade="all, delete-orphan")
    
    # This relationship should NOT cascade delete. If a user is deleted, the book should become available.
    borrowed_books = db.relationship('UniqueBook', backref='borrower', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Book(db.Model):
    __tablename__ = 'book'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    publisher = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    cost_per_day = db.Column(db.Float, nullable=True)
    price = db.Column(db.Float, nullable=True)
    image = db.Column(db.String(200), nullable=True)
    genre_id = db.Column(db.Integer, nullable=True)
    book_type_id = db.Column(db.Integer, db.ForeignKey('booktype.id'), nullable=False)
    
    # "One" side of the relationships. Cascades are defined here.
    copies = db.relationship('UniqueBook', backref='book', lazy=True, cascade="all, delete-orphan")
    ratings = db.relationship('Rating', backref='book', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='book', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Book {self.title}>'

class Purchase(db.Model):
    __tablename__ = 'purchase'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_title = db.Column(db.String(200), nullable=False)
    book_author = db.Column(db.String(100), nullable=False)
    price_paid = db.Column(db.Float, nullable=False)
    bought_on = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Purchase {self.book_title}>'

class BorrowHistory(db.Model):
    __tablename__ = 'borrow_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    copy_id = db.Column(db.Integer, db.ForeignKey('uniquebook.id'), nullable=False)
    borrowed_on = db.Column(db.DateTime, nullable=False)
    returned_on = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<BorrowHistory user={self.user_id} copy={self.copy_id}>"

class UniqueBook(db.Model):
    __tablename__ = 'uniquebook'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    status = db.Column(db.String(50), default='available')
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    borrowed_on = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    
    # "One" side for BorrowHistory
    history = db.relationship('BorrowHistory', backref='copy', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<UniqueBook Copy {self.id} of {self.book.title}>'

class Rating(db.Model):
    __tablename__ = 'rating'
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    
    def __repr__(self):
        return f'<Rating {self.rating}>'

class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    
    def __repr__(self):
        return f'<Comment by {self.user.username}>'