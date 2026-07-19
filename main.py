import os
import json
import hashlib
import smtplib
import secrets
from xml.sax.saxutils import escape
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, render_template, redirect, url_for, flash, request, g, jsonify
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor, upload_success, upload_fail
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_dance.contrib.google import make_google_blueprint, google
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import cloudinary
import cloudinary.uploader

from forms import CreatePostForm, CreateCanvasPostForm, RegisterForm, LoginForm, CommentForm, SearchForm, ContactForm
from editor_render import render_blocks_to_html, html_to_blocks, estimate_reading_time

load_dotenv()


def get_database_url():
    url = os.environ.get('DATABASE_URL', 'sqlite:///posts.db')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


IS_PRODUCTION = bool(os.environ.get('RENDER') or os.environ.get('FLASK_ENV') == 'production')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['CKEDITOR_PKG_TYPE'] = 'full'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # static assets are cache-busted via ?v= query params

if IS_PRODUCTION:
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PREFERRED_URL_SCHEME'] = 'https'

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

CKEditor(app)
Bootstrap5(app)
csrf = CSRFProtect(app)

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

MAIL_ADDRESS = os.environ.get('MAIL_ADDRESS')
MAIL_APP_PASSWORD = os.environ.get('MAIL_APP_PASSWORD')
MUSIC_URL = os.environ.get('MUSIC_URL', 'https://res.cloudinary.com/dxxkklkqy/video/upload/q_auto/v1767996842/relaxing-music-with-nature-sound-and-flute-284493_ayiq0g.mp3')

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
# Neutral placeholder cover for brand-new drafts that don't have one yet.
DEFAULT_COVER = 'https://images.unsplash.com/photo-1478720568477-152d9b164e26?w=1200'


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
    layout_type: Mapped[str] = mapped_column(String(20), nullable=False, default='article')
    canvas_data: Mapped[str] = mapped_column(Text, nullable=True)
    canvas_html: Mapped[str] = mapped_column(Text, nullable=True)
    canvas_css: Mapped[str] = mapped_column(Text, nullable=True)
    # Block editor (Editor.js) — content_json is the source of truth, body holds
    # the server-rendered HTML shown on the published page.
    content_json: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='published')
    reading_time: Mapped[int] = mapped_column(Integer, nullable=True)
    updated_date: Mapped[str] = mapped_column(String(250), nullable=True)
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
    return dict(search_form=SearchForm(), ADMIN_EMAIL=ADMIN_EMAIL, MUSIC_URL=MUSIC_URL, csp_nonce=getattr(g, 'csp_nonce', ''))


@app.before_request
def set_csp_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)


# CKEditor 4 and GrapesJS both bootstrap their editing surfaces by injecting
# inline <script>/<style> into their own iframe documents, which can't carry
# our per-request nonce. A strict nonce-only script-src silently breaks them,
# so these admin editing pages get a relaxed (still self-hosted-only) policy.
RICH_EDITOR_ENDPOINTS = {'add_new_post', 'edit_post', 'add_new_canvas_post', 'edit_post_canvas'}

# The canvas post render is deliberately framed by our own post page (sandboxed
# iframe), so it alone needs frame-ancestors 'self' instead of the site default.
CANVAS_FRAME_ENDPOINT = 'show_post_canvas_frame'


@app.after_request
def set_security_headers(response):
    nonce = getattr(g, 'csp_nonce', None) or secrets.token_urlsafe(16)
    script_src = "'self' 'unsafe-inline'" if request.endpoint in RICH_EDITOR_ENDPOINTS else f"'self' 'nonce-{nonce}'"
    frame_ancestors = "'self'" if request.endpoint == CANVAS_FRAME_ENDPOINT else "'none'"
    csp = (
        "default-src 'self'; "
        f"script-src {script_src} https://cdn.jsdelivr.net https://use.fontawesome.com https://cdn.ckeditor.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.ckeditor.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://use.fontawesome.com https://cdn.ckeditor.com; "
        "img-src 'self' data: https://res.cloudinary.com https://www.gravatar.com https://images.unsplash.com https://cdn.ckeditor.com; "
        "media-src 'self' https://res.cloudinary.com; "
        "connect-src 'self' https://cdn.ckeditor.com; "
        "form-action 'self' https://accounts.google.com; "
        f"frame-ancestors {frame_ancestors}; "
        "base-uri 'self'; "
        "object-src 'none'"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY' if frame_ancestors == "'none'" else 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


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


def run_startup_migrations():
    """db.create_all() only adds new tables, not new columns on existing ones."""
    inspector = db.inspect(db.engine)
    existing_columns = {col['name'] for col in inspector.get_columns('blog_posts')}
    new_columns = {
        'layout_type': "VARCHAR(20) DEFAULT 'article'",
        'canvas_data': "TEXT",
        'canvas_html': "TEXT",
        'canvas_css': "TEXT",
        'content_json': "TEXT",
        'status': "VARCHAR(20) DEFAULT 'published'",
        'reading_time': "INTEGER",
        'updated_date': "VARCHAR(250)",
    }
    for name, sql_type in new_columns.items():
        if name not in existing_columns:
            db.session.execute(db.text(f"ALTER TABLE blog_posts ADD COLUMN {name} {sql_type}"))
    db.session.commit()


with app.app_context():
    db.create_all()
    run_startup_migrations()
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


def visible_posts():
    """Base query for publicly-visible posts (published; NULL treated as published
    for rows that predate the status column)."""
    return db.select(BlogPost).where(
        db.or_(BlogPost.status == 'published', BlogPost.status.is_(None))
    )


@app.route('/')
def get_all_posts():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    query = visible_posts().order_by(BlogPost.id.desc())
    if category_id:
        query = query.where(BlogPost.category_id == category_id)
    pagination = db.paginate(query, page=page, per_page=POSTS_PER_PAGE, error_out=False)
    categories = db.session.execute(db.select(Category)).scalars().all()
    return render_template("index.html", all_posts=pagination.items, current_user=current_user,
                           pagination=pagination, categories=categories, selected_category=category_id)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    is_admin = current_user.is_authenticated and current_user.email == ADMIN_EMAIL
    if post.status == 'draft' and not is_admin:
        abort(404)
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


@app.route("/post/<int:post_id>/canvas-frame")
def show_post_canvas_frame(post_id):
    post = db.get_or_404(BlogPost, post_id)
    if post.layout_type != 'canvas':
        abort(404)
    return render_template("post-canvas-frame.html", post=post)


@app.route("/upload-ckeditor-image", methods=["POST"])
@admin_only
def upload_ckeditor_image():
    f = request.files.get('upload')
    if not f or get_media_type(f.filename) != 'image':
        return upload_fail(message="Please upload an image file.")
    url, media_type = upload_media(f)
    if not url:
        return upload_fail(message="Image upload failed. Check Cloudinary configuration.")
    return upload_success(url=url, filename=f.filename)


@app.route("/upload-canvas-image", methods=["POST"])
@admin_only
def upload_canvas_image():
    urls = []
    for f in request.files.getlist('files'):
        if get_media_type(f.filename) != 'image':
            continue
        url, media_type = upload_media(f)
        if url:
            urls.append(url)
    if not urls:
        return jsonify(data=[]), 400
    return jsonify(data=urls)


def unique_post_title(title, exclude_id=None):
    """BlogPost.title has a UNIQUE index; return a collision-free variant."""
    base = ((title or "").strip() or "Untitled")[:250]
    candidate, n = base, 2
    while True:
        q = db.select(BlogPost.id).where(BlogPost.title == candidate)
        if exclude_id:
            q = q.where(BlogPost.id != exclude_id)
        if not db.session.execute(q).scalar():
            return candidate
        candidate = f"{base[:240]} ({n})"
        n += 1


def _content_doc(post):
    """Editor.js document to load into the editor (or None for a blank post)."""
    if post is None:
        return None
    if post.content_json:
        try:
            return json.loads(post.content_json)
        except (ValueError, TypeError):
            pass
    if post.body:  # legacy CKEditor post — best-effort import
        return html_to_blocks(post.body)
    return None


@app.route("/new-post")
@admin_only
def add_new_post():
    categories = db.session.execute(db.select(Category)).scalars().all()
    return render_template("edit-post-block.html", post=None, is_edit=False,
                           categories=categories, content_doc=None, cover_url='',
                           current_user=current_user)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    if post.layout_type == 'canvas':
        return redirect(url_for('edit_post_canvas', post_id=post.id))
    categories = db.session.execute(db.select(Category)).scalars().all()
    cover_url = post.media_url if post.media_url and post.media_url != DEFAULT_COVER else ''
    return render_template("edit-post-block.html", post=post, is_edit=True,
                           categories=categories, content_doc=_content_doc(post),
                           cover_url=cover_url, current_user=current_user)


@app.route("/api/posts/autosave", methods=["POST"])
@admin_only
def autosave_post():
    payload = request.get_json(silent=True) or {}
    content = payload.get('content_json')
    content_str = json.dumps(content) if isinstance(content, (dict, list)) else (content or '')
    body_html = render_blocks_to_html(content_str)
    minutes, words = estimate_reading_time(content_str)
    media_url = (payload.get('media_url') or '').strip()
    media_type = get_media_type(media_url) if media_url else 'image'
    category_id = payload.get('category_id') or None
    subtitle = (payload.get('subtitle') or '').strip()
    now = date.today().strftime("%B %d, %Y")
    post_id = payload.get('id')

    post = db.session.get(BlogPost, post_id) if post_id else None
    if post_id and not post:
        return jsonify(error='not found'), 404

    if post is None:
        # Set every NOT NULL column at construction: the unique_post_title()
        # SELECT below would otherwise autoflush a half-built row.
        post = BlogPost(
            author=current_user, date=now, status='draft', layout_type='article',
            title=unique_post_title(payload.get('title')), subtitle=subtitle,
            body=body_html, content_json=content_str,
            media_url=media_url or DEFAULT_COVER, media_type=media_type,
            category_id=category_id, reading_time=minutes, updated_date=now,
        )
        db.session.add(post)
    else:
        post.title = unique_post_title(payload.get('title'), exclude_id=post.id)
        post.subtitle = subtitle
        post.category_id = category_id
        if media_url:
            post.media_url, post.media_type = media_url, media_type
        post.body = body_html
        post.content_json = content_str
        post.reading_time = minutes
        post.updated_date = now

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error='save failed'), 500
    return jsonify(id=post.id, status=post.status, title=post.title,
                   saved_at=now, reading_time=minutes, word_count=words)


@app.route("/api/posts/<int:post_id>/publish", methods=["POST"])
@admin_only
def publish_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    if post.content_json:
        post.body = render_blocks_to_html(post.content_json)
        post.reading_time, _ = estimate_reading_time(post.content_json)
    if not (post.body or '').strip():
        return jsonify(error='Add some content before publishing.'), 400
    post.status = 'published'
    post.updated_date = date.today().strftime("%B %d, %Y")
    db.session.commit()
    return jsonify(redirect=url_for('show_post', post_id=post.id))


@app.route("/api/editor/upload-image", methods=["POST"])
@admin_only
def editor_upload_image():
    f = request.files.get('image')
    if not f or get_media_type(f.filename) != 'image':
        return jsonify(success=0, message="Please choose an image file.")
    url, _ = upload_media(f)
    if not url:
        return jsonify(success=0, message="Upload failed. Check Cloudinary configuration.")
    return jsonify(success=1, file={"url": url})


@app.route("/api/editor/fetch-image", methods=["POST"])
@admin_only
def editor_fetch_image():
    url = (request.get_json(silent=True) or {}).get('url', '').strip()
    if not url:
        return jsonify(success=0, message="No URL provided.")
    return jsonify(success=1, file={"url": url})


@app.route("/drafts")
@admin_only
def list_drafts():
    drafts = db.session.execute(
        db.select(BlogPost).where(BlogPost.status == 'draft').order_by(BlogPost.id.desc())
    ).scalars().all()
    return render_template("drafts.html", drafts=drafts, current_user=current_user)


@app.route("/new-post-canvas", methods=["GET", "POST"])
@admin_only
def add_new_canvas_post():
    form = CreateCanvasPostForm()
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
            return render_template("make-canvas-post.html", form=form, current_user=current_user)
        if not form.canvas_html.data:
            flash("Please add some content to the canvas before saving.")
            return render_template("make-canvas-post.html", form=form, current_user=current_user)
        db.session.add(BlogPost(
            title=form.title.data, subtitle=form.subtitle.data, body='',
            media_url=media_url, media_type=media_type, author=current_user,
            category_id=form.category.data, date=date.today().strftime("%B %d, %Y"),
            layout_type='canvas', canvas_data=form.canvas_data.data,
            canvas_html=form.canvas_html.data, canvas_css=form.canvas_css.data
        ))
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-canvas-post.html", form=form, current_user=current_user)


@app.route("/edit-post-canvas/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post_canvas(post_id):
    post = db.get_or_404(BlogPost, post_id)
    categories = db.session.execute(db.select(Category)).scalars().all()
    form = CreateCanvasPostForm(title=post.title, subtitle=post.subtitle, media_url=post.media_url,
                                 category=post.category_id)
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
        post.category_id = form.category.data
        if form.canvas_html.data:
            post.canvas_data, post.canvas_html, post.canvas_css = form.canvas_data.data, form.canvas_html.data, form.canvas_css.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-canvas-post.html", form=form, is_edit=True, current_user=current_user, post=post)


@app.route("/delete/<int:post_id>", methods=["POST"])
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
    search_query = visible_posts().where(
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


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", current_user=current_user), 404


@app.route("/favicon.ico")
def favicon_ico():
    return redirect("https://res.cloudinary.com/dxxkklkqy/image/upload/v1767996799/favicon_x5lrfp.png")


@app.route("/robots.txt")
def robots_txt():
    body = f"User-agent: *\nAllow: /\nSitemap: {request.host_url}sitemap.xml\n"
    return app.response_class(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    posts = db.session.execute(visible_posts()).scalars().all()
    urls = [request.host_url, request.host_url + "about", request.host_url + "contact"]
    urls += [f"{request.host_url}post/{post.id}" for post in posts]
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        body.append(f"<url><loc>{escape(url)}</loc></url>")
    body.append("</urlset>")
    return app.response_class("\n".join(body), mimetype="application/xml")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
