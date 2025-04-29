from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Initialize SQLAlchemy ORM
db = SQLAlchemy()

# ---------------------
# Book Type Table
# ---------------------
class BookType(db.Model):
    __tablename__ = 'booktype'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # Example: Learning, Movie, Magazine

    books = db.relationship('Book', backref='type', lazy=True)

    def __repr__(self):
        return f'<BookType {self.name}>'

# ---------------------
# User Table
# ---------------------
class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'user', 'librarian', 'admin'
    credits = db.Column(db.Float, default=0)  # New column for user balance

    # Relationships
    ratings = db.relationship('Rating', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)
    borrowed_books = db.relationship('UniqueBook', backref='borrower', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'



# ---------------------
# Book Master Table
# ---------------------
class Book(db.Model):
    __tablename__ = 'book'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    publisher = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # New fields based on your request
    cost_per_day = db.Column(db.Float, nullable=True)  # How much it costs to borrow per day
    price = db.Column(db.Float, nullable=True)         # Full buying price of the book

    image = db.Column(db.String(200), nullable=True)
    genre_id = db.Column(db.Integer, nullable=True)

    # Foreign key to BookType
    book_type_id = db.Column(db.Integer, db.ForeignKey('booktype.id'), nullable=False)

    copies = db.relationship('UniqueBook', backref='book', lazy=True)
    ratings = db.relationship('Rating', backref='book', lazy=True)
    comments = db.relationship('Comment', backref='book', lazy=True)

    def __repr__(self):
        return f'<Book {self.title}>'

class Purchase(db.Model):
    __tablename__ = 'purchase'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Who bought
    book_title = db.Column(db.String(200), nullable=False)  # Title of bought book
    book_author = db.Column(db.String(100), nullable=False)
    price_paid = db.Column(db.Float, nullable=False)
    bought_on = db.Column(db.DateTime, default=datetime.utcnow)  # When bought

    def __repr__(self):
        return f'<Purchase {self.book_title} by {self.user.username}>'

# ---------------------
# Physical Copies Table
# ---------------------
class UniqueBook(db.Model):
    __tablename__ = 'uniquebook'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    status = db.Column(db.String(50), default='available')  # available/borrowed
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    borrowed_on = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<UniqueBook Copy {self.id} of {self.book.title}>'

# ---------------------
# Ratings Table
# ---------------------
class Rating(db.Model):
    __tablename__ = 'rating'

    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)

    def __repr__(self):
        return f'<Rating {self.rating} for {self.book.title} by {self.user.username}>'

# ---------------------
# Comments Table
# ---------------------
class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)

    def __repr__(self):
        return f'<Comment by {self.user.username} on {self.book.title}>'

# ---------------------
# Database Initialization Helper
# ---------------------
def init_db(app):
    db.init_app(app)
