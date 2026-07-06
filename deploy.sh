#!/bin/bash
set -euo pipefail

SERVER="root@llmcouncil.hosakka.com"
APP_DIR="/opt/llm-council"

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}[✓]${NC} $1"; }

log "Syncing code to $SERVER:$APP_DIR ..."
rsync -avz --delete \
  --exclude '.venv/' \
  --exclude 'node_modules/' \
  --exclude '__pycache__/' \
  --exclude '.ruff_cache/' \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.gitignore' \
  --exclude 'data/' \
  --exclude 'CLAUDE.md' \
  --exclude 'deploy.sh' \
  ./ "$SERVER:$APP_DIR/"

log "Syncing Python dependencies..."
ssh "$SERVER" "cd $APP_DIR && uv sync"

log "Restarting services..."
ssh "$SERVER" "systemctl restart llm-council-backend llm-council-frontend"

log "Deploy complete — https://llmcouncil.hosakka.com"
