#!/usr/bin/env bash
set -euo pipefail

# Allow override of PORT. Render sets $PORT automatically.
# Usage: ./start.sh [PORT]
PORT="${PORT:-${1:-5005}}"

# Where Rasa models live
MODEL_DIR="${MODEL_DIR:-models}"

# Logging helper
log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

# Timeout settings for waiting for action server
ACTION_HOST="${ACTION_HOST:-127.0.0.1}"
ACTION_PORT="${ACTION_PORT:-5055}"
ACTION_HEALTH_URL="http://${ACTION_HOST}:${ACTION_PORT}/health"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-30}"   # seconds
WAIT_INTERVAL="${WAIT_INTERVAL:-1}"  # seconds between checks

# Start action server (rasa-sdk) in background
# Start action server (rasa-sdk) in background and bind to localhost so Render doesn't expose it
log "Starting action server on ${ACTION_HOST}:${ACTION_PORT}..."
rasa run actions --host "${ACTION_HOST}" --port "${ACTION_PORT}" --debug &
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
    # Keep running so logs show the action server output, but fail early so render will mark failure
    kill "${ACTION_PID}" || true
    exit 1
  fi
  sleep "${WAIT_INTERVAL}"
  SECONDS_WAITED=$((SECONDS_WAITED + WAIT_INTERVAL))
done

# Start rasa server in foreground (main process)
log "Starting Rasa on 0.0.0.0:${PORT} (models: ${MODEL_DIR})..."
# Use --model <dir> so it loads all models from models/
rasa run --enable-api --cors "*" --model "${MODEL_DIR}" --port "${PORT}" &

RASA_PID=$!

# When this script gets SIGTERM/SIGINT, forward to children
term_handler() {
  log "Shutting down (forwarding signals)..."
  kill -TERM "${RASA_PID}" 2>/dev/null || true
  kill -TERM "${ACTION_PID}" 2>/dev/null || true
  wait "${RASA_PID}" 2>/dev/null || true
  wait "${ACTION_PID}" 2>/dev/null || true
  exit 0
}
trap term_handler SIGINT SIGTERM

# Wait for processes
wait "${RASA_PID}"
log "Rasa exited, shutting down action server (pid ${ACTION_PID})..."
kill "${ACTION_PID}" 2>/dev/null || true
wait "${ACTION_PID}" 2>/dev/null || true
