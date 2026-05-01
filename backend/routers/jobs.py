from fastapi import APIRouter, HTTPException, Depends
from redis import Redis
from rq import Queue
import json
from datetime import datetime
from ..models import Job, JobSubmit
from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

_redis = Redis.from_url(settings.redis_url)
_queue = Queue("gpu_jobs", connection=_redis)

JOB_KEY = "job:{id}"


def _save_job(job: Job):
    _redis.set(JOB_KEY.format(id=job.id), job.model_dump_json())


def _get_job(job_id: str) -> Job:
    raw = _redis.get(JOB_KEY.format(id=job_id))
    if not raw:
        raise HTTPException(status_code=404, detail="Job not found")
    return Job.model_validate_json(raw)


def _list_job_ids() -> list[str]:
    keys = _redis.keys("job:*")
    return [k.decode().split(":", 1)[1] for k in keys]


@router.post("/", response_model=Job, status_code=201)
def submit_job(payload: JobSubmit, username: str = Depends(get_current_user)):
    job = Job(**payload.model_dump(), owner=username)
    _save_job(job)
    _queue.enqueue("worker.tasks.run_job", job.id, job_timeout=3600)
    return job


@router.get("/", response_model=list[Job])
def list_jobs(username: str = Depends(get_current_user)):
    jobs = [_get_job(jid) for jid in _list_job_ids()]
    return [j for j in jobs if j.owner == username]


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str, username: str = Depends(get_current_user)):
    job = _get_job(job_id)
    if job.owner != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, username: str = Depends(get_current_user)):
    job = _get_job(job_id)
    if job.owner != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    if job.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running job")
    _redis.delete(JOB_KEY.format(id=job_id))
