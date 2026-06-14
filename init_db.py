from app import app
from models import db, Role, User, Genre  # <-- Добавили импорт Genre

with app.app_context():
    # Создаем все таблицы в файле library.db
    db.create_all()
    print("Таблицы успешно созданы в БД!")

    # 1. Проверяем и добавляем роли
    if not Role.query.filter_by(name='Администратор').first():
        admin_role = Role(name='Администратор', description='Полный доступ к системе, создание и удаление книг')
        moderator_role = Role(name='Модератор', description='Редактирование книг и модерация рецензий')
        user_role = Role(name='Пользователь', description='Оставление рецензий')
        
        db.session.add_all([admin_role, moderator_role, user_role])
        db.session.commit()
        print("Базовые роли успешно добавлены!")

        # Тестовый админ
        admin_user = User(
            login='admin',
            last_name='Солнцева',
            first_name='Студент',
            role=admin_role
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print("Тестовый пользователь 'admin' создан!")

    # 2. ДОБАВЛЕННЫЙ БЛОК: Проверяем и добавляем жанры по ТЗ
    if not Genre.query.first():
        genres_list = [
            Genre(name='Фантастика'),
            Genre(name='Ужасы'),
            Genre(name='Детектив'),
            Genre(name='Роман'),
            Genre(name='Триллер'),
            Genre(name='Фэнтези')
        ]
        db.session.add_all(genres_list)
        db.session.commit()
        print("Базовые жанры успешно добавлены в базу данных!")