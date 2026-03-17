#!/bin/bash
# Run SOSM API on the host (not in Docker).
# Camoufox needs GPU access for authentic WebGL rendering.
set -e
cd "$(dirname "$0")/backend"
source venv/bin/activate

export STANDALONE=true
export POSTGRES_HOST=localhost
export REDIS_HOST=localhost
# .env is loaded automatically by pydantic-settings
exec uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
