from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    role = db.relationship('Role', backref=db.backref('users', lazy=True))
    # Метод для установки пароля (хешируем его сразу)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Метод для проверки пароля
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
# Соединительная таблица для связи Многие-ко-Многим (Книги <-> Жанры)
book_genre = db.Table('book_genre',
    db.Column('book_id', db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id', ondelete='CASCADE'), primary_key=True)
)

class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # Обязательное, уникальное

class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)        # Название
    description = db.Column(db.Text, nullable=False)          # Краткое описание (Markdown)
    year = db.Column(db.Integer, nullable=False)              # Год (в SQLite используем Integer)
    publisher = db.Column(db.String(255), nullable=False)     # Издательство
    author = db.Column(db.String(255), nullable=False)        # Автор
    pages = db.Column(db.Integer, nullable=False)             # Объём в страницах

    # Связь с жанрами через соединительную таблицу book_genre
    genres = db.relationship('Genre', secondary=book_genre, backref=db.backref('books', lazy='dynamic'))

    @property
    def average_rating(self):
        reviews = Review.query.filter_by(book_id=self.id).all()
        if not reviews:
            return 0.0
        return round(sum(r.rating for r in reviews) / len(reviews), 2)

    @property
    def reviews_count(self):
        return Review.query.filter_by(book_id=self.id).count()
    
class Cover(db.Model):
    __tablename__ = 'covers'
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)  # Название файла на диске
    mime_type = db.Column(db.String(100), nullable=False)  # Например, image/jpeg
    md5_hash = db.Column(db.String(32), nullable=False)    # Хэш для проверки дубликатов
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    book = db.relationship('Book', backref=db.backref('cover', cascade='all, delete-orphan'))

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)          # Оценка от 0 до 5
    text = db.Column(db.Text, nullable=False)              # Текст рецензии (Markdown)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Авто-дата

    # Связи, чтобы легко доставать автора рецензии и саму книгу
    user = db.relationship('User', backref=db.backref('reviews', lazy=True))
    book = db.relationship('Book', backref=db.backref('reviews', cascade="all, delete-orphan", lazy=True))