from database import db, Book, UniqueBook, BookType
from flask import Flask
import random

# Create Flask app context
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db.init_app(app)

# Dummy book data
dummy_books = [
    {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "isbn": "9780743273565",
        "publisher": "Scribner",
        "description": "A novel set in the Jazz Age on Long Island.",
        "price": 15.99,
        "cost_per_day": 0.5,
        "genre_id": 1,
        "book_type_id": 1,
        "image": None
    },
    {
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "isbn": "9780061120084",
        "publisher": "J.B. Lippincott & Co.",
        "description": "A novel about racial injustice in the Deep South.",
        "price": 12.99,
        "cost_per_day": 0.4,
        "genre_id": 1,
        "book_type_id": 1,
        "image": "mockingbird.jpg"
    },
    {
        "title": "1984",
        "author": "George Orwell",
        "isbn": "9780451524935",
        "publisher": "Secker & Warburg",
        "description": "A dystopian novel about totalitarian regime.",
        "price": 10.99,
        "cost_per_day": 0.3,
        "genre_id": 2,
        "book_type_id": 1,
        "image": "1984.jpg"
    },
    {
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "isbn": "9780547928227",
        "publisher": "Allen & Unwin",
        "description": "A fantasy novel and prelude to The Lord of the Rings.",
        "price": 18.50,
        "cost_per_day": 0.6,
        "genre_id": 3,
        "book_type_id": 1,
        "image": "hobbit.jpg"
    },
    {
        "title": "Harry Potter and the Sorcerer's Stone",
        "author": "J.K. Rowling",
        "isbn": "9780590353427",
        "publisher": "Bloomsbury",
        "description": "The first book in the Harry Potter series.",
        "price": 22.00,
        "cost_per_day": 0.8,
        "genre_id": 4,
        "book_type_id": 1,
        "image": "harry_potter.jpg"
    }
]

# Insert dummy data
with app.app_context():
    db.create_all()  # Ensure all tables exist

    for book_data in dummy_books:
        existing_book = Book.query.filter_by(isbn=book_data['isbn']).first()
        if not existing_book:
            new_book = Book(
                title=book_data['title'],
                author=book_data['author'],
                isbn=book_data['isbn'],
                publisher=book_data['publisher'],
                description=book_data['description'],
                price=book_data['price'],
                cost_per_day=book_data['cost_per_day'],
                genre_id=book_data['genre_id'],
                book_type_id=book_data['book_type_id'],
                image=book_data['image']
            )
            db.session.add(new_book)
            db.session.commit()

            # Add 2-4 random available copies
            for _ in range(random.randint(2, 4)):
                copy = UniqueBook(
                    book_id=new_book.id,
                    status='available'
                )
                db.session.add(copy)
            db.session.commit()

    print("Dummy books added successfully!")
