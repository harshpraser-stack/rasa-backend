#!/usr/bin/env bash
set -euo pipefail

# Render will set $PORT. Default to 5005 for local runs.
PORT="${PORT:-${1:-5005}}"
MODEL_DIR="${MODEL_DIR:-models}"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

# Action server settings
ACTION_PORT=5055
ACTION_HEALTH_URL="http://127.0.0.1:${ACTION_PORT}/health"
WAIT_TIMEOUT=30
WAIT_INTERVAL=1

# Start action server (rasa-sdk). Note: do NOT try to pass --host (unsupported).
log "Starting action server on port ${ACTION_PORT}..."
rasa run actions --port "${ACTION_PORT}" --debug &
ACTION_PID=$!

# Wait for action server to become healthy
log "Waiting up to ${WAIT_TIMEOUT}s for action server at ${ACTION_HEALTH_URL} ..."
SECONDS_WAITED=0
while true; do
  if curl -sSf "${ACTION_HEALTH_URL}" > /dev/null 2>&1; then
    log "Action server is healthy."
    break
  fi

  if [ "${SECONDS_WAITED}" -ge "${WAIT_TIMEOUT}" ]; then
    log "Timed out waiting for action server. Check action server logs for errors."
    kill "${ACTION_PID}" 2>/dev/null || true
    exit 1
  fi

  sleep "${WAIT_INTERVAL}"
  SECONDS_WAITED=$((SECONDS_WAITED + WAIT_INTERVAL))
done

# Start the Rasa server (main process)
log "Starting Rasa on 0.0.0.0:${PORT} (models: ${MODEL_DIR})..."
rasa run --enable-api --cors "*" --model "${MODEL_DIR}" --port "${PORT}" &
RASA_PID=$!

# When this script receives SIGTERM/SIGINT, forward to children
term_handler() {
  log "Shutting down (forwarding signals)..."
  kill -TERM "${RASA_PID}" 2>/dev/null || true
  kill -TERM "${ACTION_PID}" 2>/dev/null || true
  wait "${RASA_PID}" 2>/dev/null || true
  wait "${ACTION_PID}" 2>/dev/null || true
  exit 0
}
trap term_handler SIGINT SIGTERM

# Wait for main Rasa process
wait "${RASA_PID}"

# If Rasa exited, make sure action server is cleaned up
log "Rasa exited, shutting down action server (pid ${ACTION_PID})..."
kill "${ACTION_PID}" 2>/dev/null || true
wait "${ACTION_PID}" 2>/dev/null || true
