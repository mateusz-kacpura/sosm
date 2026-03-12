import asyncio
import logging
from functools import partial

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.bot.donut_client import DonutClient, DonutBrowserError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


def _get_donut_client() -> DonutClient:
    return DonutClient(settings.DONUT_API_URL, settings.DONUT_API_TOKEN)


def _check_redis(celery_app) -> bool:
    """Sync: ping Redis via Celery broker connection."""
    try:
        conn = celery_app.connection()
        conn.connect()
        conn.close()
        return True
    except Exception:
        return False


def _check_celery_worker(celery_app) -> dict | None:
    """Sync: ping Celery workers via inspect API."""
    try:
        inspector = celery_app.control.inspect(timeout=3.0)
        return inspector.ping()
    except Exception:
        return None


@router.get("/status")
async def system_status():
    """Health check for all services: DB, Redis, Celery Worker, Donut Browser."""
    results = {}

    # DB
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        results["database"] = {"status": "ok", "detail": "Polaczenie aktywne"}
    except Exception as e:
        results["database"] = {"status": "error", "detail": str(e)}

    # Redis
    try:
        from app.worker import celery_app
        loop = asyncio.get_event_loop()
        redis_ok = await loop.run_in_executor(
            None, partial(_check_redis, celery_app)
        )
        if redis_ok:
            results["redis"] = {"status": "ok", "detail": "Ping OK"}
        else:
            results["redis"] = {"status": "error", "detail": "Brak odpowiedzi"}
    except Exception as e:
        results["redis"] = {"status": "error", "detail": str(e)}

    # Celery Worker
    try:
        from app.worker import celery_app
        loop = asyncio.get_event_loop()
        worker_info = await loop.run_in_executor(
            None, partial(_check_celery_worker, celery_app)
        )
        if worker_info:
            results["celery_worker"] = {
                "status": "ok",
                "detail": f"Aktywne workery: {len(worker_info)}",
                "workers": list(worker_info.keys()),
            }
        else:
            results["celery_worker"] = {
                "status": "error",
                "detail": "Brak aktywnych workerow",
            }
    except Exception as e:
        results["celery_worker"] = {"status": "error", "detail": str(e)}

    # Donut Browser
    try:
        client = _get_donut_client()
        healthy = await client.check_health()
        if healthy:
            results["donut_browser"] = {"status": "ok", "detail": "API dostepne"}
        else:
            results["donut_browser"] = {
                "status": "error",
                "detail": "API niedostepne (daemon nie uruchomiony?)",
            }
    except Exception as e:
        results["donut_browser"] = {"status": "error", "detail": str(e)}

    # API is always ok if we got here
    results["api"] = {"status": "ok", "detail": f"v{settings.VERSION}"}

    return results


# --- Donut Browser proxy endpoints ---

@router.get("/donut/profiles")
async def list_donut_profiles():
    """Proxy: list all Donut Browser profiles."""
    try:
        client = _get_donut_client()
        return await client.list_profiles()
    except DonutBrowserError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Donut Browser niedostepny: {e}")


@router.post("/donut/profiles/{profile_id}/run")
async def run_donut_profile(profile_id: str):
    """Proxy: start a Donut Browser profile (no jitter)."""
    try:
        client = _get_donut_client()
        return await client.start_profile_immediate(profile_id)
    except DonutBrowserError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Donut Browser niedostepny: {e}")


@router.post("/donut/profiles/{profile_id}/kill")
async def kill_donut_profile(profile_id: str):
    """Proxy: stop a Donut Browser profile."""
    try:
        client = _get_donut_client()
        await client.stop_profile(profile_id)
        return {"detail": "Profil zatrzymany"}
    except DonutBrowserError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Donut Browser niedostepny: {e}")
