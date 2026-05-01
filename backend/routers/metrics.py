import httpx
from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/metrics", tags=["metrics"])

DCGM_URL = "http://dcgm-exporter:9400/metrics"

_FIELDS = {
    "DCGM_FI_DEV_GPU_UTIL": "gpu_utilization_pct",
    "DCGM_FI_DEV_MEM_COPY_UTIL": "memory_utilization_pct",
    "DCGM_FI_DEV_FB_USED": "memory_used_mb",
    "DCGM_FI_DEV_FB_FREE": "memory_free_mb",
    "DCGM_FI_DEV_GPU_TEMP": "temperature_c",
    "DCGM_FI_DEV_POWER_USAGE": "power_draw_w",
}


def _parse_prometheus(text: str) -> dict:
    result: dict = {}
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        for dcgm_key, out_key in _FIELDS.items():
            if line.startswith(dcgm_key + "{"):
                try:
                    value = float(line.split("} ")[-1].strip())
                    result[out_key] = value
                except ValueError:
                    pass
    return result


@router.get("/gpu")
async def gpu_metrics(username: str = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(DCGM_URL)
            res.raise_for_status()
            data = _parse_prometheus(res.text)
            if "memory_used_mb" in data and "memory_free_mb" in data:
                data["memory_total_mb"] = data["memory_used_mb"] + data["memory_free_mb"]
            return data
    except Exception as e:
        return {"error": str(e)}
