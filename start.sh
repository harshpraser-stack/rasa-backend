#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-${1:-5005}}"
MODEL_DIR="${MODEL_DIR:-models}"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

ACTION_PORT=5055
ACTION_HEALTH_URL="http://127.0.0.1:${ACTION_PORT}/health"
WAIT_TIMEOUT=30
WAIT_INTERVAL=1

# Start action server
log "Starting action server on ${ACTION_PORT}..."
rasa run actions --port ${ACTION_PORT} &
ACTION_PID=$!

log "Waiting up to ${WAIT_TIMEOUT}s for action server ..."
SECONDS_WAITED=0
while true; do
    if curl -sSf "${ACTION_HEALTH_URL}" >/dev/null 2>&1; then
        log "Action server is healthy."
        break
    fi

    if [ ${SECONDS_WAITED} -ge ${WAIT_TIMEOUT} ]; then
        log "Timed out waiting for action server."
        kill ${ACTION_PID} || true
        exit 1
    fi

    sleep ${WAIT_INTERVAL}
    SECONDS_WAITED=$((SECONDS_WAITED + WAIT_INTERVAL))
done

# Start Rasa server
log "Starting Rasa on port ${PORT} ..."
rasa run --enable-api --cors "*" --model "${MODEL_DIR}" --port "${PORT}" &
RASA_PID=$!

# Shutdown handling
term_handler() {
    log "Shutting down..."
    kill -TERM "${RASA_PID}" 2>/dev/null || true
    kill -TERM "${ACTION_PID}" 2>/dev/null || true
    exit 0
}
trap term_handler SIGINT SIGTERM

wait "${RASA_PID}"
kill "${ACTION_PID}" || true
wait "${ACTION_PID}" || true
