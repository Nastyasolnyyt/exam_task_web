import os
import hashlib
import uuid
import bleach
import markdown
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# Импорты наших собственных модулей
from config import Config
from models import db, User, Book, Genre, Cover
from forms import LoginForm, BookForm, BookSearchForm  # <-- Добавили BookSearchForm
from forms import ReviewForm 
from models import Review

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Инициализируем базу данных
    db.init_app(app)

    # Настраиваем менеджер авторизации
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.login_message = 'Для выполнения данного действия необходимо пройти процедуру аутентификации'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ==========================================
    # МАРШРУТЫ (ROUTES)
    # ==========================================

    @app.route('/')
    def index():
        page = request.args.get('page', 1, type=int)
        
        # Инициализируем форму поиска (передаем request.args вместо request.form, так как поиск идет через GET)
        search_form = BookSearchForm(request.args)
        
        # Динамически заполняем варианты для Жанров и Годов из БД
        search_form.genres.choices = [(g.id, g.name) for g in Genre.query.order_by(Genre.name).all()]
        
        # Извлекаем все уникальные года из таблицы книг для выпадающего списка
        distinct_years = db.session.query(Book.year).distinct().order_by(Book.year.desc()).all()
        search_form.years.choices = [(y[0], str(y[0])) for y in distinct_years if y[0]]

        # Формируем базовый запрос
        query = Book.query

        # Фильтрация по Названию (частичное совпадение без учета регистра через ilike)
        if search_form.title.data:
            query = query.filter(Book.title.ilike(f"%{search_form.title.data}%"))

        # Фильтрация по Автору (частичное совпадение)
        if search_form.author.data:
            query = query.filter(Book.author.ilike(f"%{search_form.author.data}%"))

        # Фильтрация по Жанрам (многие-ко-многим)
        if search_form.genres.data:
            query = query.join(Book.genres).filter(Genre.id.in_(search_form.genres.data))

        # Фильтрация по Годам
        if search_form.years.data:
            query = query.filter(Book.year.in_(search_form.years.data))

        # Фильтрация по Объёму страниц (От / До)
        if search_form.pages_from.data is not None:
            query = query.filter(Book.pages >= search_form.pages_from.data)
        if search_form.pages_to.data is not None:
            query = query.filter(Book.pages <= search_form.pages_to.data)

        # Сортировка по умолчанию (сначала новые по ID/дате)
        query = query.order_by(Book.id.desc())

        # Пагинация (по 10 книг на страницу)
        pagination = query.paginate(page=page, per_page=10)
        books = pagination.items

        return render_template('index.html', books=books, pagination=pagination, form=search_form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
            
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(login=form.login.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                flash('Вы успешно вошли в систему.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            
            flash('Невозможно аутентифицироваться с указанными логином и паролем.', 'danger')
            
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы успешно вышли из системы.', 'success')
        return redirect(url_for('index'))

    @app.route('/book/add', methods=['GET', 'POST'])
    @login_required
    def add_book():
        # Ограничение доступа по ТЗ: добавлять может только Администратор
        if current_user.role.name != 'Администратор':
            flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
            return redirect(url_for('index'))

        form = BookForm()
        form.genres.choices = [(g.id, g.name) for g in Genre.query.all()]

        if form.validate_on_submit():
            try:
                # 1. Санитизируем описание
                clean_description = bleach.clean(form.description.data)

                # 2. Создаем запись книги
                new_book = Book(
                    title=form.title.data,
                    description=clean_description,
                    year=form.year.data,
                    publisher=form.publisher.data,
                    author=form.author.data,
                    pages=form.pages.data
                )
                
                # Привязываем выбранные жанры из мультиселекта
                if form.genres.data:
                    selected_genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
                    new_book.genres = selected_genres

                db.session.add(new_book)
                db.session.commit()  # Генерируем ID для привязки обложки

                # 3. Обработка обложки и подсчет MD5-хэша
                file = form.cover.data
                file_content = file.read()
                md5 = hashlib.md5(file_content).hexdigest()

                # Возвращаем указатель файла в начало, чтобы прочитать и сохранить целиком!
                file.seek(0)

                existing_cover = Cover.query.filter_by(md5_hash=md5).first()
                if not existing_cover:
                    # Создаем уникальное имя на диске
                    filename = f"{uuid.uuid4().hex}.{file.filename.split('.')[-1]}"
                    save_path = os.path.join(app.root_path, 'static', 'covers', filename)
                    file.save(save_path)
                    
                    new_cover = Cover(file_name=filename, mime_type=file.mimetype, md5_hash=md5, book_id=new_book.id)
                else:
                    # Если картинка дублируется, ссылаемся на старый файл на диске
                    new_cover = Cover(file_name=existing_cover.file_name, mime_type=existing_cover.mime_type, md5_hash=md5, book_id=new_book.id)
                
                db.session.add(new_cover)
                db.session.commit()
                
                flash('Книга успешно добавлена!', 'success')
                return redirect(url_for('index'))

            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при добавлении книги: {e}")
                flash('При сохранении данных возникла ошибка. Проверьте корректность введённых данных.', 'danger')
                
        return render_template('add_book.html', form=form)
    
    @app.route('/book/<int:book_id>')
    def book_detail(book_id):
        book = Book.query.get_or_404(book_id)
        
        # Конвертируем описание книги из Markdown в HTML по ТЗ
        book_description_html = markdown.markdown(book.description)
        
        # Получаем все рецензии на эту книгу
        reviews = Review.query.filter_by(book_id=book.id).order_by(Review.created_at.desc()).all()
        
        # Конвертируем тексты рецензий в HTML
        for r in reviews:
            r.text_html = markdown.markdown(r.text)

        # Проверяем, писал ли текущий пользователь уже рецензию
        already_reviewed = False
        if current_user.is_authenticated:
            already_reviewed = Review.query.filter_by(book_id=book.id, user_id=current_user.id).first() is not None

        return render_template('book_detail.html', 
                               book=book, 
                               description_html=book_description_html, 
                               reviews=reviews,
                               already_reviewed=already_reviewed)

    @app.route('/book/<int:book_id>/review', methods=['GET', 'POST'])
    @login_required
    def add_review(book_id):
        book = Book.query.get_or_404(book_id)
        
        # Проверка: если отзыв уже есть, не даем писать второй
        existing = Review.query.filter_by(book_id=book.id, user_id=current_user.id).first()
        if existing:
            flash('Вы уже оставили рецензию на эту книгу.', 'warning')
            return redirect(url_for('book_detail', book_id=book.id))
            
        form = ReviewForm()
        if form.validate_on_submit():
            try:
                clean_text = bleach.clean(form.text.data)
                review = Review(
                    book_id=book.id,
                    user_id=current_user.id,
                    rating=form.rating.data,
                    text=clean_text
                )
                db.session.add(review)
                db.session.commit()
                flash('Рецензия успешно сохранена!', 'success')
                return redirect(url_for('book_detail', book_id=book.id))
            except Exception as e:
                db.session.rollback()
                flash('При сохранении рецензии возникла ошибка.', 'danger')
                
        return render_template('add_review.html', form=form, book=book)
    
    @app.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_book(book_id):
        # Редактировать могут Администратор и Модератор
        if current_user.role.name not in ['Администратор', 'Модератор']:
            flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
            return redirect(url_for('index'))

        book = Book.query.get_or_404(book_id)
        form = BookForm(obj=book)
        form.genres.choices = [(g.id, g.name) for g in Genre.query.all()]

        # По ТЗ обложка при редактировании не меняется, делаем поле необязательным
        del form.cover

        if request.method == 'GET':
            # Предзаполняем жанры, которые уже есть у книги
            form.genres.data = [g.id for g in book.genres]

        if form.validate_on_submit():
            try:
                book.title = form.title.data
                book.author = form.author.data
                book.publisher = form.publisher.data
                book.year = form.year.data
                book.pages = form.pages.data
                book.description = bleach.clean(form.description.data)

                # Обновляем жанры
                if form.genres.data:
                    book.genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
                else:
                    book.genres = []

                db.session.commit()
                flash('Данные книги успешно обновлены.', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка редактирования: {e}")
                flash('При сохранении данных возникла ошибка. Проверьте корректность введённых данных.', 'danger')

        return render_template('add_book.html', form=form, is_edit=True, book=book)


    @app.route('/book/<int:book_id>/delete', methods=['POST'])
    @login_required
    def delete_book(book_id):
        # Удалять может ТУЛЬКО Администратор
        if current_user.role.name != 'Администратор':
            flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
            return redirect(url_for('index'))

        book = Book.query.get_or_404(book_id)
        try:
            # Находим обложки, связанные с книгой, чтобы удалить файлы с диска
            covers = Cover.query.filter_by(book_id=book.id).all()
            for cover in covers:
                # Проверяем, не используют ли другие книги этот же файл (из-за MD5 дубликатов)
                same_file_covers = Cover.query.filter_by(file_name=cover.file_name).count()
                if same_file_covers == 1:
                    file_path = os.path.join(app.root_path, 'static', 'covers', cover.file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path) # Удаляем файл физически

            # Удаляем саму книгу (ON DELETE CASCADE в БД очистит соединительную таблицу и отзывы)
            db.session.delete(book)
            db.session.commit()
            flash(f'Книга «{book.title}» успешно удалена.', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка при удалении: {e}")
            flash('Не удалось удалить книгу из-за внутренней ошибки базы данных.', 'danger')

        return redirect(url_for('index'))

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)