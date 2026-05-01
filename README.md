# DGX Cloud Clone

Self-hosted GPU job platform. Submit AI workloads, stream live logs, monitor GPU metrics — running on any NVIDIA GPU VM.

## Architecture

```
Browser → Next.js (3000) → FastAPI (8000) → Redis → RQ Worker → Docker container (GPU)
                                          ↓
                               DCGM Exporter (9400) → Prometheus (9090) → Grafana (3001)
```

**Services:**

| Service | Port | Role |
|---------|------|------|
| frontend | 3000 | Next.js 14 UI |
| backend | 8000 | FastAPI REST + SSE |
| worker | — | RQ worker, runs GPU containers |
| redis | 6379 | Job queue + state store |
| dcgm-exporter | 9400 | GPU metrics (Prometheus format) |
| prometheus | 9090 | Metrics scraper |
| grafana | 3001 | Metrics dashboard |

---

## Requirements

- Ubuntu 22.04 VM with NVIDIA GPU
- NVIDIA drivers installed (`nvidia-smi` works on host)
- SSH access to the VM
- Port 3000 and 8000 open in firewall/security group

---

## Step 1 — Provision the VM

Run once on the VM to install Docker, NVIDIA Container Toolkit, and verify GPU passthrough:

```bash
ssh ubuntu@<YOUR_VM_IP>
curl -fsSL https://raw.githubusercontent.com/therealruthvik/dgxclone/main/deploy/setup.sh | bash
```

After it finishes, apply the docker group without logging out:

```bash
newgrp docker
```

Verify:

```bash
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

You should see your GPU listed. If not, reboot the VM and try again.

---

## Step 2 — Clone the repo

On the VM:

```bash
git clone https://github.com/therealruthvik/dgxclone.git
cd dgxclone
```

---

## Step 3 — Configure environment

```bash
cp .env.example .env
nano .env
```

Edit `.env`:

```env
SECRET_KEY=replace-with-a-long-random-string
REDIS_URL=redis://redis:6379
NEXT_PUBLIC_API_URL=http://<YOUR_VM_IP>:8000
```

Generate a strong secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Step 4 — Set your VM IP in docker-compose.yml

Open `docker-compose.yml` and replace the IP in the frontend build arg:

```yaml
args:
  - NEXT_PUBLIC_API_URL=http://<YOUR_VM_IP>:8000
```

---

## Step 5 — Build and start

```bash
docker compose up -d --build
```

First build takes 5–10 minutes (pulls base images, compiles Next.js).

Check all services are running:

```bash
docker compose ps
```

All services should show `Up`. If any are restarting, check logs:

```bash
docker compose logs <service-name>
```

---

## Step 6 — Open the UI

Navigate to `http://<YOUR_VM_IP>:3000` in your browser.

1. Click **Register** — create a username and password
2. Click **Login**
3. GPU stats appear on the left panel
4. Submit your first job (see test jobs below)

---

## Test Jobs

**Quick test (no GPU):**

| Field | Value |
|-------|-------|
| Name | `hello` |
| Image | `ubuntu:22.04` |
| Command | `echo "Hello from DGX Clone"` |
| GPUs | `0` |

**Streaming logs test:**

| Field | Value |
|-------|-------|
| Name | `countdown` |
| Image | `ubuntu:22.04` |
| Command | `bash -c "for i in 10 9 8 7 6 5 4 3 2 1; do echo Count $i; sleep 1; done"` |
| GPUs | `0` |

**GPU test:**

| Field | Value |
|-------|-------|
| Name | `gpu-check` |
| Image | `nvidia/cuda:12.3.0-base-ubuntu22.04` |
| Command | `nvidia-smi` |
| GPUs | `1` |

**PyTorch CUDA test:**

| Field | Value |
|-------|-------|
| Name | `torch-cuda` |
| Image | `nvcr.io/nvidia/pytorch:24.01-py3` |
| Command | `python3 -c "import torch; print(torch.cuda.get_device_name(0))"` |
| GPUs | `1` |

Note: PyTorch image is ~20 GB — first run pulls the image and takes several minutes.

---

## Monitoring

- **Grafana:** `http://<YOUR_VM_IP>:3001` — login `admin` / `admin`
- **Prometheus:** `http://<YOUR_VM_IP>:9090`
- **Raw GPU metrics:** `http://<YOUR_VM_IP>:9400/metrics`

---

## Updating after code changes

From your local machine, copy changed files to the VM then rebuild:

```bash
scp <local-file> ubuntu@<YOUR_VM_IP>:~/dgxclone/<path>
ssh ubuntu@<YOUR_VM_IP> "cd dgxclone && docker compose up -d --build backend worker frontend"
```

---

## Troubleshooting

**GPU not detected in containers:**
```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Permission denied on docker.sock:**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

**Frontend shows old IP after VM restart:**

Edit `docker-compose.yml`, update `NEXT_PUBLIC_API_URL`, rebuild:
```bash
docker compose up -d --build frontend
```

**Worker stuck / jobs stay queued:**
```bash
docker compose logs worker
docker compose restart worker
```

**Check Redis job state directly:**
```bash
docker compose exec redis redis-cli keys "job:*"
docker compose exec redis redis-cli get "job:<job-id>"
```

---

## Stack

- **Backend:** FastAPI, Redis, RQ, Docker SDK, python-jose, passlib
- **Frontend:** Next.js 14, Tailwind CSS, EventSource (SSE)
- **GPU metrics:** DCGM Exporter, Prometheus, Grafana
- **Containers:** Docker with NVIDIA Container Toolkit
