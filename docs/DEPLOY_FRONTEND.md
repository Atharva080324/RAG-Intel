# Deploy the React Frontend (Vercel or Netlify)

> The frontend is a **static Vite build** — no server required.
> It talks to the FastAPI backend via `VITE_API_BASE`.

---

## Option A — Vercel (recommended)

### 1. Push the repo to GitHub

The `frontend/` directory should be inside your repository root.

### 2. Create a Vercel project

1. Go to [vercel.com/new](https://vercel.com/new) and import your repository.
2. **Root Directory**: set to `frontend` (click the pencil icon).
3. **Framework Preset**: Vite (auto-detected).
4. **Build Command**: `npm run build`
5. **Output Directory**: `dist`

### 3. Set environment variables in Vercel

In **Project Settings → Environment Variables**, add:

| Name | Value |
|------|-------|
| `VITE_API_BASE` | `https://rag-intel.duckdns.org` (your Caddy domain) |

### 4. Deploy

Click **Deploy**. Vercel assigns a URL like `https://rag-intel.vercel.app`.

---

## Option B — Netlify

### 1. Connect repository

1. [app.netlify.com/start](https://app.netlify.com/start) → connect GitHub.
2. **Base directory**: `frontend`
3. **Build command**: `npm run build`
4. **Publish directory**: `frontend/dist`

### 2. Environment variables

**Site Settings → Build & Deploy → Environment**:

| Key | Value |
|-----|-------|
| `VITE_API_BASE` | `https://rag-intel.duckdns.org` |

### 3. Redirects (SPA fallback)

Create `frontend/public/_redirects`:

```
/*  /index.html  200
```

---

## After Deployment

### Update CORS on the backend

In your `.env.production` on the Oracle VM:

```env
CORS_ORIGINS=https://rag-intel.vercel.app
FRONTEND_URL=https://rag-intel.vercel.app
```

Then restart the API:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d api
```

### Update Google OAuth Redirect URI

1. Go to [console.cloud.google.com](https://console.cloud.google.com) →
   **APIs & Services → Credentials → your OAuth Web client**.
2. Under **Authorised redirect URIs**, add:
   ```
   https://rag-intel.duckdns.org/auth/google/callback
   ```
3. Under **Authorised JavaScript origins**, add:
   ```
   https://rag-intel.vercel.app
   ```
4. Save. OAuth changes take effect in ~5 minutes.

---

## Verify

```bash
# Build passes locally
cd frontend
npm run build
npm run test

# Open the deployed URL, click "Try Demo"
# → Should receive a JWT and redirect to /documents
# → Uploaded demo docs should appear
# → Clicking "Chat" → streaming answer works
```

---

## Continuous Deployment

Both Vercel and Netlify automatically rebuild on every push to `main`.
To change the API base URL, update the environment variable in the dashboard —
no code change needed.
