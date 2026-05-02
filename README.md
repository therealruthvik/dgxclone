# RUN:ai — Self-Hosted GPU Job Platform

Submit Docker-based AI workloads to a GPU cluster, stream live logs, and monitor GPU utilization — deployed on Kubernetes via Helm.

## Architecture

```
Browser → Next.js (3000) → FastAPI (8000) → Redis → RQ Worker → k8s Job (GPU pod)
                                          ↓
                               DCGM Exporter (9400) → Prometheus (9090) → Grafana (3000)
```

**Services:**

| Service | Port | Role |
|---------|------|------|
| frontend | 3000 | Next.js 14 UI |
| backend | 8000 | FastAPI REST + SSE log streaming |
| worker | — | RQ worker, creates k8s Jobs for GPU workloads |
| redis | 6379 | Job queue + state store |
| dcgm-exporter | 9400 | Per-GPU metrics (Prometheus format) |
| prometheus | 9090 | Metrics scraper |
| grafana | 3000 | GPU dashboard |

---

## Requirements

- Ubuntu 22.04 VM with NVIDIA GPU
- NVIDIA drivers installed (`nvidia-smi` works on host)
- SSH access to the VM
- Ports open: `80`, `443` (Ingress), `6443` (k3s API) — or a `NodePort` range if not using Ingress

---

## Part 1 — Provision the VM

Run once on the VM to install Docker, NVIDIA Container Toolkit, k3s, and the NVIDIA device plugin:

```bash
ssh ubuntu@YOUR_SERVER_IP
curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USER/dgxclone/main/deploy/setup.sh | bash
```

Or copy and run manually:

```bash
chmod +x deploy/setup.sh && ./deploy/setup.sh
```

After it finishes:

```bash
newgrp docker   # apply docker group without logging out
```

Verify GPU passthrough:

```bash
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi
```

Verify GPU visible to k3s:

```bash
sudo k3s kubectl get nodes -o json | jq '.items[].status.allocatable'
# should include "nvidia.com/gpu": "1" (or more)
```

---

## Part 2 — Build and Push Docker Images

Build all three images from your local machine (use `--platform linux/amd64` if building on Apple Silicon):

```bash
# Backend
docker build --platform linux/amd64 \
  -t YOUR_DOCKERHUB_USER/runaiclone-backend:latest \
  -f backend/Dockerfile .

# Worker
docker build --platform linux/amd64 \
  -t YOUR_DOCKERHUB_USER/runaiclone-worker:latest \
  -f worker/Dockerfile .

# Frontend — bake in the API path at build time
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_URL=/api \
  -t YOUR_DOCKERHUB_USER/runaiclone-frontend:latest \
  -f frontend/Dockerfile ./frontend

# Push all three
docker push YOUR_DOCKERHUB_USER/runaiclone-backend:latest
docker push YOUR_DOCKERHUB_USER/runaiclone-worker:latest
docker push YOUR_DOCKERHUB_USER/runaiclone-frontend:latest
```

> **Note:** `NEXT_PUBLIC_API_URL=/api` works when using Ingress (the default). The Ingress controller rewrites `/api/...` → `/...` and forwards to the backend. If deploying without Ingress, set it to `http://YOUR_SERVER_IP:NODE_PORT` instead.

---

## Part 3 — Configure Helm Values

Edit `helm/dgxclone/values.yaml`:

```yaml
images:
  backend:
    repository: YOUR_DOCKERHUB_USER/runaiclone-backend
  worker:
    repository: YOUR_DOCKERHUB_USER/runaiclone-worker
  frontend:
    repository: YOUR_DOCKERHUB_USER/runaiclone-frontend

backend:
  secretKey: "replace-with-a-long-random-string"

ingress:
  enabled: true
  className: nginx
  host: YOUR_SERVER_IP.nip.io   # or your real domain
```

Generate a secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Part 4 — Install ingress-nginx (if not already installed)

```bash
sudo k3s kubectl apply -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/cloud/deploy.yaml

# Wait for controller to be ready
sudo k3s kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=120s
```

---

## Part 5 — Deploy via Helm

```bash
# On the VM (copy the helm/ directory there first via rsync or git clone)
sudo k3s kubectl create namespace dgxclone --dry-run=client -o yaml | sudo k3s kubectl apply -f -

helm upgrade --install dgxclone helm/dgxclone/ \
  --namespace dgxclone \
  --kubeconfig /etc/rancher/k3s/k3s.yaml \
  --wait
```

Check all pods are running:

```bash
sudo k3s kubectl get pods -n dgxclone
```

---

## Part 6 — Open the UI

Navigate to `http://YOUR_SERVER_IP.nip.io` in your browser (or the NodePort if Ingress is not used).

1. Click **Register** — create a username and password
2. Click **Login**
3. GPU stats load on the dashboard
4. Submit your first job

---

## Test Jobs

**Quick test (no GPU):**

| Field | Value |
|-------|-------|
| Name | `hello` |
| Image | `ubuntu:22.04` |
| Command | `echo "hello from RUN:ai"` |
| GPUs | `0` |

**Streaming logs test:**

| Field | Value |
|-------|-------|
| Name | `countdown` |
| Image | `ubuntu:22.04` |
| Command | `bash -c "for i in 10 9 8 7 6 5 4 3 2 1; do echo Count $i; sleep 1; done"` |
| GPUs | `0` |

**GPU detection test:**

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

> The PyTorch image is ~20 GB. First run pulls the image — the log panel shows pull status while waiting.

---

## Monitoring

| Dashboard | URL |
|-----------|-----|
| Grafana | `http://YOUR_SERVER_IP.nip.io/grafana` or NodePort |
| Prometheus | `http://YOUR_SERVER_IP.nip.io/prometheus` or NodePort |
| Raw GPU metrics | `http://DCGM_CLUSTER_IP:9400/metrics` |

Grafana default login: `admin` / `admin`

---

## Updating After Code Changes

Sync code to the VM:

```bash
rsync -avz --exclude 'node_modules' --exclude '.next' --exclude '.git' \
  /path/to/dgxclone/ \
  ubuntu@YOUR_SERVER_IP:~/dgxclone/
```

Rebuild and redeploy a single service (e.g., frontend):

```bash
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_URL=/api \
  -t YOUR_DOCKERHUB_USER/runaiclone-frontend:latest \
  -f frontend/Dockerfile ./frontend
docker push YOUR_DOCKERHUB_USER/runaiclone-frontend:latest

# On VM:
sudo k3s kubectl rollout restart deployment/dgxclone-frontend -n dgxclone
```

---

## Troubleshooting

**GPU not visible in k3s (`nvidia.com/gpu` missing from Allocatable):**
```bash
# Patch device plugin DaemonSet to use nvidia runtime
sudo k3s kubectl -n kube-system patch daemonset nvidia-device-plugin-daemonset \
  --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/runtimeClassName","value":"nvidia"}]'
```

**Pods stuck in `ContainerCreating` / GPU jobs fail with NVML error:**
```bash
# Configure nvidia-ctk for k3s containerd
sudo nvidia-ctk runtime configure \
  --runtime=containerd \
  --config=/var/lib/rancher/k3s/agent/etc/containerd/config.toml
sudo systemctl restart k3s
```

**Frontend pod in `Error` state (exec format error):**
- Image built for wrong architecture. Rebuild with `--platform linux/amd64`.

**Jobs stuck in `queued` / worker not picking up:**
```bash
sudo k3s kubectl logs -n dgxclone deploy/dgxclone-worker
```

**Log panel blank during image pull:**
- Normal — log streaming shows pull status messages every 15 seconds. Large images (PyTorch) take several minutes.

**503 Service Unavailable:**
```bash
sudo k3s kubectl get pods -n dgxclone
sudo k3s kubectl describe ingress -n dgxclone
```

**Debug Redis job state:**
```bash
sudo k3s kubectl exec -n dgxclone deploy/dgxclone-backend -- \
  redis-cli -u redis://dgxclone-redis:6379 keys "job:*"
```

**Disk full during Docker build:**
```bash
docker system prune -a --volumes
```

---

## Project Structure

```
├── backend/          FastAPI app (auth, jobs, logs, k8s stats, GPU metrics)
├── worker/           RQ worker — creates k8s Jobs for GPU workloads
├── frontend/         Next.js 14 UI
├── helm/dgxclone/    Helm chart (backend, worker, frontend, redis, prometheus, grafana, dcgm)
├── monitoring/       Prometheus scrape config, Grafana provisioning
├── deploy/
│   ├── setup.sh      One-time VM provisioner (Docker + NVIDIA + k3s + device plugin)
│   └── deploy.sh     rsync + remote start helper
└── docker-compose.yml  Alternative: run stack in Docker without k8s
```

---

## Stack

- **Backend:** FastAPI, Redis, RQ, kubernetes Python client, python-jose, passlib
- **Frontend:** Next.js 14, Tailwind CSS, EventSource (SSE for live log streaming)
- **Orchestration:** k3s (lightweight Kubernetes), Helm
- **GPU metrics:** NVIDIA DCGM Exporter, Prometheus, Grafana
- **Container runtime:** containerd + NVIDIA Container Toolkit
