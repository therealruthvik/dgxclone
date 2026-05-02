import json
import os
import time
from datetime import datetime

from kubernetes import client as k8s_client, config as k8s_config
from kubernetes.client.exceptions import ApiException
from redis import Redis

_redis = Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379"))
NAMESPACE = os.environ.get("K8S_NAMESPACE", "default")
JOB_KEY = "job:{id}"
_JOB_LABEL = "dgxclone/job-id"


def _init_k8s():
    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()


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

    _init_k8s()
    batch_v1 = k8s_client.BatchV1Api()
    core_v1 = k8s_client.CoreV1Api()

    # k8s name: prefix + first 16 chars of UUID (no dots, lowercase, valid DNS label)
    k8s_job_name = f"dgxclone-{job_id[:16]}"

    resources = None
    if job.get("gpu_count", 0) > 0:
        resources = k8s_client.V1ResourceRequirements(
            limits={"nvidia.com/gpu": str(job["gpu_count"])}
        )

    env_vars = [
        k8s_client.V1EnvVar(name=k, value=v)
        for k, v in job.get("env", {}).items()
    ]

    container = k8s_client.V1Container(
        name="job",
        image=job["image"],
        command=["/bin/sh", "-c", job["command"]],
        env=env_vars or None,
        resources=resources,
    )

    k8s_job_body = k8s_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_client.V1ObjectMeta(
            name=k8s_job_name,
            labels={_JOB_LABEL: job_id},
        ),
        spec=k8s_client.V1JobSpec(
            template=k8s_client.V1PodTemplateSpec(
                metadata=k8s_client.V1ObjectMeta(
                    labels={_JOB_LABEL: job_id}
                ),
                spec=k8s_client.V1PodSpec(
                    containers=[container],
                    restart_policy="Never",
                ),
            ),
            backoff_limit=0,
            ttl_seconds_after_finished=86400,
        ),
    )

    try:
        batch_v1.create_namespaced_job(namespace=NAMESPACE, body=k8s_job_body)
    except ApiException as e:
        _update_job(
            job_id,
            status="failed",
            finished_at=datetime.utcnow().isoformat(),
            exit_code=-1,
            log_output=f"Failed to create k8s Job: {e}",
        )
        return

    # Wait for pod to appear (image pull can take minutes)
    pod_name = None
    for _ in range(120):
        time.sleep(3)
        try:
            pods = core_v1.list_namespaced_pod(
                namespace=NAMESPACE,
                label_selector=f"job-name={k8s_job_name}",
            )
            if pods.items:
                pod_name = pods.items[0].metadata.name
                _update_job(job_id, pod_name=pod_name)
                break
        except Exception:
            pass

    if not pod_name:
        _update_job(
            job_id,
            status="failed",
            finished_at=datetime.utcnow().isoformat(),
            exit_code=-1,
            log_output="Timed out waiting for pod to appear",
        )
        return

    # Poll for job completion (up to 1 hour)
    exit_code = -1
    for _ in range(1200):
        time.sleep(3)
        try:
            k8s_job = batch_v1.read_namespaced_job(name=k8s_job_name, namespace=NAMESPACE)
            if k8s_job.status.succeeded:
                exit_code = 0
                break
            if k8s_job.status.failed:
                exit_code = 1
                break
        except Exception:
            break

    # Collect logs
    logs = ""
    try:
        logs = core_v1.read_namespaced_pod_log(name=pod_name, namespace=NAMESPACE)
    except Exception as e:
        logs = f"Failed to retrieve logs: {e}"

    _update_job(
        job_id,
        status="completed" if exit_code == 0 else "failed",
        finished_at=datetime.utcnow().isoformat(),
        exit_code=exit_code,
        log_output=logs[-10_000:],
        pod_name=None,
    )
