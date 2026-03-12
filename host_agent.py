"""SOSM Host Agent — manages host-level processes from the frontend.

Runs natively on the host (NOT in Docker) to start/stop:
- Donut Browser daemon
- Celery worker

Usage:
    ./backend/venv/bin/python host_agent.py
    # or via start.sh (automatic)

Listens on port 8020, CORS enabled for localhost origins.
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [host-agent] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="SOSM Host Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
VENV_DIR = os.path.join(BACKEND_DIR, "venv")
WORKER_LOG = os.path.join(PROJECT_DIR, "celery-worker.log")
DAEMON_STATE = os.path.expanduser("~/.local/share/donutbrowser/daemon-state.json")
DONUT_DAEMON = "/usr/bin/donut-daemon"

# Load Donut Browser API credentials from backend/.env
_DONUT_API_URL = "http://127.0.0.1:10108"
_DONUT_API_TOKEN = ""
_env_file = os.path.join(BACKEND_DIR, ".env")
if os.path.isfile(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("DONUT_API_URL="):
                _DONUT_API_URL = _line.split("=", 1)[1]
            elif _line.startswith("DONUT_API_TOKEN="):
                _DONUT_API_TOKEN = _line.split("=", 1)[1]


def _donut_headers() -> dict:
    return {"Authorization": f"Bearer {_DONUT_API_TOKEN}"}


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _get_daemon_pid() -> int | None:
    try:
        with open(DAEMON_STATE) as f:
            data = json.load(f)
        pid = data.get("daemon_pid")
        if pid and _is_pid_alive(int(pid)):
            return int(pid)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass
    return None


def _get_worker_pids() -> list[int]:
    """Find Celery worker PIDs via pgrep."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "celery.*app.worker.celery_app.*worker"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return [int(p) for p in result.stdout.strip().split("\n") if p]
    except Exception:
        pass
    return []


@app.get("/status")
def status():
    """Check status of host-level processes and Donut Browser API."""
    daemon_pid = _get_daemon_pid()
    worker_pids = _get_worker_pids()

    # Check if Donut Browser API is actually reachable
    donut_api_ok = False
    if daemon_pid:
        try:
            resp = httpx.get(
                f"{_DONUT_API_URL}/v1/profiles",
                headers=_donut_headers(),
                timeout=5.0,
            )
            donut_api_ok = resp.status_code < 500
        except Exception:
            pass

    return {
        "donut_daemon": {
            "running": daemon_pid is not None,
            "pid": daemon_pid,
            "api_available": donut_api_ok,
        },
        "celery_worker": {
            "running": len(worker_pids) > 0,
            "pids": worker_pids,
        },
    }


DONUT_GUI = "/usr/bin/donutbrowser"


@app.post("/donut/start")
def start_donut():
    """Start Donut Browser GUI app (which activates daemon + API)."""
    daemon_pid = _get_daemon_pid()

    # Check if API is already available
    if daemon_pid:
        try:
            resp = httpx.get(
                f"{_DONUT_API_URL}/v1/profiles",
                headers=_donut_headers(),
                timeout=3.0,
            )
            if resp.status_code < 500:
                return {"status": "already_running", "pid": daemon_pid, "api_available": True}
        except Exception:
            pass

    # Start the GUI app (which connects to daemon and activates the API)
    gui_binary = DONUT_GUI if os.path.isfile(DONUT_GUI) else DONUT_DAEMON
    if not os.path.isfile(gui_binary):
        return {"status": "error", "detail": f"Nie znaleziono {gui_binary}"}

    try:
        subprocess.Popen(
            [gui_binary] + (["run"] if gui_binary == DONUT_DAEMON else []),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for API to become available (GUI needs time to connect to daemon)
        for _ in range(15):
            time.sleep(2)
            try:
                resp = httpx.get(
                    f"{_DONUT_API_URL}/v1/profiles",
                    headers=_donut_headers(),
                    timeout=3.0,
                )
                if resp.status_code < 500:
                    daemon_pid = _get_daemon_pid()
                    logger.info("Donut Browser started, API available, daemon PID: %s", daemon_pid)
                    return {"status": "started", "pid": daemon_pid, "api_available": True}
            except Exception:
                continue

        daemon_pid = _get_daemon_pid()
        return {
            "status": "started",
            "pid": daemon_pid,
            "api_available": False,
            "detail": "GUI uruchomiony, ale API nie odpowiada. Wlacz API w ustawieniach Donut Browser.",
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/donut/stop")
def stop_donut():
    """Stop Donut Browser daemon."""
    daemon_pid = _get_daemon_pid()
    if not daemon_pid:
        return {"status": "not_running"}

    try:
        os.kill(daemon_pid, signal.SIGTERM)
        time.sleep(1)
        if _is_pid_alive(daemon_pid):
            os.kill(daemon_pid, signal.SIGKILL)
        logger.info("Donut daemon stopped (PID: %d)", daemon_pid)
        return {"status": "stopped"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/worker/start")
def start_worker():
    """Start Celery worker on the host."""
    if _get_worker_pids():
        return {"status": "already_running", "pids": _get_worker_pids()}

    celery_bin = os.path.join(VENV_DIR, "bin", "celery")
    if not os.path.isfile(celery_bin):
        return {"status": "error", "detail": f"Nie znaleziono {celery_bin}"}

    env = os.environ.copy()
    # Load backend .env
    env_file = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    env[key.strip()] = val.strip()

    env["POSTGRES_HOST"] = "localhost"
    env["REDIS_HOST"] = "localhost"

    try:
        proc = subprocess.Popen(
            [
                celery_bin, "-A", "app.worker.celery_app",
                "worker", "--loglevel=info", "--concurrency=10",
            ],
            cwd=BACKEND_DIR,
            env=env,
            stdout=open(WORKER_LOG, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        time.sleep(2)

        pids = _get_worker_pids()
        if pids:
            logger.info("Celery worker started, PIDs: %s", pids)
            return {"status": "started", "pids": pids}
        else:
            return {"status": "error", "detail": f"Worker nie uruchomil sie (sprawdz {WORKER_LOG})"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/worker/stop")
def stop_worker():
    """Stop Celery worker."""
    pids = _get_worker_pids()
    if not pids:
        return {"status": "not_running"}

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    time.sleep(2)
    remaining = _get_worker_pids()
    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

    logger.info("Celery worker stopped (PIDs: %s)", pids)
    return {"status": "stopped"}


# --- Donut Browser API proxy (host can reach localhost:10108) ---

@app.get("/donut/profiles")
def list_donut_profiles():
    """Proxy: list all Donut Browser profiles."""
    try:
        resp = httpx.get(
            f"{_DONUT_API_URL}/v1/profiles",
            headers=_donut_headers(),
            timeout=10.0,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=resp.text)
        return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Donut Browser API niedostepne")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/donut/profiles/{profile_id}/run")
def run_donut_profile(profile_id: str):
    """Proxy: start a Donut Browser profile."""
    try:
        resp = httpx.post(
            f"{_DONUT_API_URL}/v1/profiles/{profile_id}/run",
            headers=_donut_headers(),
            json={},
            timeout=60.0,
        )
        if resp.status_code == 500:
            # Profile may be already running — kill and retry
            httpx.post(
                f"{_DONUT_API_URL}/v1/profiles/{profile_id}/kill",
                headers=_donut_headers(),
                timeout=10.0,
            )
            time.sleep(2)
            resp = httpx.post(
                f"{_DONUT_API_URL}/v1/profiles/{profile_id}/run",
                headers=_donut_headers(),
                json={},
                timeout=60.0,
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=resp.text)
        return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Donut Browser API niedostepne")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/donut/profiles/{profile_id}/kill")
def kill_donut_profile(profile_id: str):
    """Proxy: stop a Donut Browser profile."""
    try:
        resp = httpx.post(
            f"{_DONUT_API_URL}/v1/profiles/{profile_id}/kill",
            headers=_donut_headers(),
            timeout=10.0,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=resp.text)
        return {"detail": "Profil zatrzymany"}
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Donut Browser API niedostepne")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8020, log_level="info")
