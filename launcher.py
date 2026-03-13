"""SOSM Standalone Launcher — entry point for the .exe.

Double-click to start the SOSM panel. Opens browser automatically.
Donut Browser API token is auto-configured (no manual setup needed).
"""
import os
import sys
import webbrowser
import threading
import logging

# Set standalone mode BEFORE any app imports
os.environ["STANDALONE"] = "true"

# When running as PyInstaller .exe, set working directory to backend
if getattr(sys, 'frozen', False):
    _base = os.path.dirname(sys.executable)
else:
    _base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')

os.chdir(_base)
if _base not in sys.path:
    sys.path.insert(0, _base)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SOSM] %(message)s")
logger = logging.getLogger(__name__)


def open_browser_delayed(url: str, delay: float = 3.0):
    import time
    time.sleep(delay)
    webbrowser.open(url)


def _get_data_dir() -> str:
    """Compute DATA_DIR before settings are loaded."""
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
        else:
            base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        return os.path.join(base, 'SOSM')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'sosm_data')


def _load_env_file(data_dir: str):
    """Load .env from DATA_DIR (for DONUT_BINARY_PATH and other overrides)."""
    env_file = os.path.join(data_dir, ".env")
    if os.path.isfile(env_file):
        logger.info("Loading config from %s", env_file)
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value


def _auto_configure_donut():
    """Auto-detect Donut Browser API token (no manual config needed)."""
    # Skip if user explicitly set the token
    if os.environ.get("DONUT_API_TOKEN"):
        logger.info("Using DONUT_API_TOKEN from environment")
        return

    try:
        from app.bot.donut_auto_config import auto_configure
        token = auto_configure()
        if token:
            os.environ["DONUT_API_TOKEN"] = token
        else:
            logger.warning("Donut Browser not configured — install and start it at least once")
    except Exception as e:
        logger.warning("Donut Browser auto-config failed: %s", e)


def main():
    data_dir = _get_data_dir()
    os.makedirs(data_dir, exist_ok=True)

    # Load optional .env overrides
    _load_env_file(data_dir)

    # Auto-configure Donut Browser API token
    _auto_configure_donut()

    import uvicorn
    from app.core.config import settings

    os.makedirs(settings.DATA_DIR, exist_ok=True)

    host = "127.0.0.1"
    port = 8010
    url = f"http://{host}:{port}"

    logger.info("Starting SOSM Panel at %s", url)
    logger.info("Data directory: %s", settings.DATA_DIR)

    # Open browser after server starts
    threading.Thread(target=open_browser_delayed, args=(url, 3.0), daemon=True).start()

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
