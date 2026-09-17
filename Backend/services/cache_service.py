import asyncio
import time

from services.gps_service import get_noida_electric_buses

_cache = []
_last_updated = 0
CACHE_DURATION = 60


def get_cached_buses():
    return _cache


def get_cache_info():
    return {
        "last_updated": _last_updated,
        "cache_age": round(time.time() - _last_updated, 1) if _last_updated else None,
        "cache_duration": CACHE_DURATION,
        "bus_count": len(_cache)
    }


async def update_cache():
    global _cache, _last_updated

    while True:
        try:
            buses = await asyncio.to_thread(get_noida_electric_buses)

            _cache = buses
            _last_updated = time.time()

            print(f"GPS cache updated: {len(_cache)} buses")

        except Exception as e:
            print(f"GPS update failed: {e}")

        await asyncio.sleep(CACHE_DURATION)