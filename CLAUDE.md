# DGX Cloud Clone — CLAUDE.md

## Project Overview

Self-hosted GPU job platform. Submit Docker-based AI workloads, stream live logs, monitor GPU metrics. Targets Ubuntu 22.04 VM with NVIDIA GPU.

## Architecture

```
Browser → Next.js (3000) → FastAPI (8000) → Redis → RQ Worker → Docker container (GPU)
                                          ↓
                               DCGM Exporter (9400) → Prometheus (9090) → Grafana (3001)
```

## Services & Ports

| Service        | Port | Description                              |
|----------------|------|------------------------------------------|
| frontend       | 3000 | Next.js 14 UI                            |
| backend        | 8000 | FastAPI REST + SSE log streaming         |
| worker         | —    | RQ worker, runs GPU Docker containers    |
| redis          | 6379 | Job queue + state store                  |
| dcgm-exporter  | 9400 | GPU metrics (Prometheus format)          |
| prometheus     | 9090 | Metrics scraper                          |
| grafana        | 3001 | Metrics dashboard (admin/admin)          |

## Key Files

| File | Role |
|------|------|
| `backend/main.py` | FastAPI app, mounts all routers |
| `backend/auth.py` | JWT auth, `OAuth2PasswordBearer(auto_error=False)` for SSE query-param token support |
| `backend/config.py` | Pydantic settings, reads `.env` |
| `backend/models.py` | `Job`, `User`, `Token` Pydantic models |
| `backend/routers/auth.py` | `/auth/register`, `/auth/token` endpoints |
| `backend/routers/jobs.py` | CRUD for jobs, enqueues to RQ queue `gpu_jobs` |
| `backend/routers/logs.py` | SSE log streaming at `/jobs/{id}/logs/stream` |
| `backend/routers/metrics.py` | GPU metrics proxy at `/metrics/gpu` |
| `worker/tasks.py` | `run_job()` — pulls job from Redis, runs Docker container, streams logs back |
| `frontend/src/app/page.tsx` | Main page, auth flow, job polling every 5s |
| `frontend/src/components/JobList.tsx` | Job tiles + auto-streaming `LogStream` component |
| `frontend/src/components/JobSubmitForm.tsx` | Job submit form |
| `frontend/src/components/GpuStats.tsx` | GPU metrics panel |
| `frontend/src/lib/api.ts` | All API calls (login, register, jobs CRUD, GPU metrics) |
| `docker-compose.yml` | Full stack definition |
| `monitoring/prometheus.yml` | Prometheus scrape config |
| `deploy/setup.sh` | One-time VM provisioner (Docker + NVIDIA Container Toolkit) |

## Data Model

**Job** (stored in Redis as JSON, key `job:{uuid}`):
- `id`, `name`, `image`, `command`, `env`, `gpu_count`
- `status`: `queued` → `running` → `completed` | `failed`
- `owner`: username string (jobs are user-scoped)
- `container_id`: set by worker when container starts, cleared when done
- `log_output`: last 10k chars of container stdout+stderr

**Users** stored in-memory dict in `backend/auth.py` (`_users`). Not persisted across restarts.

## Critical Implementation Details

### SSE Authentication
`EventSource` API cannot send custom headers. Token passed as query param `?token=`. `OAuth2PasswordBearer(auto_error=False)` required — without it, missing `Authorization` header raises 401 before `get_current_user` body runs. Logic: `token = query_token or token`.

### Log Streaming Flow
1. Worker sets `container_id` on job when container starts
2. `logs.py` polls Redis up to 30s for `container_id` to appear
3. Streams Docker container logs via `container.logs(stream=True, follow=True)`
4. On `docker.errors.NotFound`, falls back to stored `log_output` (container already finished)
5. Sends `[DONE]` sentinel to close client EventSource

### Frontend Auto-Log Streaming
`LogStream` component in `JobList.tsx`:
- `startedRef` prevents duplicate `EventSource` connections on re-renders
- Skips `queued` status; starts automatically on `running`/`completed`/`failed`
- Returns `null` when no lines (no empty UI element)

### Job Deletion
- `DELETE /jobs/{id}` removes job key from Redis entirely (`_redis.delete`)
- Blocked for `running` jobs (container would be orphaned)
- Frontend optimistically removes from local state on button click

### RQ Queue
Queue name: `gpu_jobs`. Worker task path: `worker.tasks.run_job`. Job timeout: 3600s.

## Environment Variables

```env
SECRET_KEY=<long random string>
REDIS_URL=redis://redis:6379
NEXT_PUBLIC_API_URL=http://<VM_IP>:8000
```

`NEXT_PUBLIC_API_URL` also baked into frontend at build time via Docker build arg in `docker-compose.yml`.

## Dev / Deploy Commands

```bash
# Full stack
docker compose up -d --build

# Rebuild specific service
docker compose up -d --build backend worker frontend

# Logs
docker compose logs -f backend
docker compose logs -f worker

# Debug Redis state
docker compose exec redis redis-cli keys "job:*"
docker compose exec redis redis-cli get "job:<id>"
```

## Known Constraints

- Users stored in-memory — lost on `backend` container restart
- `gpu_count` max 1 (model enforces `le=1`)
- CORS is open (`allow_origins=["*"]`) — acceptable for single-user VM deployment
- VM IP hardcoded in `docker-compose.yml` frontend build arg — must update on IP change
