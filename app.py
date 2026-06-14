import os
import hashlib
import uuid
import bleach
import markdown
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import Config
from models import db, User, Book, Genre, Cover, Role
from forms import LoginForm, BookForm, BookSearchForm, RegisterForm
from forms import ReviewForm
from models import Review

# Разрешённые HTML-теги после рендеринга Markdown
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'code', 'pre', 'hr', 'a'
]
ALLOWED_ATTRS = {'a': ['href', 'title']}

def sanitize_markdown(text):
    """
    Правильный порядок: сначала рендерим Markdown в HTML,
    потом чистим HTML от опасных тегов через Bleach.
    Это сохраняет форматирование и убирает XSS.
    """
    html = markdown.markdown(text)
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.login_message = 'Для выполнения данного действия необходимо пройти процедуру аутентификации'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def utility_processor():
        def page_url(page_num):
            """
            Строит URL для страницы пагинации, сохраняя все текущие
            параметры поиска (включая мультиселекты genres и years).
            """
            args = request.args.to_dict(flat=False)  # flat=False сохраняет списки
            args['page'] = [str(page_num)]
            from urllib.parse import urlencode
            return url_for('index') + '?' + urlencode(args, doseq=True)
        return dict(page_url=page_url)

    # ==========================================
    # МАРШРУТЫ
    # ==========================================

    @app.route('/')
    def index():
        page = request.args.get('page', 1, type=int)

        search_form = BookSearchForm(request.args)

        search_form.genres.choices = [(g.id, g.name) for g in Genre.query.order_by(Genre.name).all()]

        distinct_years = db.session.query(Book.year).distinct().order_by(Book.year.desc()).all()
        search_form.years.choices = [(y[0], str(y[0])) for y in distinct_years if y[0]]

        query = Book.query

        if search_form.title.data:
            query = query.filter(Book.title.ilike(f"%{search_form.title.data}%"))

        if search_form.author.data:
            query = query.filter(Book.author.ilike(f"%{search_form.author.data}%"))

        # ИСПРАВЛЕНИЕ: getlist напрямую из request.args для мультиселектов,
        # чтобы пагинация не теряла выбранные значения
        selected_genres = request.args.getlist('genres', type=int)
        if selected_genres:
            query = query.join(Book.genres).filter(Genre.id.in_(selected_genres))

        selected_years = request.args.getlist('years', type=int)
        if selected_years:
            query = query.filter(Book.year.in_(selected_years))

        if search_form.pages_from.data is not None:
            query = query.filter(Book.pages >= search_form.pages_from.data)
        if search_form.pages_to.data is not None:
            query = query.filter(Book.pages <= search_form.pages_to.data)

        # ИСПРАВЛЕНИЕ: сортировка по году выхода (сначала новые), как требует ТЗ
        query = query.order_by(Book.year.desc())

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

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        form = RegisterForm()
        if form.validate_on_submit():
            # Проверяем совпадение паролей
            if form.password.data != form.password2.data:
                flash('Пароли не совпадают.', 'danger')
                return render_template('register.html', form=form)

            # Проверяем, не занят ли логин
            if User.query.filter_by(login=form.login.data).first():
                flash('Пользователь с таким логином уже существует.', 'danger')
                return render_template('register.html', form=form)

            # Новый пользователь всегда получает роль «Пользователь»
            user_role = Role.query.filter_by(name='Пользователь').first()
            new_user = User(
                login=form.login.data,
                last_name=form.last_name.data,
                first_name=form.first_name.data,
                middle_name=form.middle_name.data or None,
                role=user_role
            )
            new_user.set_password(form.password.data)

            try:
                db.session.add(new_user)
                db.session.commit()
                flash('Регистрация прошла успешно! Войдите в систему.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash('Ошибка при регистрации. Попробуйте ещё раз.', 'danger')

        return render_template('register.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы успешно вышли из системы.', 'success')
        return redirect(url_for('index'))

    @app.route('/book/add', methods=['GET', 'POST'])
    @login_required
    def add_book():
        if current_user.role.name != 'Администратор':
            flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
            return redirect(url_for('index'))

        form = BookForm()
        form.genres.choices = [(g.id, g.name) for g in Genre.query.all()]

        if form.validate_on_submit():
            try:
                # ИСПРАВЛЕНИЕ: сначала рендерим Markdown, потом чистим Bleach
                clean_description = sanitize_markdown(form.description.data)

                new_book = Book(
                    title=form.title.data,
                    description=clean_description,
                    year=form.year.data,
                    publisher=form.publisher.data,
                    author=form.author.data,
                    pages=form.pages.data
                )

                if form.genres.data:
                    selected_genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
                    new_book.genres = selected_genres

                db.session.add(new_book)
                db.session.commit()

                file = form.cover.data
                file_content = file.read()
                md5 = hashlib.md5(file_content).hexdigest()
                file.seek(0)

                existing_cover = Cover.query.filter_by(md5_hash=md5).first()
                if not existing_cover:
                    filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[-1]}"
                    save_path = os.path.join(app.root_path, 'static', 'covers', filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    file.save(save_path)
                    new_cover = Cover(file_name=filename, mime_type=file.mimetype, md5_hash=md5, book_id=new_book.id)
                else:
                    new_cover = Cover(file_name=existing_cover.file_name, mime_type=existing_cover.mime_type, md5_hash=md5, book_id=new_book.id)

                db.session.add(new_cover)
                db.session.commit()

                flash('Книга успешно добавлена!', 'success')
                # ИСПРАВЛЕНИЕ: редирект на страницу просмотра книги, как требует ТЗ
                return redirect(url_for('book_detail', book_id=new_book.id))

            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при добавлении книги: {e}")
                flash('При сохранении данных возникла ошибка. Проверьте корректность введённых данных.', 'danger')

        return render_template('add_book.html', form=form)

    @app.route('/book/<int:book_id>')
    def book_detail(book_id):
        book = Book.query.get_or_404(book_id)

        # Описание уже хранится как очищенный HTML (после sanitize_markdown),
        # поэтому просто подставляем его без повторного рендеринга
        book_description_html = book.description

        reviews = Review.query.filter_by(book_id=book.id).order_by(Review.created_at.desc()).all()

        for r in reviews:
            # Тексты рецензий тоже хранятся как HTML после sanitize_markdown
            r.text_html = r.text

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

        existing = Review.query.filter_by(book_id=book.id, user_id=current_user.id).first()
        if existing:
            flash('Вы уже оставили рецензию на эту книгу.', 'warning')
            return redirect(url_for('book_detail', book_id=book.id))

        form = ReviewForm()
        if form.validate_on_submit():
            try:
                # ИСПРАВЛЕНИЕ: применяем sanitize_markdown к тексту рецензии
                clean_text = sanitize_markdown(form.text.data)
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
        if current_user.role.name not in ['Администратор', 'Модератор']:
            flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
            return redirect(url_for('index'))

        book = Book.query.get_or_404(book_id)
        form = BookForm(obj=book)
        form.genres.choices = [(g.id, g.name) for g in Genre.query.all()]

        del form.cover

        if request.method == 'GET':
            form.genres.data = [g.id for g in book.genres]

        if form.validate_on_submit():
            try:
                book.title = form.title.data
                book.author = form.author.data
                book.publisher = form.publisher.data
                book.year = form.year.data
                book.pages = form.pages.data
                # ИСПРАВЛЕНИЕ: применяем sanitize_markdown и при редактировании
                book.description = sanitize_markdown(form.description.data)

                if form.genres.data:
                    book.genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
                else:
                    book.genres = []

                db.session.commit()
                flash('Данные книги успешно обновлены.', 'success')
                # ИСПРАВЛЕНИЕ: редирект на страницу просмотра книги
                return redirect(url_for('book_detail', book_id=book.id))
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка редактирования: {e}")
                flash('При сохранении данных возникла ошибка. Проверьте корректность введённых данных.', 'danger')

        return render_template('add_book.html', form=form, is_edit=True, book=book)

    @app.route('/book/<int:book_id>/delete', methods=['POST'])
    @login_required
    def delete_book(book_id):
        if current_user.role.name != 'Администратор':
            flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
            return redirect(url_for('index'))

        book = Book.query.get_or_404(book_id)
        try:
            covers = Cover.query.filter_by(book_id=book.id).all()
            for cover in covers:
                same_file_covers = Cover.query.filter_by(file_name=cover.file_name).count()
                if same_file_covers == 1:
                    file_path = os.path.join(app.root_path, 'static', 'covers', cover.file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)

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