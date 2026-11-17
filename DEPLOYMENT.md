# FlowShark Production Deployment Guide: Render (Backend) + Vercel (Frontend)

This guide walks you through deploying FlowShark live to production:
- **Backend API & Background Worker**: Hosted on **Render** (FastAPI, non-destructive IMAP sync, SQLite/PostgreSQL, Gemini AI).
- **Frontend SPA Dashboard**: Hosted on **Vercel** (React, Vite, Tailwind CSS).

---

## Architecture Overview

```mermaid
flowchart LR
    A["User Browser"] -->|HTTPS| B["Vercel (React Frontend)<br>https://flowshark.vercel.app"]
    B -->|REST API / JSON| C["Render Web Service (FastAPI Backend)<br>https://flowshark-api.onrender.com"]
    C -->|IMAP SSL (Port 993)| D["Gmail Servers (Non-destructive Body.Peek)"]
    C -->|Generative AI API| E["Google Gemini / OpenAI"]
    C -->|SQLAlchemy| F["SQLite Persistent Disk / PostgreSQL"]
```

---

## Part 1: Deploy Backend to Render

### Step 1: Push Code to GitHub
Ensure your repository is pushed to GitHub:
```bash
git add .
git commit -m "Configure FlowShark for Vercel and Render production deployment"
git push origin main
```

### Step 2: Create a Web Service on Render
1. Log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Connect your GitHub repository.
4. Fill in the following service settings:

| Setting | Value |
| :--- | :--- |
| **Name** | `flowshark-api` *(or your preferred name)* |
| **Region** | Oregon (US West) or your nearest region |
| **Root Directory** | `gmail-fastapi-integration` |
| **Runtime** | `Python` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | **Free** *(or Starter)* |

*(Alternatively, if you use Render Blueprints, choose "Blueprint" and point to `gmail-fastapi-integration/render.yaml`)*.

### Step 3: Configure Environment Variables on Render
Under the **Environment** tab of your Render Web Service, add the following variables:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | Enables production mode |
| `LOG_LEVEL` | `info` | Structured logging level |
| `BACKGROUND_SYNC_ENABLED` | `true` | Runs continuous 30-second IMAP sync |
| `BACKGROUND_SYNC_INTERVAL_SECONDS` | `30` | Sync frequency in seconds |
| `GMAIL_ADDRESS` | `yourcompany@gmail.com` | Your business Gmail address |
| `GMAIL_APP_PASSWORD` | `abcd efgh ijkl mnop` | 16-character Google App Password |
| `GEMINI_API_KEY` | `AIzaSy...` | Your Google Gemini API Key |
| `LLM_PROVIDER` | `gemini` | `gemini`, `openai`, or `fallback` |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` | Comma-separated list of allowed frontend URLs *(Wildcard `*.vercel.app` is pre-configured by default)* |

### Step 4: Verify Backend Health
Once deployed, Render gives you a public URL (e.g. `https://flowshark-api.onrender.com`).
Verify in your browser:
- Health check: `https://flowshark-api.onrender.com/api/health` $\rightarrow$ `{"status":"ok"}`
- Swagger Documentation: `https://flowshark-api.onrender.com/docs`
- Industry Taxonomy: `https://flowshark-api.onrender.com/api/industries`

---

## Part 2: Deploy Frontend to Vercel

### Step 1: Import Project into Vercel
1. Log in to [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New...** $\rightarrow$ **Project**.
3. Select your GitHub repository.

### Step 2: Configure Project Settings in Vercel
In the project configuration screen:

1. **Root Directory**: Click "Edit" and select:
   ```text
   gmail-fastapi-integration/frontend
   ```
2. **Framework Preset**: `Vite` (Vercel automatically detects this).
3. **Build Command**: `npm run build`
4. **Output Directory**: `dist`

### Step 3: Add Environment Variables in Vercel
Expand **Environment Variables** and add:

| Key | Value | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `https://flowshark-api.onrender.com` | The public URL of your Render backend |

*(Do **not** include a trailing slash; e.g. `https://flowshark-api.onrender.com`)*.

### Step 4: Deploy
Click **Deploy**. Vercel will install dependencies, compile TypeScript, run Vite build, and provide a live URL (e.g., `https://flowshark-frontend.vercel.app`).

---

## Part 3: Persistent Database Storage on Render (Optional but Recommended)

By default, Render's Free tier filesystem is ephemeral (resets on restart or redeploy). To persist your email database across redeploys:

### Option A: Render Free PostgreSQL (Zero-maintenance)
1. In Render, click **New +** $\rightarrow$ **PostgreSQL Database**.
2. Name it `flowshark-db` (Free tier).
3. Copy the **Internal Database URL** (e.g., `postgres://user:pass@dpg-xxx/flowshark_db`).
4. In your `flowshark-api` Web Service Environment variables, add:
   ```text
   DATABASE_URL = postgres://user:pass@dpg-xxx/flowshark_db
   ```
5. FlowShark automatically normalizes `postgres://` to `postgresql://` and creates all tables on first startup!

### Option B: Render Persistent Disk (For SQLite)
If you prefer keeping SQLite:
1. On your Render Web Service settings (Paid Starter plan), go to **Disks** $\rightarrow$ **Add Disk**.
2. Mount Path: `/var/data`
3. Set Environment Variable:
   ```text
   DATABASE_URL = sqlite:////var/data/flowshark.db
   ```

---

## Verification & Troubleshooting Checklist

- [ ] **CORS Errors**: The backend automatically supports `https://*.vercel.app`. If using a custom domain (e.g. `https://app.flowshark.io`), add it to `ALLOWED_ORIGINS` on Render.
- [ ] **Gmail Authentication**: Ensure 2-Step Verification is enabled on your Google account and use an **App Password**, not your normal login password.
- [ ] **Instant Syncing**: The background worker starts automatically on boot when `BACKGROUND_SYNC_ENABLED=true`. Check logs in Render Dashboard to see live sync progress.
