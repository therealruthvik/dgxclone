#!/bin/bash
# Run on Lambda Labs VM to set up the platform
set -euo pipefail

# ---------------------------------------------------------------------------
# Helper: install/fix NVIDIA drivers if nvidia-smi is broken
# ---------------------------------------------------------------------------
ensure_nvidia_smi() {
  if nvidia-smi &>/dev/null; then
    echo "    nvidia-smi OK"
    return 0
  fi

  echo "==> nvidia-smi failed — installing NVIDIA drivers"
  sudo apt-get update -qq
  # Detect recommended driver version; fall back to 535
  DRIVER=$(ubuntu-drivers devices 2>/dev/null | awk '/recommended/{print $NF}' | head -1)
  DRIVER=${DRIVER:-nvidia-driver-535}
  echo "    Installing $DRIVER"
  sudo apt-get install -y "$DRIVER"

  echo "==> Rebooting to load drivers — re-run this script after reboot"
  sudo reboot
  # Script exits here; user must re-run after reboot
}

echo "==> Checking NVIDIA drivers"
ensure_nvidia_smi

echo "==> Installing Docker"
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
sudo usermod -aG docker "$USER"

echo "==> Installing Docker Compose plugin"
sudo apt-get install -y docker-compose-plugin

echo "==> Installing NVIDIA Container Toolkit"
if ! dpkg -s nvidia-container-toolkit &>/dev/null; then
  distribution=$(. /etc/os-release; echo "$ID$VERSION_ID")
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -s -L "https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list" \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  sudo apt-get update -qq
  sudo apt-get install -y nvidia-container-toolkit
fi

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "==> Verifying GPU passthrough in Docker"
RETRY=0
until docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi &>/dev/null; do
  RETRY=$((RETRY + 1))
  if [ "$RETRY" -ge 3 ]; then
    echo "ERROR: GPU not visible inside Docker after $RETRY attempts."
    echo "       Try: sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
    exit 1
  fi
  echo "    Retrying Docker GPU check ($RETRY/3)..."
  sleep 5
done
echo "    GPU visible inside Docker — OK"

echo ""
echo "==> Setup complete."
echo "    Apply docker group without logout:  newgrp docker"
echo "    Then start the stack:               docker compose up -d --build"
