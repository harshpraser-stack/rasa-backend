#!/usr/bin/env bash
set -euo pipefail

# Allow override of PORT. Render sets $PORT automatically.
PORT="${PORT:-${1:-5005}}"
MODEL_DIR="${MODEL_DIR:-models}"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

# Action server binds only to localhost
ACTION_HOST="${ACTION_HOST:-127.0.0.1}"
ACTION_PORT="${ACTION_PORT:-5055}"
ACTION_HEALTH_URL="http://${ACTION_HOST}:${ACTION_PORT}/health"

WAIT_TIMEOUT="${WAIT_TIMEOUT:-30}"
WAIT_INTERVAL="${WAIT_INTERVAL:-1}"

# Start action server (rasa-sdk) bound to localhost using the python -m entrypoint
log "Starting action server on ${ACTION_HOST}:${ACTION_PORT}..."
# Use python -m rasa_sdk.endpoint so --host is accepted
python -m rasa_sdk.endpoint --host "${ACTION_HOST}" --port "${ACTION_PORT}" &
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
    log "Timed out waiting for action server. Check action server logs for errors."
    kill "${ACTION_PID}" || true
    exit 1
  fi
  sleep "${WAIT_INTERVAL}"
  SECONDS_WAITED=$((SECONDS_WAITED + WAIT_INTERVAL))
done

# Start Rasa (publicly exposed process). Bind to 0.0.0.0:$PORT (Render provides $PORT)
log "Starting Rasa on 0.0.0.0:${PORT} (models: ${MODEL_DIR})..."
# run in background but we will wait on RASA_PID so the script stays alive
rasa run --enable-api --cors "*" --model "${MODEL_DIR}" --port "${PORT}" &
RASA_PID=$!

# Forward SIGTERM/SIGINT to children and wait
term_handler() {
  log "Shutting down (forwarding signals)..."
  kill -TERM "${RASA_PID}" 2>/dev/null || true
  kill -TERM "${ACTION_PID}" 2>/dev/null || true
  wait "${RASA_PID}" 2>/dev/null || true
  wait "${ACTION_PID}" 2>/dev/null || true
  exit 0
}
trap term_handler SIGINT SIGTERM

# Wait for the Rasa process (main)
wait "${RASA_PID}"

# Cleanup - if rasa exits, stop action server
log "Rasa exited, shutting down action server (pid ${ACTION_PID})..."
kill "${ACTION_PID}" 2>/dev/null || true
wait "${ACTION_PID}" 2>/dev/null || true
