import docker
import json
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from redis import Redis
from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/jobs", tags=["logs"])

_redis = Redis.from_url(settings.redis_url)
JOB_KEY = "job:{id}"


@router.get("/{job_id}/logs/stream")
async def stream_logs(job_id: str, username: str = Depends(get_current_user)):
    raw = _redis.get(JOB_KEY.format(id=job_id))
    if not raw:
        raise HTTPException(status_code=404, detail="Job not found")

    job = json.loads(raw)
    if job.get("owner") != username:
        raise HTTPException(status_code=403, detail="Forbidden")

    async def generate():
        # If already finished, stream stored logs
        if job.get("status") in ("completed", "failed"):
            logs = job.get("log_output", "")
            for line in logs.splitlines():
                yield f"data: {line}\n\n"
            yield "data: [DONE]\n\n"
            return

        container_id = job.get("container_id")
        if not container_id:
            # Poll until container_id appears or job finishes (large images take minutes to pull)
            for i in range(180):
                await asyncio.sleep(2)
                if i % 20 == 0:
                    yield "data: [Pulling image, please wait...]\n\n"
                raw2 = _redis.get(JOB_KEY.format(id=job_id))
                if not raw2:
                    break
                job2 = json.loads(raw2)
                if job2.get("container_id"):
                    container_id = job2["container_id"]
                    break
                if job2.get("status") in ("completed", "failed"):
                    logs = job2.get("log_output", "")
                    for line in logs.splitlines():
                        yield f"data: {line}\n\n"
                    yield "data: [DONE]\n\n"
                    return

        if not container_id:
            yield "data: [Timed out waiting for container — image may still be pulling]\n\n"
            yield "data: [DONE]\n\n"
            return

        client = docker.from_env()
        try:
            container = client.containers.get(container_id)
            loop = asyncio.get_event_loop()
            log_iter = await loop.run_in_executor(
                None, lambda: container.logs(stream=True, follow=True)
            )
            for chunk in log_iter:
                line = chunk.decode("utf-8", errors="replace").rstrip()
                if line:
                    yield f"data: {line}\n\n"
        except docker.errors.NotFound:
            # Container done — serve stored logs
            raw3 = _redis.get(JOB_KEY.format(id=job_id))
            if raw3:
                job3 = json.loads(raw3)
                for line in (job3.get("log_output") or "").splitlines():
                    yield f"data: {line}\n\n"
        except Exception as e:
            yield f"data: [error: {e}]\n\n"
        finally:
            client.close()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
