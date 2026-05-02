import os
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

_DCGM_FIELDS = {
    "DCGM_FI_DEV_GPU_UTIL":     "gpu_utilization_pct",
    "DCGM_FI_DEV_FB_USED":      "gpu_memory_used_mb",
    "DCGM_FI_DEV_FB_FREE":      "gpu_memory_free_mb",
    "DCGM_FI_DEV_GPU_TEMP":     "gpu_temperature_c",
    "DCGM_FI_DEV_POWER_USAGE":  "gpu_power_w",
}


def _init_k8s():
    try:
        k8s_config.load_incluster_config()
    except Exception:
        kubeconfig = os.environ.get("KUBECONFIG", "/etc/rancher/k3s/k3s.yaml")
        try:
            k8s_config.load_kube_config(config_file=kubeconfig)
        except Exception as e:
            raise RuntimeError(f"No k8s config available: {e}")


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
    result: dict = {
        "nodes": None,
        "pods_running": None,
        "pods_total": None,
        "namespaces": None,
        "memory_used_gb": None,
        "memory_total_gb": None,
        "gpu_utilization_pct": None,
        "gpu_memory_used_mb": None,
        "gpu_memory_total_mb": None,
        "gpu_temperature_c": None,
        "gpu_power_w": None,
        "k8s_error": None,
    }

    # --- GPU metrics (DCGM — always available) ---
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            res = await client.get(DCGM_URL)
            for line in res.text.splitlines():
                if line.startswith("#"):
                    continue
                for dcgm_key, out_key in _DCGM_FIELDS.items():
                    if line.startswith(dcgm_key + "{"):
                        try:
                            result[out_key] = float(line.split("} ")[-1].strip())
                        except ValueError:
                            pass
        used = result.get("gpu_memory_used_mb")
        free = result.get("gpu_memory_free_mb")
        if used is not None and free is not None:
            result["gpu_memory_total_mb"] = used + free
    except Exception as e:
        result["gpu_error"] = str(e)

    # --- k8s stats ---
    if not _K8S_AVAILABLE:
        result["k8s_error"] = "kubernetes package not installed"
        return result

    try:
        _init_k8s()
        v1 = k8s_client.CoreV1Api()

        nodes = v1.list_node()
        result["nodes"] = len(nodes.items)

        pods = v1.list_pod_for_all_namespaces()
        result["pods_running"] = sum(1 for p in pods.items if p.status.phase == "Running")
        result["pods_total"] = len(pods.items)

        result["namespaces"] = len(v1.list_namespace().items)

        result["memory_total_gb"] = round(sum(
            _parse_memory_gb(n.status.allocatable.get("memory", "0Ki"))
            for n in nodes.items
            if n.status.allocatable
        ), 1)

        # Used memory from metrics-server (optional addon)
        try:
            custom = k8s_client.CustomObjectsApi()
            node_metrics = custom.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
            result["memory_used_gb"] = round(sum(
                _parse_memory_gb(item.get("usage", {}).get("memory", "0Ki"))
                for item in node_metrics.get("items", [])
            ), 1)
        except Exception:
            pass

    except Exception as e:
        result["k8s_error"] = str(e)

    return result
