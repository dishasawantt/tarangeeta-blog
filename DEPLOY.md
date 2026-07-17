# Deploy Tarangeeta to Render + Neon (Free)

This guide deploys the blog for **$0/month** using:

- **[Render](https://render.com)** — hosts the Flask app (free tier, sleeps after 15 min idle)
- **[Neon](https://neon.tech)** — PostgreSQL database (free tier, no expiry)
- **Cloudinary** — media (free tier)
- **Google Cloud Console** — OAuth login (free)

Your live URL will look like: `https://tarangeeta-blog.onrender.com`

---

## Prerequisites

- GitHub account with this repo pushed
- Gmail account (for contact + verification emails)
- Google account (for OAuth + Neon/Render sign-up)

---

## Step 1 — Push code to GitHub

If the repo is not on GitHub yet:

```bash
cd tarangeeta-blog
git add .
git commit -m "Add Render + Neon deployment config"
git remote add origin https://github.com/YOUR_USERNAME/tarangeeta-blog.git
git push -u origin main
```

---

## Step 2 — Create a Neon PostgreSQL database

1. Go to [console.neon.tech](https://console.neon.tech) and sign up (free).
2. Click **New Project** → name it `tarangeeta` → create.
3. On the project dashboard, open **Connection details**.
4. Copy the **connection string** (URI format). It looks like:

   ```
   postgresql://neondb_owner:xxxxxxxx@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

5. Keep this string safe — you will paste it into Render as `DATABASE_URL`.

> **Note:** Neon URLs already use `postgresql://`. The app also auto-converts legacy `postgres://` URLs.

---

## Step 3 — Create a Render web service

### Option A: Blueprint (recommended)

1. Go to [dashboard.render.com](https://dashboard.render.com) → sign up with GitHub.
2. Click **New** → **Blueprint**.
3. Connect your `tarangeeta-blog` repository.
4. Render reads `render.yaml` and creates the web service.
5. When prompted, fill in the secret env vars (see Step 4).

### Option B: Manual setup

1. **New** → **Web Service** → connect your GitHub repo.
2. Configure:

   | Setting | Value |
   |---------|-------|
   | Name | `tarangeeta-blog` |
   | Region | closest to you |
   | Branch | `main` |
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn main:app --bind 0.0.0.0:$PORT --workers 1` |
   | Instance Type | **Free** |

3. Click **Create Web Service** (deploy will fail until env vars are set — that's OK).

---

## Step 4 — Set environment variables on Render

In Render → your service → **Environment** → add:

| Variable | Value | Required |
|----------|-------|----------|
| `DATABASE_URL` | Neon connection string from Step 2 | **Yes** |
| `SECRET_KEY` | Random string — run `python -c "import secrets; print(secrets.token_hex(32))"` | **Yes** |
| `ADMIN_EMAIL` | Your Gmail (admin posts + messages) | **Yes** |
| `GOOGLE_CLIENT_ID` | From Google Console (Step 5) | For Google login |
| `GOOGLE_CLIENT_SECRET` | From Google Console (Step 5) | For Google login |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary dashboard | For media upload |
| `CLOUDINARY_API_KEY` | Cloudinary dashboard | For media upload |
| `CLOUDINARY_API_SECRET` | Cloudinary dashboard | For media upload |
| `MAIL_ADDRESS` | Your Gmail address | For email |
| `MAIL_APP_PASSWORD` | Gmail App Password (Step 6) | For email |

Render auto-sets `RENDER=true` and `PORT` — do not add those manually.

Click **Save Changes** → Render redeploys automatically.

---

## Step 5 — Configure Google OAuth

Replace `YOUR_APP` with your Render service name (e.g. `tarangeeta-blog`).

### 5a. Create OAuth credentials

1. Open [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials).
2. Create or select a project.
3. **APIs & Services** → **OAuth consent screen** → configure (External, add your email as test user if in Testing mode).
4. **Credentials** → **Create Credentials** → **OAuth client ID** → type **Web application**.

### 5b. Set URLs (exact values)

| Field | URL |
|-------|-----|
| **Authorized JavaScript origins** | `https://YOUR_APP.onrender.com` |
| **Authorized redirect URIs** | `https://YOUR_APP.onrender.com/login/google/authorized` |

> This redirect URI is required by Flask-Dance. It is **not** `/google-callback` — that is an internal route after OAuth completes.

### 5c. Copy credentials to Render

- **Client ID** → `GOOGLE_CLIENT_ID`
- **Client secret** → `GOOGLE_CLIENT_SECRET`

Save and redeploy on Render.

---

## Step 6 — Gmail App Password (contact + verification)

1. Enable [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification) on your Google account.
2. Go to [App Passwords](https://myaccount.google.com/apppasswords).
3. Create an app password for **Mail**.
4. Set on Render:
   - `MAIL_ADDRESS` = your Gmail
   - `MAIL_APP_PASSWORD` = the 16-character app password (no spaces)

---

## Step 7 — Cloudinary (media uploads)

1. Sign up at [cloudinary.com](https://cloudinary.com) (free tier).
2. From the dashboard, copy:
   - Cloud name → `CLOUDINARY_CLOUD_NAME`
   - API Key → `CLOUDINARY_API_KEY`
   - API Secret → `CLOUDINARY_API_SECRET`
3. Add to Render env vars and redeploy.

Posts can also use direct media URLs without Cloudinary.

---

## Step 8 — Verify deployment

1. Open `https://YOUR_APP.onrender.com`.
2. First load after idle may take **30–60 seconds** (free tier cold start).
3. Confirm the home page loads and categories appear.
4. **Register** with your `ADMIN_EMAIL` address (or use Google sign-in).
5. If using local registration, check email for verification link (must use production URL).
6. Log in → you should see **Create New Post** (admin only).
7. Create a test post with a Cloudinary upload or image URL.
8. Test search, comments, and contact form.

---

## Step 9 — Create your admin account

Admin access is gated by `ADMIN_EMAIL`. The account must use that exact email.

**Option A — Google (easiest)**  
Sign in with Google using the `ADMIN_EMAIL` account. OAuth users are auto-verified.

**Option B — Email + password**  
1. Register at `/register` with `ADMIN_EMAIL`.
2. Click the verification link in your email.
3. Log in at `/login`.

---

## Architecture

```
Browser
   │
   ▼
Render (Gunicorn + Flask)  ──HTTPS──►  Neon PostgreSQL
   │
   ├──► Cloudinary (media)
   ├──► Google OAuth
   └──► Gmail SMTP (contact / verify)
```

---

## Free tier limits

| Service | Limit |
|---------|-------|
| Render | 750 hrs/month, sleeps after 15 min idle, ~60s cold start |
| Neon | 0.5 GB storage, compute scales to zero when idle |
| Cloudinary | 25 credits/month |

For a personal blog, this is usually enough.

---

## Troubleshooting

### Deploy fails at build

- Check Render logs → **Logs** tab.
- Confirm `requirements.txt` installs cleanly.
- Python version is pinned in `runtime.txt` (3.12.7).

### Database connection errors

- Ensure `DATABASE_URL` includes `?sslmode=require`.
- Use the **pooled** or **direct** Neon connection string (either works).
- Confirm the URL starts with `postgresql://` (app fixes `postgres://` automatically).

### Google login redirects to error

- Redirect URI must be exactly:  
  `https://YOUR_APP.onrender.com/login/google/authorized`
- No trailing slash mismatch.
- JavaScript origin must be `https://YOUR_APP.onrender.com` (no path).

### Emails not sending

- Use a Gmail **App Password**, not your regular password.
- 2-Step Verification must be enabled.
- Check Render logs for SMTP errors (failures are silent in the app).

### Site is slow on first visit

- Normal on Render free tier — service woke from sleep.
- Upgrade to Render Starter ($7/mo) for always-on.

### Admin buttons not showing

- Logged-in email must **exactly match** `ADMIN_EMAIL` on Render.
- Templates use the `ADMIN_EMAIL` env var, not a hardcoded address.

### OAuth works locally but not on Render

- Update Google Console URLs to use `onrender.com`, not `localhost`.
- Remove `OAUTHLIB_INSECURE_TRANSPORT` — it is only set in development.

---

## Redeploying after code changes

Push to `main` on GitHub — Render auto-deploys if connected.

```bash
git add .
git commit -m "Your change"
git push
```

---

## Custom domain (optional, paid on Render)

Render free tier uses `*.onrender.com`. Custom domains require a paid Render plan. You would also add the domain to Google OAuth authorized origins.

---

## Quick reference — URLs to configure

| Service | What to set |
|---------|-------------|
| Google OAuth origin | `https://YOUR_APP.onrender.com` |
| Google OAuth redirect | `https://YOUR_APP.onrender.com/login/google/authorized` |
| Live site | `https://YOUR_APP.onrender.com` |
| Email verify links | Auto — uses `request.host_url` over HTTPS |

---

## Files added for deployment

| File | Purpose |
|------|---------|
| `render.yaml` | Render Blueprint config |
| `Procfile` | Gunicorn start command with `$PORT` |
| `runtime.txt` | Python 3.12.7 |
| `.env.example` | Local env template |
