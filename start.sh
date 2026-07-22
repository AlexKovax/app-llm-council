#!/bin/bash

# LLM Council - Start script
# On first run, this script bootstraps the environment:
#   - installs `uv` (Python package manager) if missing
#   - syncs Python dependencies via `uv sync`
#   - installs frontend npm dependencies if node_modules is missing
# Subsequent runs skip the bootstrap steps and just launch the servers.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "Starting LLM Council..."
echo ""

# ----------------------------------------------------------------------------
# Bootstrap: uv (Python package manager)
# ----------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Installing uv (Python package manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Make uv available in the current shell
  UV_BIN_DIRS="$HOME/.local/bin $HOME/.cargo/bin"
  for dir in $UV_BIN_DIRS; do
    if [ -x "$dir/uv" ]; then
      export PATH="$dir:$PATH"
      break
    fi
  done

  if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv installation failed. Please install uv manually:" >&2
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
  fi
  echo "✓ uv installed: $(uv --version)"
else
  echo "✓ uv found: $(uv --version)"
fi

# ----------------------------------------------------------------------------
# Bootstrap: Python dependencies
# ----------------------------------------------------------------------------
echo "Syncing Python dependencies..."
uv sync
echo ""

# ----------------------------------------------------------------------------
# Bootstrap: frontend dependencies
# ----------------------------------------------------------------------------
if [ ! -d "frontend/node_modules" ]; then
  echo "frontend/node_modules not found. Installing npm dependencies..."
  if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found. Please install Node.js (LTS) first:" >&2
    echo "  https://nodejs.org/" >&2
    exit 1
  fi
  echo "  npm: $(npm --version)  node: $(node --version)"
  (cd frontend && npm install)
  echo "✓ Frontend dependencies installed"
else
  echo "✓ Frontend dependencies found"
fi
echo ""

# ----------------------------------------------------------------------------
# Bootstrap: .env file (create with placeholder if missing)
# ----------------------------------------------------------------------------
if [ ! -f ".env" ]; then
  echo "Creating .env file with placeholder..."
  cat > .env <<'EOF'
OPENROUTER_API_KEY=XXX
EOF
  echo ""
  echo "================================================================"
  echo "  ACTION REQUIRED"
  echo "  A .env file has been created with a placeholder key."
  echo "  Edit it and replace XXX with your real OpenRouter API key"
  echo "  (sk-or-v1-...), then re-run this script:"
  echo ""
  echo "    \$EDITOR .env"
  echo "    ./start.sh"
  echo "================================================================"
  echo ""
  exit 0
fi

# Warn if .env still contains the placeholder
if grep -q "^OPENROUTER_API_KEY=XXX$" .env 2>/dev/null; then
  echo "================================================================"
  echo "  ACTION REQUIRED"
  echo "  .env still contains the placeholder key (XXX)."
  echo "  Edit it and replace XXX with your real OpenRouter API key"
  echo "  (sk-or-v1-...):"
  echo ""
  echo "    \$EDITOR .env"
  echo "================================================================"
  echo ""
fi

# ----------------------------------------------------------------------------
# Launch servers
# ----------------------------------------------------------------------------
echo "Starting backend on http://localhost:8001..."
uv run python -m backend.main &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

echo "Starting frontend on http://localhost:5173..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "✓ LLM Council is running!"
echo "  Backend:  http://localhost:8001  (pid $BACKEND_PID)"
echo "  Frontend: http://localhost:5173  (pid $FRONTEND_PID)"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
