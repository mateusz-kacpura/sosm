"""SOSM Standalone Launcher — entry point for the .exe.

Double-click to start the SOSM panel. Opens browser automatically.
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


def main():
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
