#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DAEMON_STATE="$HOME/.local/share/donutbrowser/daemon-state.json"
DONUT_DAEMON="/usr/bin/donut-daemon"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
WORKER_LOG="$PROJECT_DIR/celery-worker.log"
AGENT_LOG="$PROJECT_DIR/host-agent.log"

echo -e "${YELLOW}=== SOSM Panel - Uruchamianie systemu ===${NC}"
echo ""

# 1. Donut Browser daemon
echo -n "[1/5] Donut Browser daemon... "
DAEMON_RUNNING=false
if [ -f "$DAEMON_STATE" ]; then
    DAEMON_PID=$(python3 -c "import json; print(json.load(open('$DAEMON_STATE')).get('daemon_pid', ''))" 2>/dev/null || echo "")
    if [ -n "$DAEMON_PID" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
        DAEMON_RUNNING=true
    fi
fi

if [ "$DAEMON_RUNNING" = true ]; then
    echo -e "${GREEN}juz uruchomiony (PID: $DAEMON_PID)${NC}"
else
    if [ -x "$DONUT_DAEMON" ]; then
        nohup "$DONUT_DAEMON" run > /dev/null 2>&1 &
        sleep 3
        echo -e "${GREEN}uruchomiony${NC}"
    else
        echo -e "${RED}nie znaleziono $DONUT_DAEMON${NC}"
    fi
fi

# 2. Docker Compose
echo -n "[2/5] Docker Compose... "
cd "$PROJECT_DIR"
docker compose up -d --quiet-pull 2>/dev/null
echo -e "${GREEN}uruchomiony${NC}"

# 3. API health check
echo -n "[3/5] Czekanie na API... "
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8010/health > /dev/null 2>&1; then
        echo -e "${GREEN}gotowe (${WAITED}s)${NC}"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done
if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}timeout po ${MAX_WAIT}s${NC}"
fi

# 4. Celery worker
echo -n "[4/5] Celery worker... "
if pgrep -f "celery.*app.worker.celery_app.*worker" > /dev/null 2>&1; then
    echo -e "${GREEN}juz uruchomiony${NC}"
else
    set -a
    source "$BACKEND_DIR/.env"
    set +a
    export POSTGRES_HOST=localhost
    export REDIS_HOST=localhost

    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/celery" -A app.worker.celery_app worker \
        --loglevel=info --concurrency=10 \
        > "$WORKER_LOG" 2>&1 &
    sleep 2

    if pgrep -f "celery.*app.worker.celery_app.*worker" > /dev/null 2>&1; then
        echo -e "${GREEN}uruchomiony${NC}"
    else
        echo -e "${RED}blad uruchomienia (sprawdz $WORKER_LOG)${NC}"
    fi
fi

# 5. Host Agent
echo -n "[5/5] Host Agent (port 8020)... "
if curl -sf http://localhost:8020/status > /dev/null 2>&1; then
    echo -e "${GREEN}juz uruchomiony${NC}"
else
    cd "$PROJECT_DIR"
    nohup "$VENV_DIR/bin/python" host_agent.py \
        > "$AGENT_LOG" 2>&1 &
    sleep 2

    if curl -sf http://localhost:8020/status > /dev/null 2>&1; then
        echo -e "${GREEN}uruchomiony${NC}"
    else
        echo -e "${RED}blad uruchomienia (sprawdz $AGENT_LOG)${NC}"
    fi
fi

# Summary
echo ""
echo -e "${YELLOW}=== Status ===${NC}"
echo -e "  Frontend:      ${GREEN}http://localhost:3010${NC}"
echo -e "  API:           ${GREEN}http://localhost:8010${NC}"
echo -e "  Host Agent:    ${GREEN}http://localhost:8020${NC}"
echo -e "  Donut Browser: ${GREEN}http://127.0.0.1:10108${NC}"
echo -e "  System panel:  ${GREEN}http://localhost:3010/system${NC}"
echo ""

# Open browser
if command -v xdg-open &> /dev/null; then
    read -p "Otworzyc panel w przegladarce? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        xdg-open "http://localhost:3010/system" &
    fi
fi
