import time
import requests

from services.direction_service import update_bus_history

GPS_API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"

_last_good_buses = []
_last_good_at = None
MAX_CACHE_SECONDS = 900


def _fetch_live_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://margdarshi.upsrtcvlt.com",
        "Referer": "https://margdarshi.upsrtcvlt.com/",
    }

    last_error = None

    for attempt in range(3):
        try:
            response = requests.post(
                GPS_API_URL,
                headers=headers,
                timeout=(5, 15),
            )
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list):
                raise ValueError("MARGDARSHI returned an unexpected response")

            return data
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"MARGDARSHI live GPS request failed: {last_error}")


def get_noida_electric_buses():
    global _last_good_buses, _last_good_at

    try:
        data = _fetch_live_data()
        buses = []

        for bus in data:
            if bus.get("depot_name") != "NOIDA ELECTRIC":
                continue

            latitude = bus.get("latitude")
            longitude = bus.get("longitude")

            if latitude is None or longitude is None:
                continue

            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (ValueError, TypeError):
                continue

            result = {
                "bus_id": bus.get("bus_id"),
                "latitude": latitude,
                "longitude": longitude,
                "speed": bus.get("speed"),
                "timestamp": bus.get("timestamp"),
                "vehicle_status": bus.get("vehicle_status")
            }

            direction = update_bus_history(result)

            if direction:
                result.update(direction)

            buses.append(result)

        if buses:
            _last_good_buses = buses
            _last_good_at = time.time()

        return buses

    except Exception:
        if _last_good_buses and _last_good_at:
            age = time.time() - _last_good_at

            if age <= MAX_CACHE_SECONDS:
                cached = [dict(bus) for bus in _last_good_buses]

                for bus in cached:
                    bus["data_stale"] = True
                    bus["cache_age_seconds"] = int(age)

                return cached

        raise
