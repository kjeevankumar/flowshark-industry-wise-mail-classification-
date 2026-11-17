# FlowShark AI — Email Intelligence & Lead Management System

A production-ready B2B Email Intelligence and Lead Management application built with **Python FastAPI**, **Gmail IMAP/SMTP integration**, **SQLAlchemy + SQLite**, **NLP text preprocessing**, **Hybrid AI Classification** (Rules + NLP + LLMs), and a modern **React + Vite + Tailwind CSS** frontend dashboard.

---

## Architecture Overview

```
                                  ┌───────────────────────────────┐
                                  │      Gmail Mailbox Server     │
                                  │   (imap.gmail.com:993 - SSL)  │
                                  └───────────────┬───────────────┘
                                                  │
                                                  │ Non-destructive BODY.PEEK[]
                                                  │ UIDVALIDITY & UID tracking
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Backend Service (Port 8001 / 8000)                                                      │
│                                                                                                 │
│  ┌───────────────────────┐      ┌─────────────────────────┐      ┌───────────────────────────┐  │
│  │   IMAP Ingestion      │ ───► │    NLP Preprocessor     │ ───► │     Hybrid Classifier     │  │
│  │   - Read-only INBOX   │      │    - HTML cleaning      │      │     - Rule Signal Engine  │  │
│  │   - Deduplication     │      │    - Quoted text sep    │      │     - Negation Lookbehind │  │
│  │   - Thread header RFC │      │    - Promo noise filter │      │     - LLM Semantic (Opt)  │  │
│  └───────────────────────┘      └─────────────────────────┘      └─────────────┬─────────────┘  │
│                                                                                │                │
│                                 ┌─────────────────────────┐                    ▼                │
│                                 │   SQLite / PostgreSQL   │ ◄──────────────────┘                │
│                                 │   - emails              │                                     │
│                                 │   - conversations       │                                     │
│                                 │   - classifications     │                                     │
│                                 │   - audit_history       │                                     │
│                                 └────────────┬────────────┘                                     │
│                                              │                                                  │
│                                              ▼                                                  │
│                                 ┌─────────────────────────┐                                     │
│                                 │     REST API Routes     │                                     │
│                                 │     /api/dashboard/*    │                                     │
│                                 │     /api/emails/*       │                                     │
│                                 │     /api/classification │                                     │
│                                 └────────────┬────────────┘                                     │
└──────────────────────────────────────────────┼──────────────────────────────────────────────────┘
                                               │
                                               │ JSON REST API / WebSockets
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FlowShark React Dashboard (React 18 + Vite + Tailwind CSS + Lucide Icons)                       │
│                                                                                                 │
│  - Pipeline Analytics: Real-time counts for New Leads, Negotiations, Follow-ups, POs, Invoices  │
│  - Email Ingestion Stream: Search, filter by business intent, view full MIME & HTML headers     │
│  - Conversation Detail: Thread history, key signals detected, suggested next actions            │
│  - Human Review & Audit: Instant category override with audit history logging                   │
│  - Connection Health: Live IMAP SSL and SMTP STARTTLS diagnostic gauges                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Classification Taxonomy

FlowShark classifies incoming communications across three independent, orthogonal dimensions:

| Dimension | Categories |
|---|---|
| **Relationship** | `new_contact`, `existing_lead`, `existing_customer`, `unknown` |
| **Intent** | `new_enquiry`, `negotiation`, `follow_up`, `business_clarification`, `purchase_order`, `invoice`, `complaint`, `other` |
| **Lead Stage** | `new`, `qualified`, `proposal_sent`, `negotiation`, `won`, `lost`, `unknown` |

### Signal Detection & Negation Awareness
- The rule engine uses 4-word lookbehind windows to prevent false positives (e.g., *"not interested"*, *"never requesting a quotation"*, *"don't send invoice"* are excluded).
- Quoted replies (`On ... wrote:`) are split from new content.
- Promotional newsletters and spam blasts are automatically identified and categorized as `other` (`requires_human_review=True`).

---

## Benchmark Evaluation Results

Evaluation against the 15 ground-truth benchmark test suite (`app/evaluation/benchmark_dataset.py`):

| Model / Pipeline | Accuracy | Macro F1 | Human Review Rate |
|---|---|---|---|
| **Pure Rule-Based Engine** | 93.3% | 0.912 | 20.0% |
| **Hybrid NLP + Rule + Fallback** | **100.0%** | **1.000** | 13.3% |

---

## Quick Start Guide

### 1. Prerequisites
- Python 3.12+ (tested on Python 3.14.2)
- Node.js 18+ and npm

### 2. Backend Setup
```bash
cd gmail-fastapi-integration

# Install Python requirements
pip install -r requirements.txt

# Configure environment credentials
cp .env.example .env
# Edit .env with your GMAIL_ADDRESS and 16-character GMAIL_APP_PASSWORD
# Optional settings:
# SYNC_INTERVAL_SECONDS=30 (background poll interval in seconds)
# BACKGROUND_SYNC_ENABLED=true (automated background worker)
```

### 3. Run Automated Tests
```bash
pytest -v
# Output: 45 passed in 0.92s
```

### 4. Build & Run Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. Launch Application
```bash
# Start FastAPI backend (serves both API and built React Dashboard UI):
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Access the application in your browser:
- **FlowShark Dashboard**: [http://127.0.0.1:8001/](http://127.0.0.1:8001/)
- **Swagger Interactive API Documentation**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
- **ReDoc API Documentation**: [http://127.0.0.1:8001/redoc](http://127.0.0.1:8001/redoc)

For frontend development mode with hot reloading:
```bash
cd frontend
npm run dev
# Vite runs at http://localhost:5173 and proxies /api to http://127.0.0.1:8001
```

---

## REST API Reference

### Health & Connectivity
- `GET /api/health`: Health status and service timestamp.
- `GET /api/email/config-status`: Check Gmail configuration without leaking secrets.
- `GET /api/email/test-imap`: Test SSL connection to `imap.gmail.com:993`, check UIDVALIDITY and total inbox count.
- `GET /api/email/test-smtp`: Test STARTTLS auth on `smtp.gmail.com:587` **without** dispatching an email.

### Inbox & Synchronization
- `GET /api/email/sync-status`: Real-time synchronization state, worker status (`running`, `syncing`, `idle`, `error`), last processed UID, and new email counters.
- `GET /api/emails`: Paginated list of ingested emails with classification metadata (supports `category`, `search`, `limit`, `offset` filters).
- `GET /api/emails/{id}`: Detailed email view with full HTML, plain text, headers, and classification history.
- `GET /api/emails/threads/{thread_id}`: All messages belonging to a conversation thread in chronological order.
- `POST /api/emails/sync`: Incremental sync fetching latest batch from Gmail IMAP (`batch_size=50`).

### AI Classification & Human Review
- `POST /api/classification/classify/{email_id}`: Trigger hybrid classification on a specific email.
- `POST /api/classification/classify-batch`: Batch classify all unclassified emails.
- `GET /api/classification/categories`: Taxonomy metadata with labels and color schemes.
- `PATCH /api/classification/{id}/correct`: Record a human correction audit trail.
- `GET /api/classification/metrics`: Accuracy, distribution, and benchmark statistics.

### Dashboard Analytics
- `GET /api/dashboard/summary`: High-level counters for pipeline stages, recent activity, and LLM provider status.

### Outbound Email (Explicit User Invocation Only)
- `POST /api/email/send-test`: Send a test email to verify delivery.
- `POST /api/email/send`: Send a custom plain-text/HTML message.
