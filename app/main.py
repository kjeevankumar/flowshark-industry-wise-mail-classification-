"""FastAPI Application Entry Point for FlowShark AI Email Intelligence & Lead Management.

Integrates:
- Gmail IMAP/SMTP services (tested, read-only, non-destructive).
- Database-backed email inbox synchronization.
- AI & NLP Lead Classification pipelines.
- Dashboard analytics and human correction audit history.
- CORS for React / Vite frontend.
"""

from contextlib import asynccontextmanager
import logging
import os
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db.session import init_db
from app.routes.classification_routes import router as classification_router
from app.routes.dashboard_routes import router as dashboard_router
from app.routes.email_inbox_routes import router as inbox_router
from app.routes.email_routes import router as email_router

# Configure clean structured logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gmail_fastapi.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Initializing FlowShark AI Email Intelligence backend (Env: %s)", settings.APP_ENV)

    # Initialize database tables
    try:
        init_db()
        logger.info("Database initialized successfully at %s", settings.DATABASE_URL)
    except Exception as err:
        logger.error("Database initialization failed: %s", str(err))

    if settings.is_configured:
        logger.info("Gmail account configured: %s", settings.masked_gmail_address)
    else:
        logger.warning("Gmail credentials are not configured. Run /api/email/config-status to check status.")

    if settings.is_llm_configured:
        logger.info("Active LLM Provider: %s (Model: %s)", settings.LLM_PROVIDER, settings.LLM_MODEL)
    else:
        logger.info("No external LLM API key detected. Running on high-performance rule-based + NLP fallback classifier.")

    logger.info("Startup complete. Outbound emails are disabled by default and require explicit REST API triggers.")

    # Start automated background synchronization worker
    from app.services.background_sync import get_sync_worker
    worker = get_sync_worker(settings=settings)
    if settings.BACKGROUND_SYNC_ENABLED:
        await worker.start()

    yield

    # Gracefully stop background worker on shutdown
    if worker.is_running:
        logger.info("Shutting down background sync worker cleanly...")
        await worker.stop()

    logger.info("Shutting down FlowShark AI Email Intelligence backend cleanly.")


# Create FastAPI application
app = FastAPI(
    title="FlowShark AI Email Intelligence & Lead Management API",
    description=(
        "Production-ready B2B Email Intelligence and Lead Classification backend.\n\n"
        "### Key Capabilities\n"
        "- **Gmail IMAP/SMTP Integration**: SSL, UIDVALIDITY, and read-only `BODY.PEEK[]`.\n"
        "- **Inbox Management**: Incremental database synchronization with deduplication.\n"
        "- **Hybrid AI Classifier**: Rule-based signal detection + NLP preprocessing + Configurable LLMs.\n"
        "- **Multi-Dimensional Taxonomies**: Relationship, Intent, and Sales Lead Stage.\n"
        "- **Confidence & Human Review**: Audit trail with manual corrections history.\n"
        "- **FlowShark Dashboard**: Real-time sales pipeline metrics and lead tracking.\n"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware (supports local development, Vercel deployments, and custom production domains)
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
custom_origins = [o.strip() for o in raw_allowed_origins.split(",") if o.strip()]
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
allowed_origins = list(set(default_origins + custom_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(email_router)
app.include_router(inbox_router)
app.include_router(classification_router)
app.include_router(dashboard_router)

# Direct aliases for Section 9 contract endpoints
from app.routes.classification_routes import get_industries_taxonomy, update_industry_classification
from app.routes.dashboard_routes import get_industry_analytics

app.add_api_route("/api/industries", get_industries_taxonomy, methods=["GET"], tags=["Industry Classification"])
app.add_api_route("/api/analytics/industries", get_industry_analytics, methods=["GET"], tags=["Industry Classification"])
app.add_api_route("/api/classifications/{classification_id}/industry", update_industry_classification, methods=["PUT"], tags=["Industry Classification"])

# Mount frontend assets and serve single-page dashboard if built
import os
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
assets_dir = os.path.join(frontend_dist, "assets")

if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

@app.get("/", include_in_schema=False)
async def serve_root():
    index_file = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "FlowShark AI Email Intelligence API is active. Open /docs for API documentation."}


# Global fallback error handler to prevent internal tracebacks or secrets from leaking
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception processing request %s %s: %s", request.method, request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please check application logs for details.",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
