# /library_project/app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
import os
import random
import json

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

def seed_data():
    """Seeds the database with initial data from environment variables and JSON."""
    # --- Seed Users ---
    if not models.User.query.filter_by(role='admin').first():
        admin_pass = os.environ.get('ADMIN_PASSWORD')
        admin = models.User(
            username=os.environ.get('ADMIN_USERNAME'),
            email=os.environ.get('ADMIN_EMAIL'),
            password=generate_password_hash(admin_pass, method='pbkdf2:sha256'),
            role='admin'
        )
        db.session.add(admin)
        print("Default admin created.")

    if not models.User.query.filter_by(role='librarian').first():
        librarian_pass = os.environ.get('LIBRARIAN_PASSWORD')
        librarian = models.User(
            username=os.environ.get('LIBRARIAN_USERNAME'),
            email=os.environ.get('LIBRARIAN_EMAIL'),
            password=generate_password_hash(librarian_pass, method='pbkdf2:sha256'),
            role='librarian'
        )
        db.session.add(librarian)
        print("Default librarian created.")

    # --- Seed Book Types ---
    if not models.BookType.query.first():
        types_str = os.environ.get('INITIAL_BOOK_TYPES', '')
        types = [t.strip() for t in types_str.split(',') if t.strip()]
        for t in types:
            db.session.add(models.BookType(name=t))
        print("Default book types seeded.")
    
    db.session.commit()

    # --- Seed Books from JSON ---
    try:
        with open('seed_books.json', 'r') as f:
            dummy_books = json.load(f)
        
        for book_data in dummy_books:
            if not models.Book.query.filter_by(isbn=book_data['isbn']).first():
                new_book = models.Book(**book_data)
                db.session.add(new_book)
                db.session.flush()
                
                for _ in range(random.randint(2, 4)):
                    copy = models.UniqueBook(book_id=new_book.id, status='available')
                    db.session.add(copy)
                print(f"Added book: {new_book.title}")
        
        db.session.commit()
        print("Database seeded successfully! ✅")
    except FileNotFoundError:
        print("seed_books.json not found. Skipping book seeding.")
    except json.JSONDecodeError:
        print("Error decoding seed_books.json. Skipping book seeding.")

def create_app():
    """Construct the core application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object('config.DevelopmentConfig')

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'])
    except OSError:
        pass

    db.init_app(app)
    login_manager.init_app(app)

    from . import models

    with app.app_context():
        # Using inspect to check for tables is more robust than checking for file path
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if not inspector.has_table("user"):
            print("Tables not found, creating and seeding...")
            db.create_all()
            seed_data()
        
        @login_manager.user_loader
        def load_user(user_id):
            return models.User.query.get(int(user_id))

        # Register Blueprints
        from .main.routes import main_bp
        app.register_blueprint(main_bp)
        from .auth.routes import auth_bp
        app.register_blueprint(auth_bp)
        from .user.routes import user_bp
        app.register_blueprint(user_bp)
        from .librarian.routes import librarian_bp
        app.register_blueprint(librarian_bp)
        from .admin.routes import admin_bp
        app.register_blueprint(admin_bp)

        return app