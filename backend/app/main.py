import os
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core import security
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

# Auth middleware — protects /api/ when password is set
class AuthMiddleware(BaseHTTPMiddleware):
    OPEN_PATHS = frozenset({
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/set-password",
        "/api/auth/logout",
        "/health",
    })

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Allow preflight, open paths, and non-API routes (frontend static)
        if request.method == "OPTIONS":
            return await call_next(request)
        if path in self.OPEN_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        # No password configured — allow unrestricted access
        if not security.password_is_set():
            return await call_next(request)

        # Require valid session
        token = request.cookies.get(security.SESSION_COOKIE)
        if token and security.validate_session(token):
            return await call_next(request)

        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})


# Middleware order: AuthMiddleware added first (inner), CORS added second (outer)
# This ensures CORS headers are set even on 401 responses
app.add_middleware(AuthMiddleware)
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
from app.api.auth import router as auth_router
from app.api.workflow_endpoints import router as workflow_router

app.include_router(auth_router, prefix="/api")
app.include_router(api_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")


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

        # Check if password protection is active
        await security.init_password_check()

        # Initialize async task runner
        from app import task_runner
        task_runner.init(max_concurrency=settings.BROWSER_CONCURRENCY)

        # Resume interrupted workflow runs
        from app.workflow.executor import WorkflowExecutor
        await WorkflowExecutor().resume_interrupted_runs()

        # Start periodic campaign checker (replaces Celery Beat)
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.core.scheduler import check_active_campaigns, check_scheduled_workflows

        scheduler = AsyncIOScheduler()
        scheduler.add_job(check_active_campaigns, 'interval', seconds=60, id='campaign_checker')
        scheduler.add_job(check_scheduled_workflows, 'interval', seconds=60, id='workflow_scheduler')
        scheduler.start()
        logger.info("APScheduler started (campaign + workflow checkers every 60s)")

        # Auto-start Donut Browser daemon if not running
        try:
            from app.bot.donut_client import DonutClient
            client = DonutClient(settings.DONUT_API_URL, settings.DONUT_API_TOKEN)
            if await client.check_health():
                logger.info("Donut Browser API connected at %s", settings.DONUT_API_URL)
            else:
                logger.info("Donut Browser not running — attempting auto-start...")
                from app.api.system_endpoints import start_donut
                result = await start_donut()
                if result.get("api_available"):
                    logger.info("Donut Browser auto-started (pid %s)", result.get("pid"))
                else:
                    logger.warning("Donut Browser started but API not responding: %s",
                                   result.get("detail", result.get("status")))
        except Exception as e:
            logger.warning("Donut Browser startup check failed: %s", e)


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

        @app.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
        async def serve_frontend(request: Request, path: str = ""):
            """Serve Next.js static export files with .html fallback."""
            # Never intercept API or health routes — let FastAPI routers handle them
            if path.startswith("api/") or path == "health":
                return JSONResponse(status_code=404, content={"detail": "Not found"})

            # Only serve frontend files for GET/HEAD requests
            if request.method not in ("GET", "HEAD"):
                return JSONResponse(status_code=405, content={"detail": "Method not allowed"})

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
