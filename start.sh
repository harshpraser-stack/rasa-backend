#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-${1:-5005}}"
MODEL_DIR="${MODEL_DIR:-models}"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

# action server settings
ACTION_PORT=5055
ACTION_HEALTH_URL="http://127.0.0.1:${ACTION_PORT}/health"
WAIT_TIMEOUT=30
WAIT_INTERVAL=1

# Start action server (DO NOT pass --host)
log "Starting action server on port ${ACTION_PORT}..."
rasa run actions --port "${ACTION_PORT}" &
ACTION_PID=$!

# Wait for action server to be healthy
log "Waiting up to ${WAIT_TIMEOUT}s for action server at ${ACTION_HEALTH_URL}..."
SECONDS_WAITED=0
while true; do
  if curl -sSf "${ACTION_HEALTH_URL}" >/dev/null 2>&1; then
    log "Action server is healthy."
    break
  fi
  if [ "${SECONDS_WAITED}" -ge "${WAIT_TIMEOUT}" ]; then
    log "Timed out waiting for action server. Check action server logs."
    kill "${ACTION_PID}" || true
    exit 1
  fi
  sleep "${WAIT_INTERVAL}"
  SECONDS_WAITED=$((SECONDS_WAITED + WAIT_INTERVAL))
done

# Start Rasa server (use --interface to bind to 0.0.0.0)
log "Starting Rasa HTTP server on 0.0.0.0:${PORT} (model dir: ${MODEL_DIR})..."
rasa run --enable-api --cors "*" --model "${MODEL_DIR}" --interface 0.0.0.0 --port "${PORT}" &
RASA_PID=$!

# Forward SIGINT/SIGTERM to children
term_handler() {
  log "Shutting down..."
  kill -TERM "${RASA_PID}" 2>/dev/null || true
  kill -TERM "${ACTION_PID}" 2>/dev/null || true
  wait "${RASA_PID}" 2>/dev/null || true
  wait "${ACTION_PID}" 2>/dev/null || true
  exit 0
}
trap term_handler SIGINT SIGTERM

# Wait for the Rasa server to exit
wait "${RASA_PID}"
log "Rasa exited; stopping action server..."
kill "${ACTION_PID}" 2>/dev/null || true
wait "${ACTION_PID}" 2>/dev/null || true
