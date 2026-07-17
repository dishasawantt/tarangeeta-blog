import os
import hashlib
import smtplib
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_dance.contrib.google import make_google_blueprint, google
from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import cloudinary
import cloudinary.uploader

from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, SearchForm, ContactForm

load_dotenv()


def get_database_url():
    url = os.environ.get('DATABASE_URL', 'sqlite:///posts.db')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['CKEDITOR_PKG_TYPE'] = 'full'

if os.environ.get('RENDER') or os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PREFERRED_URL_SCHEME'] = 'https'

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

CKEditor(app)
Bootstrap5(app)

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

MAIL_ADDRESS = os.environ.get('MAIL_ADDRESS')
MAIL_APP_PASSWORD = os.environ.get('MAIL_APP_PASSWORD')
MUSIC_URL = os.environ.get('MUSIC_URL', 'https://res.cloudinary.com/dxxkklkqy/video/upload/v1767996842/relaxing-music-with-nature-sound-and-flute-284493_ayiq0g.mp3')

def send_email(name, email, message):
    if not MAIL_ADDRESS or not MAIL_APP_PASSWORD:
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_ADDRESS
        msg['To'] = MAIL_ADDRESS
        msg['Subject'] = f"New Contact from Tarangeeta: {name}"
        body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MAIL_ADDRESS, MAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception:
        pass

def generate_verification_token():
    return secrets.token_urlsafe(32)

def send_verification_email(email, token, base_url):
    if not MAIL_ADDRESS or not MAIL_APP_PASSWORD:
        return
    try:
        verify_url = f"{base_url}verify/{token}"
        msg = MIMEMultipart()
        msg['From'] = MAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = "Verify your email - Tarangeeta"
        body = f"Welcome to Tarangeeta!\n\nVerify your email: {verify_url}\n\n— Tarangeeta"
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MAIL_ADDRESS, MAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception:
        pass

login_manager = LoginManager()
login_manager.init_app(app)

if os.environ.get('FLASK_DEBUG') or os.environ.get('FLASK_ENV') == 'development':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

google_bp = make_google_blueprint(
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
    redirect_to="google_callback"
)
app.register_blueprint(google_bp, url_prefix="/login")

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'dishasawantt@gmail.com')
POSTS_PER_PAGE = 6
VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'webm', 'mkv', 'ogg', 'ogv'}


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
db.init_app(app)


class Category(db.Model):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    posts = relationship("BlogPost", back_populates="category")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(String(10), nullable=False, default='image')
    comments = relationship("Comment", back_populates="parent_post", cascade="all, delete-orphan")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    email_verified: Mapped[bool] = mapped_column(db.Boolean, default=False)
    verification_token: Mapped[str] = mapped_column(String(100), nullable=True)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


@app.template_filter('gravatar')
def gravatar_filter(email, size=100):
    digest = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    return f'https://www.gravatar.com/avatar/{digest}?s={size}&d=retro'


@app.context_processor
def inject_globals():
    return dict(search_form=SearchForm(), ADMIN_EMAIL=ADMIN_EMAIL, MUSIC_URL=MUSIC_URL)


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.email != ADMIN_EMAIL:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


def get_media_type(url):
    if not url:
        return 'image'
    ext = url.rsplit('.', 1)[-1].lower().split('?')[0]
    return 'video' if ext in VIDEO_EXTENSIONS else 'image'


def upload_media(file):
    if not file or not os.environ.get('CLOUDINARY_CLOUD_NAME'):
        return None, None
    try:
        is_video = get_media_type(file.filename) == 'video'
        result = cloudinary.uploader.upload(file, resource_type='video' if is_video else 'image')
        return result.get('secure_url'), 'video' if is_video else 'image'
    except Exception:
        return None, None


def init_categories():
    for name in ["Spiritual", "Technology", "Personal", "Emotions", "Other"]:
        if not db.session.execute(db.select(Category).where(Category.name == name)).scalar():
            db.session.add(Category(name=name))
    db.session.commit()


with app.app_context():
    db.create_all()
    init_categories()


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if db.session.execute(db.select(User).where(User.email == form.email.data)).scalar():
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        token = generate_verification_token()
        user = User(
            email=form.email.data,
            name=form.name.data,
            password=generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8),
            email_verified=False,
            verification_token=token
        )
        db.session.add(user)
        db.session.commit()
        send_verification_email(form.email.data, token, request.host_url)
        flash("Please check your email to verify your account before logging in.")
        return redirect(url_for("login"))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        if not check_password_hash(user.password, form.password.data):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        if not user.email_verified and user.email != ADMIN_EMAIL:
            flash("Please verify your email before logging in. Check your inbox.")
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=form, current_user=current_user)


@app.route('/verify/<token>')
def verify_email(token):
    user = db.session.execute(db.select(User).where(User.verification_token == token)).scalar()
    if user:
        user.email_verified = True
        user.verification_token = None
        db.session.commit()
        flash("Email verified! You can now log in.")
    else:
        flash("Invalid or expired verification link.")
    return redirect(url_for('login'))


@app.route('/resend-verification')
def resend_verification():
    if current_user.is_authenticated:
        if not current_user.email_verified:
            token = generate_verification_token()
            current_user.verification_token = token
            db.session.commit()
            send_verification_email(current_user.email, token, request.host_url)
            flash("Verification email sent! Check your inbox.")
        else:
            flash("Your email is already verified.")
    return redirect(url_for('get_all_posts'))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/google-callback')
def google_callback():
    if not google.authorized:
        return redirect(url_for('google.login'))
    resp = google.get('/oauth2/v2/userinfo')
    if resp.ok:
        user_info = resp.json()
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0])
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if not user:
            user = User(email=email, name=name, password='google-oauth', email_verified=True)
            db.session.add(user)
            db.session.commit()
        elif not user.email_verified:
            user.email_verified = True
            db.session.commit()
        login_user(user)
        return redirect(url_for('get_all_posts'))
    flash('Failed to get user info from Google.')
    return redirect(url_for('login'))


@app.route('/')
def get_all_posts():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    query = db.select(BlogPost).order_by(BlogPost.id.desc())
    if category_id:
        query = query.where(BlogPost.category_id == category_id)
    pagination = db.paginate(query, page=page, per_page=POSTS_PER_PAGE, error_out=False)
    categories = db.session.execute(db.select(Category)).scalars().all()
    return render_template("index.html", all_posts=pagination.items, current_user=current_user,
                           pagination=pagination, categories=categories, selected_category=category_id)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        if not current_user.email_verified and current_user.email != ADMIN_EMAIL:
            flash("Please verify your email to comment.")
            return redirect(url_for("show_post", post_id=post_id))
        db.session.add(Comment(text=form.comment_text.data, comment_author=current_user, parent_post=post))
        db.session.commit()
    return render_template("post.html", post=post, current_user=current_user, form=form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    categories = db.session.execute(db.select(Category)).scalars().all()
    form.category.choices = [(c.id, c.name) for c in categories]
    if form.validate_on_submit():
        media_url = form.media_url.data
        media_type = get_media_type(media_url) if media_url else 'image'
        if form.media_upload.data:
            uploaded_url, uploaded_type = upload_media(form.media_upload.data)
            if uploaded_url:
                media_url, media_type = uploaded_url, uploaded_type
        if not media_url:
            flash("Please provide a media URL or upload an image/video.")
            return render_template("make-post.html", form=form, current_user=current_user)
        db.session.add(BlogPost(
            title=form.title.data, subtitle=form.subtitle.data, body=form.body.data,
            media_url=media_url, media_type=media_type, author=current_user,
            category_id=form.category.data, date=date.today().strftime("%B %d, %Y")
        ))
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    categories = db.session.execute(db.select(Category)).scalars().all()
    form = CreatePostForm(title=post.title, subtitle=post.subtitle, media_url=post.media_url,
                          body=post.body, category=post.category_id)
    form.category.choices = [(c.id, c.name) for c in categories]
    if form.validate_on_submit():
        media_url = form.media_url.data
        media_type = get_media_type(media_url) if media_url else post.media_type
        if form.media_upload.data:
            uploaded_url, uploaded_type = upload_media(form.media_upload.data)
            if uploaded_url:
                media_url, media_type = uploaded_url, uploaded_type
        post.title, post.subtitle = form.title.data, form.subtitle.data
        post.media_url, post.media_type = media_url, media_type
        post.category_id, post.body = form.category.data, form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=form, is_edit=True, current_user=current_user, post=post)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    db.session.delete(db.get_or_404(BlogPost, post_id))
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/search")
def search():
    query = request.args.get('query', '')
    page = request.args.get('page', 1, type=int)
    if not query:
        return render_template("search.html", posts=[], query=query, pagination=None, current_user=current_user)
    search_query = db.select(BlogPost).where(
        db.or_(BlogPost.title.ilike(f'%{query}%'), BlogPost.subtitle.ilike(f'%{query}%'), BlogPost.body.ilike(f'%{query}%'))
    ).order_by(BlogPost.id.desc())
    pagination = db.paginate(search_query, page=page, per_page=POSTS_PER_PAGE, error_out=False)
    return render_template("search.html", posts=pagination.items, query=query, pagination=pagination, current_user=current_user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if not current_user.is_authenticated:
        flash("Please log in to send a message.")
        return redirect(url_for('login'))
    form = ContactForm()
    msg_sent = False
    if form.validate_on_submit():
        db.session.add(ContactMessage(
            name=current_user.name, email=current_user.email,
            message=form.message.data, date=date.today().strftime("%B %d, %Y")
        ))
        db.session.commit()
        send_email(current_user.name, current_user.email, form.message.data)
        msg_sent = True
    return render_template("contact.html", form=form, msg_sent=msg_sent, current_user=current_user)


@app.route("/messages")
@admin_only
def view_messages():
    messages = db.session.execute(db.select(ContactMessage).order_by(ContactMessage.id.desc())).scalars().all()
    return render_template("messages.html", messages=messages, current_user=current_user)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
