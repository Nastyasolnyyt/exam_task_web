import os

class Config:
    # Секретный ключ для сессий (нужен для авторизации)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-for-exam'
    
    # Путь к БД. 
    # В экзамене упоминается MySQL. У тебя стоит локальный сервер MySQL/MariaDB?
    # Если нет, для начала можем использовать SQLite (файл в папке),
    # а перед сдачей переключить на MySQL.
    SQLALCHEMY_DATABASE_URI = 'sqlite:///library.db' 
    SQLALCHEMY_TRACK_MODIFICATIONS = False