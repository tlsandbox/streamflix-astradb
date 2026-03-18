#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "Missing .env file. Copy .env.example to .env and fill Astra credentials first."
  exit 1
fi

set -a
source "$ROOT_DIR/.env"
set +a

BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"

if [[ -z "${VITE_API_BASE_URL:-}" ]]; then
  export VITE_API_BASE_URL="http://localhost:${BACKEND_PORT}"
fi

if [[ -z "${CORS_ORIGINS:-}" ]]; then
  export CORS_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"
fi

echo "Starting backend on port ${BACKEND_PORT}"
echo "Starting frontend on port ${FRONTEND_PORT}"

python3 -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port "${BACKEND_PORT}" &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$ROOT_DIR/frontend"
npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}"
