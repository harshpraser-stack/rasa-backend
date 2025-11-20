#!/bin/bash
set -euo pipefail

# Default PORT if not provided (useable for local testing)
: "${PORT:=5005}"

# Start action server in background on port 5055
echo "Starting action server on port 5055..."
rasa run actions --port 5055 &

# Wait a second for actions to spin up (optional)
sleep 1

# Start Rasa server bound to $PORT and enable API
echo "Starting Rasa server on port ${PORT}..."
# Ensure Rasa loads models from the models/ directory you pushed
rasa run --enable-api --cors "*" --model models --port "$PORT"
