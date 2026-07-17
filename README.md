# tarangeeta-blog

> Personal spiritual and tech blog with Flask CMS — user auth, rich-text posts, Cloudinary media, Google OAuth, and comments.

## Features

- User registration and login (local + Google OAuth)
- Rich-text posts with Flask-CKEditor
- Media uploads via Cloudinary
- Categories, search, pagination, and comments
- Contact form with email notifications
- Admin panel (email-gated)

## Technology Stack

| Layer | Technologies |
|---|---|
| Backend | Flask 3, SQLAlchemy, Flask-Login, Flask-WTF |
| Auth | Google OAuth (Flask-Dance), pbkdf2 password hashing |
| Media | Cloudinary |
| Frontend | Bootstrap 5, Jinja2 templates |
| Deployment | Gunicorn (Heroku-style Procfile) |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes (production) | Flask session secret |
| `DATABASE_URL` | No | PostgreSQL URL (SQLite default) |
| `ADMIN_EMAIL` | Yes | Admin user email |
| `GOOGLE_CLIENT_ID` | For OAuth | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For OAuth | Google OAuth secret |
| `CLOUDINARY_CLOUD_NAME` | For media | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | For media | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | For media | Cloudinary API secret |

## Run

```bash
python main.py
```

Production:

```bash
gunicorn main:app
```

## Author

**Disha Sawant** — [GitHub](https://github.com/dishasawantt)
