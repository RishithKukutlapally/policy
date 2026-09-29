#!/bin/bash
set -euo pipefail

echo "=== Bootstrapping dev environment ==="

# Backend dependencies
cd backend && uv sync && cd ..

# Frontend dependencies
cd frontend && npm ci && cd ..

# Environment
if [ -f ".env.example" ] && [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your API keys"
fi

# Local dev servers (verification mode: local)
(cd backend && uv run uvicorn src.main:app --port 8000) &
(cd frontend && npm run dev -- --port 3000) &

# Health checks
echo "Waiting for services..."
for i in 1 2 3 4 5; do curl -sf http://localhost:8000/health && break || sleep 2; done
for i in 1 2 3 4 5; do curl -sf http://localhost:3000 > /dev/null && break || sleep 2; done

echo "=== Environment ready ==="
