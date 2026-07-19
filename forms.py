import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, PasswordField, SelectField, TextAreaField, HiddenField
from wtforms.validators import DataRequired, URL, Optional, Email, ValidationError

ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov', 'avi', 'webm', 'mkv']

def validate_email_domain(form, field):
    if not re.match(r'^[^@]+@[^@]+\.[a-zA-Z]{2,}$', field.data):
        raise ValidationError("Enter a valid email address.")


class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    category = SelectField("Category", coerce=int, validators=[DataRequired()])
    media_url = StringField("Media URL", validators=[Optional(), URL()])
    media_upload = FileField("Upload Media", validators=[FileAllowed(ALLOWED_EXTENSIONS)])
    body = HiddenField()  # block editor content is saved via the autosave/publish JSON API
    submit = SubmitField("Submit Post")


class CreateCanvasPostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    category = SelectField("Category", coerce=int, validators=[DataRequired()])
    media_url = StringField("Media URL", validators=[Optional(), URL()])
    media_upload = FileField("Upload Media", validators=[FileAllowed(ALLOWED_EXTENSIONS)])
    canvas_data = HiddenField()
    canvas_html = HiddenField()
    canvas_css = HiddenField()
    submit = SubmitField("Save Canvas Post")


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), validate_email_domain])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign Me Up!")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), validate_email_domain])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Let Me In!")


class CommentForm(FlaskForm):
    comment_text = TextAreaField("", validators=[DataRequired()])
    submit = SubmitField("Post Comment")


class SearchForm(FlaskForm):
    query = StringField("Search", validators=[DataRequired()])
    submit = SubmitField("Search")


class ContactForm(FlaskForm):
    message = TextAreaField("Message", validators=[DataRequired()])
    submit = SubmitField("Send Message")
