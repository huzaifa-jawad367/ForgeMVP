"""System hardware metrics: CPU, RAM, and (optionally) NVIDIA GPU."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import psutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GPU helpers — pynvml is optional
# ---------------------------------------------------------------------------

_GPU_AVAILABLE: bool = False

try:
    import pynvml  # type: ignore[import-untyped]

    pynvml.nvmlInit()
    _GPU_AVAILABLE = True
    logger.debug("pynvml initialised successfully")
except Exception:  # noqa: BLE001
    logger.info("pynvml unavailable — GPU metrics will be reported as None")


def _gpu_metrics() -> Dict[str, Optional[float]]:
    """Query the first NVIDIA GPU for utilisation, memory, and temperature."""
    if not _GPU_AVAILABLE:
        return {
            "gpu_utilization": None,
            "gpu_memory_percent": None,
            "gpu_temperature": None,
        }

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        temp = pynvml.nvmlDeviceGetTemperature(
            handle, pynvml.NVML_TEMPERATURE_GPU
        )

        gpu_mem_pct = (mem_info.used / mem_info.total) * 100.0 if mem_info.total else 0.0

        return {
            "gpu_utilization": float(util.gpu),
            "gpu_memory_percent": round(gpu_mem_pct, 2),
            "gpu_temperature": float(temp),
        }
    except Exception:  # noqa: BLE001
        logger.warning("Failed to query GPU metrics", exc_info=True)
        return {
            "gpu_utilization": None,
            "gpu_memory_percent": None,
            "gpu_temperature": None,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_hardware_metrics() -> Dict[str, Any]:
    """Return a flat dict of current CPU, memory, and GPU metrics.

    Keys always present:

    * ``cpu_percent`` — overall CPU usage (%).
    * ``memory_percent`` — physical RAM usage (%).
    * ``memory_used_gb`` — physical RAM in use (GiB, 2 d.p.).

    GPU keys (``None`` when no NVIDIA GPU / pynvml is unavailable):

    * ``gpu_utilization`` — GPU core usage (%).
    * ``gpu_memory_percent`` — GPU VRAM usage (%).
    * ``gpu_temperature`` — GPU temperature (°C).
    """
    vm = psutil.virtual_memory()

    metrics: Dict[str, Any] = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": vm.percent,
        "memory_used_gb": round(vm.used / (1024 ** 3), 2),
    }

    metrics.update(_gpu_metrics())
    return metrics
