import asyncio
import json
import threading
import time
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from redis import Redis
from ..auth import get_current_user
from ..config import settings

try:
    from kubernetes import client as k8s_client, config as k8s_config
    _K8S_AVAILABLE = True
except ImportError:
    _K8S_AVAILABLE = False

router = APIRouter(prefix="/jobs", tags=["logs"])
_redis = Redis.from_url(settings.redis_url)
JOB_KEY = "job:{id}"


def _make_k8s_core_client():
    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()
    return k8s_client.CoreV1Api()


@router.get("/{job_id}/logs/stream")
async def stream_logs(job_id: str, username: str = Depends(get_current_user)):
    raw = _redis.get(JOB_KEY.format(id=job_id))
    if not raw:
        raise HTTPException(status_code=404, detail="Job not found")

    job = json.loads(raw)
    if job.get("owner") != username:
        raise HTTPException(status_code=403, detail="Forbidden")

    async def generate():
        # Already finished — serve stored logs immediately
        if job.get("status") in ("completed", "failed"):
            for line in (job.get("log_output") or "").splitlines():
                yield f"data: {line}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Wait for pod_name to appear in Redis (worker sets it once pod is scheduled)
        pod_name = job.get("pod_name")
        if not pod_name:
            for i in range(180):
                await asyncio.sleep(2)
                if i % 20 == 0:
                    yield "data: [Pulling image, please wait...]\n\n"
                raw2 = _redis.get(JOB_KEY.format(id=job_id))
                if not raw2:
                    break
                job2 = json.loads(raw2)
                if job2.get("pod_name"):
                    pod_name = job2["pod_name"]
                    break
                if job2.get("status") in ("completed", "failed"):
                    for line in (job2.get("log_output") or "").splitlines():
                        yield f"data: {line}\n\n"
                    yield "data: [DONE]\n\n"
                    return

        if not pod_name:
            yield "data: [Timed out waiting for pod]\n\n"
            yield "data: [DONE]\n\n"
            return

        if not _K8S_AVAILABLE:
            yield "data: [kubernetes package not available]\n\n"
            yield "data: [DONE]\n\n"
            return

        log_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def fetch_logs():
            try:
                v1 = _make_k8s_core_client()
                namespace = settings.k8s_namespace

                # Wait for pod to reach Running/Succeeded/Failed before tailing logs
                for _ in range(60):
                    try:
                        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                        if pod.status.phase in ("Running", "Succeeded", "Failed"):
                            break
                    except Exception:
                        pass
                    time.sleep(3)

                resp = v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    follow=True,
                    _preload_content=False,
                )
                for chunk in resp.read_chunked():
                    text = chunk.decode("utf-8", errors="replace")
                    for line in text.splitlines():
                        if line:
                            loop.call_soon_threadsafe(log_queue.put_nowait, line)
            except Exception:
                # Streaming failed — fall back to stored log_output
                raw3 = _redis.get(JOB_KEY.format(id=job_id))
                if raw3:
                    job3 = json.loads(raw3)
                    for line in (job3.get("log_output") or "").splitlines():
                        loop.call_soon_threadsafe(log_queue.put_nowait, line)
            finally:
                loop.call_soon_threadsafe(log_queue.put_nowait, None)

        threading.Thread(target=fetch_logs, daemon=True).start()

        while True:
            line = await log_queue.get()
            if line is None:
                break
            yield f"data: {line}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
