import docker
import json
import os
from datetime import datetime
from redis import Redis

_redis = Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379"))

JOB_KEY = "job:{id}"


def _update_job(job_id: str, **kwargs):
    raw = _redis.get(JOB_KEY.format(id=job_id))
    if not raw:
        return
    data = json.loads(raw)
    data.update(kwargs)
    _redis.set(JOB_KEY.format(id=job_id), json.dumps(data))


def run_job(job_id: str):
    raw = _redis.get(JOB_KEY.format(id=job_id))
    if not raw:
        return

    job = json.loads(raw)
    _update_job(job_id, status="running", started_at=datetime.utcnow().isoformat())

    device_requests = []
    if job.get("gpu_count", 0) > 0:
        device_requests = [
            docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])
        ]

    client = docker.from_env()
    container = None
    try:
        container = client.containers.run(
            image=job["image"],
            command=job["command"],
            environment=job.get("env", {}),
            device_requests=device_requests,
            detach=True,
            stdout=True,
            stderr=True,
        )
        _update_job(job_id, container_id=container.id)

        result = container.wait()
        exit_code = result.get("StatusCode", -1)
        logs = container.logs().decode("utf-8", errors="replace")

        _update_job(
            job_id,
            status="completed" if exit_code == 0 else "failed",
            finished_at=datetime.utcnow().isoformat(),
            exit_code=exit_code,
            log_output=logs[-10_000:],
            container_id=None,
        )
    except Exception as e:
        _update_job(
            job_id,
            status="failed",
            finished_at=datetime.utcnow().isoformat(),
            exit_code=-1,
            log_output=str(e),
            container_id=None,
        )
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
        client.close()
