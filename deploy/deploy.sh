#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${1:-frankfurt}"
REMOTE_DIR="/opt/arcotel-schedule-bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> Deploying Arcotel Schedule Bot to ${REMOTE_HOST}:${REMOTE_DIR}..."

# 1. Ensure target directory exists on remote
ssh "${REMOTE_HOST}" "mkdir -p ${REMOTE_DIR}/data ${REMOTE_DIR}/assets/icons"

# 2. Archive and transfer project files
echo "==> Transferring files..."
tar -czf - \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='data/*.json' \
    --exclude='*.log' \
    -C "${PROJECT_DIR}" . | ssh "${REMOTE_HOST}" "tar -xzf - -C ${REMOTE_DIR}"

# 3. Setup Python venv and install dependencies on remote
echo "==> Configuring remote host..."
ssh "${REMOTE_HOST}" bash -s << 'EOF'
set -euo pipefail
cd /opt/arcotel-schedule-bot

# Ensure librsvg2-bin is available for card rendering
if ! command -v rsvg-convert &> /dev/null; then
    echo "Installing librsvg2-bin..."
    apt-get update -qq && apt-get install -y librsvg2-bin
fi

if ! python3 -m venv --help &> /dev/null; then
    echo "Installing python3-venv..."
    apt-get update -qq && apt-get install -y python3-venv python3.10-venv python3-pip
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtualenv..."
    python3 -m venv .venv
fi

echo "Installing / updating dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Create .env if missing
if [ ! -f ".env" ]; then
    echo "Creating initial .env from .env.example..."
    cp .env.example .env
fi

# Configure systemd service
echo "Configuring systemd service..."
cp deploy/arcotel-bot.service /etc/systemd/system/arcotel-bot.service
systemctl daemon-reload
systemctl enable arcotel-bot.service
systemctl restart arcotel-bot.service

echo "Checking status..."
systemctl is-active arcotel-bot.service
EOF

echo "==> Deployment to ${REMOTE_HOST} completed successfully!"
