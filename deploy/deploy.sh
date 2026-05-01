#!/bin/bash
# Run from your Mac: ./deploy/deploy.sh
set -euo pipefail

LAMBDA_IP="155.248.198.208"
LAMBDA_USER="${1:-ubuntu}"
REMOTE_DIR="~/dgxclone"

echo "==> Copying project to Lambda ($LAMBDA_USER@$LAMBDA_IP)"
rsync -avz --exclude '.git' --exclude 'node_modules' --exclude '.next' \
  /Users/ruthvikg/pythonprojects/dgxclone/ \
  "$LAMBDA_USER@$LAMBDA_IP:$REMOTE_DIR/"

echo "==> Running setup + launch on Lambda"
ssh "$LAMBDA_USER@$LAMBDA_IP" bash << 'REMOTE'
set -euo pipefail
cd ~/dgxclone

# Install Docker + NVIDIA toolkit if not present
if ! command -v docker &>/dev/null; then
  echo "--- Installing Docker + NVIDIA toolkit"
  chmod +x deploy/setup.sh && ./deploy/setup.sh
fi

# Open firewall ports
sudo ufw allow 8000/tcp 2>/dev/null || true
sudo ufw allow 3000/tcp 2>/dev/null || true
sudo ufw allow 3001/tcp 2>/dev/null || true
sudo ufw allow 9090/tcp 2>/dev/null || true

# Copy env
cp .env.example .env

# Pull images + start
docker compose pull --quiet 2>/dev/null || true
docker compose up -d --build

echo "--- Services:"
docker compose ps
REMOTE

echo ""
echo "==> Done!"
echo "    API:     http://$LAMBDA_IP:8000/docs"
echo "    UI:      http://$LAMBDA_IP:3000  (run frontend separately)"
echo "    Grafana: http://$LAMBDA_IP:3001  (admin/admin)"
