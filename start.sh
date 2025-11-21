#!/usr/bin/env bash
set -euo pipefail

# Allow override of PORT. Render sets $PORT automatically.
PORT="${PORT:-${1:-5005}}"

MODEL_DIR="${MODEL_DIR:-models}"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

ACTION_PORT="${ACTION_PORT:-5055}"
ACTION_HEALTH_URL="http://127.0.0.1:${ACTION_PORT}/health"
WAIT_TIMEOUT=30
WAIT_INTERVAL=1

# Start action server (Rasa SDK)
log "Starting action server on port ${ACTION_PORT}..."
rasa run actions --port "${ACTION_PORT}" --debug &
ACTION_PID=$!

# Wait for action server to become healthy
log "Waiting up to ${WAIT_TIMEOUT}s for action server to respond at ${ACTION_HEALTH_URL}..."
SECONDS_WAITED=0
while true; do
  if curl -sSf "${ACTION_HEALTH_URL}" > /dev/null 2>&1; then
    log "Action server is healthy."
    break
  fi
  if [ "${SECONDS_WAITED}" -ge "${WAIT_TIMEOUT}" ]; then
    log "Timed out waiting for action server. Check logs for issues."
    kill "${ACTION_PID}" || true
    exit 1
  fi
  sleep "${WAIT_INTERVAL}"
  SECONDS_WAITED=$((SECONDS_WAITED + WAIT_INTERVAL))
done

# Start Rasa server
log "Starting Rasa on 0.0.0.0:${PORT} (models: ${MODEL_DIR})..."
rasa run --enable-api --cors "*" --model "${MODEL_DIR}" --port "${PORT}" &
RASA_PID=$!

# Handle shutdown
term_handler() {
  log "Shutting down..."
  kill -TERM "${RASA_PID}" 2>/dev/null || true
  kill -TERM "${ACTION_PID}" 2>/dev/null || true
  wait "${RASA_PID}" || true
  wait "${ACTION_PID}" || true
  exit 0
}
trap term_handler SIGINT SIGTERM

wait "${RASA_PID}"
log "Rasa exited. Shutting down action server..."
kill "${ACTION_PID}" 2>/dev/null || true
wait "${ACTION_PID}" 2>/dev/null || true
