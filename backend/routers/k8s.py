import httpx
from fastapi import APIRouter, Depends
from ..auth import get_current_user

try:
    from kubernetes import client as k8s_client, config as k8s_config
    _K8S_AVAILABLE = True
except ImportError:
    _K8S_AVAILABLE = False

router = APIRouter(prefix="/k8s", tags=["k8s"])

DCGM_URL = "http://dcgm-exporter:9400/metrics"


def _init_k8s():
    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()


def _parse_memory_gb(mem_str: str) -> float:
    try:
        if mem_str.endswith("Ki"):
            return int(mem_str[:-2]) / (1024 * 1024)
        if mem_str.endswith("Mi"):
            return int(mem_str[:-2]) / 1024
        if mem_str.endswith("Gi"):
            return float(mem_str[:-2])
        if mem_str.endswith("Ti"):
            return float(mem_str[:-2]) * 1024
        return int(mem_str) / (1024 ** 3)
    except Exception:
        return 0.0


@router.get("/stats")
async def k8s_stats(username: str = Depends(get_current_user)):
    if not _K8S_AVAILABLE:
        return {"error": "kubernetes package not installed"}

    try:
        _init_k8s()
        v1 = k8s_client.CoreV1Api()

        nodes = v1.list_node()
        node_count = len(nodes.items)

        pods = v1.list_pod_for_all_namespaces()
        pods_running = sum(1 for p in pods.items if p.status.phase == "Running")
        pods_total = len(pods.items)

        namespaces = v1.list_namespace()
        namespace_count = len(namespaces.items)

        # Allocatable memory across all nodes
        memory_total_gb = sum(
            _parse_memory_gb(n.status.allocatable.get("memory", "0Ki"))
            for n in nodes.items
            if n.status.allocatable
        )

        # Used memory from metrics server (optional — requires metrics-server addon)
        memory_used_gb = 0.0
        try:
            custom = k8s_client.CustomObjectsApi()
            node_metrics = custom.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
            memory_used_gb = sum(
                _parse_memory_gb(item.get("usage", {}).get("memory", "0Ki"))
                for item in node_metrics.get("items", [])
            )
        except Exception:
            pass

        # GPU utilization from DCGM exporter
        gpu_utilization_pct = None
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                res = await client.get(DCGM_URL)
                for line in res.text.splitlines():
                    if line.startswith("DCGM_FI_DEV_GPU_UTIL{"):
                        gpu_utilization_pct = float(line.split("} ")[-1].strip())
                        break
        except Exception:
            pass

        return {
            "nodes": node_count,
            "pods_running": pods_running,
            "pods_total": pods_total,
            "namespaces": namespace_count,
            "memory_used_gb": round(memory_used_gb, 1),
            "memory_total_gb": round(memory_total_gb, 1),
            "gpu_utilization_pct": gpu_utilization_pct,
        }
    except Exception as e:
        return {"error": str(e)}
