import time
import requests

from services.direction_service import update_bus_history

GPS_API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"

_last_good_buses = []
_last_good_at = None
MAX_CACHE_SECONDS = 900

NOIDA_POLYGON = [
    (28.69, 77.28),
    (28.70, 77.39),
    (28.63, 77.49),
    (28.54, 77.47),
    (28.45, 77.38),
    (28.40, 77.30),
    (28.52, 77.27),
    (28.62, 77.24)
]

GREATER_NOIDA_POLYGON = [
    (28.63, 77.39),
    (28.62, 77.51),
    (28.55, 77.59),
    (28.45, 77.64),
    (28.34, 77.61),
    (28.30, 77.49),
    (28.33, 77.40),
    (28.45, 77.36),
    (28.54, 77.39)
]


def _point_in_polygon(latitude, longitude, polygon):
    inside = False
    j = len(polygon) - 1

    for i in range(len(polygon)):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]

        crosses = (lat_i > latitude) != (lat_j > latitude)
        if crosses:
            lon_at_lat = (lon_j - lon_i) * (latitude - lat_i) / (lat_j - lat_i) + lon_i
            if longitude < lon_at_lat:
                inside = not inside

        j = i

    return inside


def _in_noida_region(latitude, longitude):
    return (
        _point_in_polygon(latitude, longitude, NOIDA_POLYGON)
        or _point_in_polygon(latitude, longitude, GREATER_NOIDA_POLYGON)
    )

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
            bus_id = str(
                bus.get("bus_id")
                or bus.get("regNum")
                or bus.get("registration_no")
                or bus.get("RegNo")
                or ""
            ).strip().upper()

            electric_depot = str(bus.get("depot_name") or "").strip().upper()
            known_electric = bus_id in {
                "UP80KT3702",
                "UP80KT4582",
                "UP70PT6077",
                "UP70PT6268",
                "UP80LT4113",
                "UP80LT4117",
                "UP80LT4126",
                "UP80KT3630",
                "UP80KT3703",
                "UP70PT6330",
                "UP80LT4114",
                "UP80LT4120",
            }

            if electric_depot != "NOIDA ELECTRIC" and not known_electric:
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

            if not _in_noida_region(latitude, longitude):
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
