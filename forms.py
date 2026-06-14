from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, IntegerField, SelectMultipleField
from wtforms.validators import DataRequired, NumberRange, Optional
from wtforms import SelectField

# 1. Форма авторизации
class LoginForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired(message="Это поле обязательно для заполнения")])
    password = PasswordField('Пароль', validators=[DataRequired(message="Это поле обязательно для заполнения")])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

# 2. Форма добавления/редактирования книги
class BookForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(message="Это поле обязательно для заполнения")])
    description = TextAreaField('Описание (Markdown)', validators=[DataRequired(message="Это поле обязательно для заполнения")])
    year = IntegerField('Год', validators=[DataRequired(message="Это поле обязательно для заполнения")])
    publisher = StringField('Издательство', validators=[DataRequired(message="Это поле обязательно для заполнения")])
    author = StringField('Автор', validators=[DataRequired(message="Это поле обязательно для заполнения")])
    pages = IntegerField('Объём (страниц)', validators=[
        DataRequired(message="Это поле обязательно для заполнения"),
        NumberRange(min=1, message="Количество страниц должно быть больше 0")
    ])
    genres = SelectMultipleField('Жанры', coerce=int)
    cover = FileField('Обложка', validators=[
        FileRequired(message="Необходимо загрузить обложку"),
        FileAllowed(['jpg', 'png', 'jpeg'], 'Только изображения типов JPG, PNG, JPEG!')
    ])
    submit = SubmitField('Сохранить')

# 3. ВАРИАНТ 3: Форма поиска книг
# ИСПРАВЛЕНИЕ: добавлен Optional() для pages_from и pages_to,
# иначе WTForms падает с ошибкой при пустых числовых полях
class BookSearchForm(FlaskForm):
    class Meta:
        # Отключаем CSRF для GET-формы поиска
        csrf = False

    title = StringField('Название книги')
    author = StringField('Автор')
    genres = SelectMultipleField('Жанры', coerce=int)
    years = SelectMultipleField('Годы', coerce=int)
    pages_from = IntegerField('Объём от', validators=[Optional()])
    pages_to   = IntegerField('Объём до', validators=[Optional()])
    submit = SubmitField('Найти')

class RegisterForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired(message="Это поле обязательно")])
    last_name = StringField('Фамилия', validators=[DataRequired(message="Это поле обязательно")])
    first_name = StringField('Имя', validators=[DataRequired(message="Это поле обязательно")])
    middle_name = StringField('Отчество (необязательно)')
    password = PasswordField('Пароль', validators=[DataRequired(message="Это поле обязательно")])
    password2 = PasswordField('Повторите пароль', validators=[DataRequired(message="Это поле обязательно")])
    submit = SubmitField('Зарегистрироваться')

class ReviewForm(FlaskForm):
    rating = SelectField('Оценка', coerce=int, choices=[
        (5, '5 – отлично'),
        (4, '4 – хорошо'),
        (3, '3 – удовлетворительно'),
        (2, '2 – неудовлетворительно'),
        (1, '1 – плохо'),
        (0, '0 – ужасно')
    ], default=5)
    text = TextAreaField('Текст рецензии (Markdown)', validators=[DataRequired(message="Напишите текст рецензии")])
    submit = SubmitField('Сохранить')