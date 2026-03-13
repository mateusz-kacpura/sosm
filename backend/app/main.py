import os
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3010",
        "http://localhost:8010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.endpoints import router as api_router
from app.api.system_endpoints import router as system_router

app.include_router(api_router, prefix="/api")
app.include_router(system_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME}...")

    if settings.STANDALONE:
        # Create data directory
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.DATA_DIR, "screenshots"), exist_ok=True)

        # Initialize SQLite database
        from app.core.database import init_db
        await init_db()
        logger.info("SQLite database initialized at %s", settings.DATA_DIR)

        # Initialize async task runner
        from app import task_runner
        task_runner.init(max_concurrency=settings.BROWSER_CONCURRENCY)

        # Start periodic campaign checker (replaces Celery Beat)
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.core.scheduler import check_active_campaigns

        scheduler = AsyncIOScheduler()
        scheduler.add_job(check_active_campaigns, 'interval', seconds=60, id='campaign_checker')
        scheduler.start()
        logger.info("APScheduler started (campaign checker every 60s)")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}


# Serve static frontend (standalone mode)
# Next.js static export uses {route}.html pattern (e.g. /campaigns → campaigns.html)
if settings.STANDALONE:
    if getattr(sys, 'frozen', False):
        _frontend_dir = os.path.join(sys._MEIPASS, 'frontend_dist')
    else:
        _frontend_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'out')

    if os.path.isdir(_frontend_dir):
        # Mount _next for static assets (JS, CSS)
        _next_dir = os.path.join(_frontend_dir, '_next')
        if os.path.isdir(_next_dir):
            app.mount("/_next", StaticFiles(directory=_next_dir), name="next_assets")

        @app.api_route("/{path:path}", methods=["GET", "HEAD"])
        async def serve_frontend(request: Request, path: str = ""):
            """Serve Next.js static export files with .html fallback."""
            # Try exact file first (e.g. favicon.ico, file.svg)
            file_path = os.path.join(_frontend_dir, path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)

            # Try {path}.html (Next.js pattern: /campaigns → campaigns.html)
            html_path = os.path.join(_frontend_dir, f"{path}.html")
            if os.path.isfile(html_path):
                return FileResponse(html_path, media_type="text/html")

            # Try {path}/index.html
            index_path = os.path.join(_frontend_dir, path, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path, media_type="text/html")

            # Fallback to index.html (SPA client-side routing)
            fallback = os.path.join(_frontend_dir, "index.html")
            if os.path.isfile(fallback):
                return FileResponse(fallback, media_type="text/html")

            return FileResponse(os.path.join(_frontend_dir, "404.html"), status_code=404, media_type="text/html")

        logger.info("Serving static frontend from %s", _frontend_dir)
    else:
        logger.warning("Frontend dist directory not found: %s", _frontend_dir)
