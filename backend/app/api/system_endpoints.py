import asyncio
import json
import logging
import os
import platform
import signal
import subprocess
import time
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
    try:
        conn = celery_app.connection()
        conn.connect()
        conn.close()
        return True
    except Exception:
        return False


def _check_celery_worker(celery_app) -> dict | None:
    try:
        inspector = celery_app.control.inspect(timeout=3.0)
        return inspector.ping()
    except Exception:
        return None


@router.get("/status")
async def system_status():
    """Health check for all services."""
    results = {}

    # DB
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_type = "SQLite" if settings.STANDALONE else "PostgreSQL"
        results["database"] = {"status": "ok", "detail": f"{db_type} — polaczenie aktywne"}
    except Exception as e:
        results["database"] = {"status": "error", "detail": str(e)}

    if settings.STANDALONE:
        from app.task_runner import get_active_task_count
        results["task_runner"] = {
            "status": "ok",
            "detail": f"Aktywne zadania: {get_active_task_count()}",
        }
    else:
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
    try:
        client = _get_donut_client()
        return await client.list_profiles()
    except DonutBrowserError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Donut Browser niedostepny: {e}")


@router.post("/donut/profiles/{profile_id}/run")
async def run_donut_profile(profile_id: str):
    try:
        client = _get_donut_client()
        return await client.start_profile_immediate(profile_id)
    except DonutBrowserError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Donut Browser niedostepny: {e}")


@router.post("/donut/profiles/{profile_id}/kill")
async def kill_donut_profile(profile_id: str):
    try:
        client = _get_donut_client()
        await client.stop_profile(profile_id)
        return {"detail": "Profil zatrzymany"}
    except DonutBrowserError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Donut Browser niedostepny: {e}")


# --- Host agent endpoints (standalone: merged into main API) ---

def _donut_binary_path() -> str:
    # Allow explicit override via env var
    custom = os.environ.get("DONUT_BINARY_PATH")
    if custom and os.path.isfile(custom):
        return custom

    if platform.system() == "Windows":
        candidates = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'donut-browser', 'Donut.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'donutbrowser', 'DonutBrowser.exe'),
        ]
    else:
        candidates = [
            "/usr/bin/donutbrowser",
            "/usr/local/bin/donutbrowser",
            os.path.expanduser("~/donutbrowser/donutbrowser"),
            os.path.expanduser("~/.local/bin/donutbrowser"),
        ]
        # Search for AppImage or extracted archives in common locations
        for search_dir in [os.path.expanduser("~"), "/opt"]:
            try:
                for entry in os.scandir(search_dir):
                    if entry.is_dir() and "donut" in entry.name.lower():
                        for name in ("donutbrowser", "DonutBrowser", "donut-browser"):
                            p = os.path.join(entry.path, name)
                            if os.path.isfile(p):
                                candidates.append(p)
            except (PermissionError, OSError):
                pass

    for path in candidates:
        if os.path.isfile(path):
            return path
    # Fallback to first candidate (will produce clear error message)
    return candidates[0] if candidates else "donutbrowser"


def _daemon_state_path() -> str:
    if platform.system() == "Windows":
        candidates = [
            os.path.join(os.environ.get('APPDATA', ''), 'donutbrowser', 'daemon-state.json'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'donutbrowser', 'daemon-state.json'),
        ]
    else:
        xdg = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        candidates = [
            os.path.join(xdg, 'donutbrowser', 'daemon-state.json'),
            os.path.expanduser('~/.donutbrowser/daemon-state.json'),
            os.path.expanduser('~/.config/donutbrowser/daemon-state.json'),
        ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    # Return default (first candidate)
    return candidates[0]


def _is_pid_alive(pid: int) -> bool:
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _get_daemon_pid() -> int | None:
    try:
        with open(_daemon_state_path()) as f:
            data = json.load(f)
        pid = data.get("daemon_pid")
        if pid and _is_pid_alive(int(pid)):
            return int(pid)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass
    return None


@router.get("/host/status")
async def host_status():
    daemon_pid = _get_daemon_pid()
    donut_api_ok = False
    if daemon_pid:
        try:
            client = _get_donut_client()
            donut_api_ok = await client.check_health()
        except Exception:
            pass

    result = {
        "donut_daemon": {
            "running": daemon_pid is not None,
            "pid": daemon_pid,
            "api_available": donut_api_ok,
        },
    }

    if settings.STANDALONE:
        from app.task_runner import get_active_task_count
        result["task_runner"] = {
            "running": True,
            "active_tasks": get_active_task_count(),
        }

    return result


@router.post("/host/donut/start")
async def start_donut():
    daemon_pid = _get_daemon_pid()
    if daemon_pid:
        try:
            client = _get_donut_client()
            if await client.check_health():
                return {"status": "already_running", "pid": daemon_pid, "api_available": True}
        except Exception:
            pass

    gui_binary = _donut_binary_path()
    if not os.path.isfile(gui_binary):
        return {"status": "error", "detail": f"Nie znaleziono {gui_binary}"}

    try:
        if platform.system() == "Windows":
            subprocess.Popen(
                [gui_binary],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            subprocess.Popen(
                [gui_binary],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        for _ in range(15):
            await asyncio.sleep(2)
            try:
                client = _get_donut_client()
                if await client.check_health():
                    return {"status": "started", "pid": _get_daemon_pid(), "api_available": True}
            except Exception:
                continue

        return {"status": "started", "pid": _get_daemon_pid(), "api_available": False,
                "detail": "GUI uruchomiony, ale API nie odpowiada."}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/host/donut/stop")
async def stop_donut():
    daemon_pid = _get_daemon_pid()
    if not daemon_pid:
        return {"status": "not_running"}

    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", str(daemon_pid), "/F"],
                           capture_output=True, timeout=5)
        else:
            os.kill(daemon_pid, signal.SIGTERM)
            time.sleep(1)
            if _is_pid_alive(daemon_pid):
                os.kill(daemon_pid, signal.SIGKILL)
        return {"status": "stopped"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
