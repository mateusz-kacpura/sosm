#!/bin/bash
# Run SOSM API on the host (not in Docker).
# Camoufox needs GPU access for authentic WebGL rendering.
set -e
cd "$(dirname "$0")/backend"
source venv/bin/activate

# Camoufox requires glxtest for GPU detection. The binary is not
# shipped with the pip package — copy from system Firefox if missing.
CAMOU_DIR="${HOME}/.cache/camoufox"
if [ -d "$CAMOU_DIR" ] && [ ! -f "$CAMOU_DIR/glxtest" ]; then
    if [ -f /usr/lib/firefox/glxtest ]; then
        cp /usr/lib/firefox/glxtest "$CAMOU_DIR/glxtest"
        chmod +x "$CAMOU_DIR/glxtest"
        echo "Copied glxtest from system Firefox to $CAMOU_DIR"
    else
        echo "WARNING: glxtest not found — Camoufox GPU detection will fail."
        echo "Install Firefox (apt install firefox) or copy glxtest manually."
    fi
fi

export STANDALONE=true
export POSTGRES_HOST=localhost
export REDIS_HOST=localhost
# .env is loaded automatically by pydantic-settings
exec uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
