import math
import os
import threading
import time
from datetime import datetime, timezone

import requests

from services.direction_service import update_bus_history
from services.ml_prediction_service import analyze_buses, prepare_histories

GPS_API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"

_last_good_buses = []
_last_good_at = None
_latest_processed_buses = []
_latest_processed_at = None
_cache_lock = threading.Lock()
MAX_CACHE_SECONDS = 900
PROCESSED_CACHE_SECONDS = max(120, int(int(os.getenv("PREDICTION_COLLECT_INTERVAL_SECONDS", "60")) * 2.5))

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
            lon_at_lat = (
                (lon_j - lon_i) * (latitude - lat_i) / (lat_j - lat_i)
                + lon_i
            )

            if longitude < lon_at_lat:
                inside = not inside

        j = i

    return inside


def _in_noida_region(latitude, longitude):
    return (
        _point_in_polygon(latitude, longitude, NOIDA_POLYGON)
        or _point_in_polygon(latitude, longitude, GREATER_NOIDA_POLYGON)
    )


def _parse_timestamp(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def _fix_age_seconds(timestamp, now=None):
    event_time = _parse_timestamp(timestamp)

    if event_time is None:
        return None

    age = (time.time() if now is None else now) - event_time

    if not math.isfinite(age):
        return None

    return max(0, int(age))


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


def _process_live_buses(data):
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

        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
            and _in_noida_region(latitude, longitude)
        ):
            continue

        raw_speed = bus.get("speed")
        try:
            parsed_speed = float(raw_speed)
            speed_valid = math.isfinite(parsed_speed) and 0 <= parsed_speed <= 130
        except (TypeError, ValueError):
            parsed_speed = 0.0
            speed_valid = False

        result = {
            "bus_id": str(bus.get("bus_id") or "").strip().upper(),
            "latitude": latitude,
            "longitude": longitude,
            "speed": round(parsed_speed, 1) if speed_valid else 0.0,
            "speed_valid": speed_valid,
            "timestamp": bus.get("timestamp"),
            "vehicle_status": bus.get("vehicle_status")
        }

        buses.append(result)

    if not buses:
        return []

    now = time.time()

    for result in buses:
        fix_age = _fix_age_seconds(result.get("timestamp"), now)
        result["fix_age_seconds"] = fix_age
        result["gps_age_seconds"] = fix_age
        result["data_stale"] = bool(
            fix_age is None or fix_age > 180
        )
        result["source_health"] = (
            "fresh" if fix_age is not None and fix_age <= 90
            else "aging" if fix_age is not None and fix_age <= 180
            else "stale"
        )

    histories = prepare_histories(buses)

    for result in buses:
        bus_id = str(result.get("bus_id") or "").strip().upper()
        history = histories.get(bus_id, [])
        direction = update_bus_history(result, history)

        if direction:
            result.update(direction)

        if history:
            result["validated_latitude"] = history[-1]["latitude"]
            result["validated_longitude"] = history[-1]["longitude"]
            result["canonical_latitude"] = history[-1]["latitude"]
            result["canonical_longitude"] = history[-1]["longitude"]
        else:
            result["validated_latitude"] = latitude
            result["validated_longitude"] = longitude
            result["canonical_latitude"] = latitude
            result["canonical_longitude"] = longitude

    ml_analysis = analyze_buses(buses, histories=histories)

    for result in buses:
        prediction = ml_analysis.get(
            str(result.get("bus_id") or "").strip().upper()
        )

        if prediction:
            result.update(prediction)

    return buses


def refresh_noida_electric_buses():
    global _last_good_buses, _last_good_at
    global _latest_processed_buses, _latest_processed_at

    try:
        data = _fetch_live_data()
        buses = _process_live_buses(data)

        if buses:
            now = time.time()

            with _cache_lock:
                _latest_processed_buses = [dict(bus) for bus in buses]
                _latest_processed_at = now
                _last_good_buses = [dict(bus) for bus in buses]
                _last_good_at = now

        return buses

    except Exception as error:
        raise RuntimeError(f"Noida bus refresh failed: {error}") from error


def get_noida_electric_buses(force_refresh=False):
    with _cache_lock:
        if (
            _latest_processed_buses
            and _latest_processed_at
            and time.time() - _latest_processed_at <= PROCESSED_CACHE_SECONDS
        ):
            return [dict(bus) for bus in _latest_processed_buses]

        if _last_good_buses and _last_good_at:
            age = time.time() - _last_good_at

            if age <= MAX_CACHE_SECONDS:
                cached = [dict(bus) for bus in _last_good_buses]

                for bus in cached:
                    bus["cache_age_seconds"] = int(age)

                    fix_age = bus.get("fix_age_seconds")
                    bus["data_stale"] = bool(
                        bus.get("data_stale")
                        or (
                            fix_age is not None
                            and fix_age > 180
                        )
                        or age > PROCESSED_CACHE_SECONDS
                    )

                return cached

    return []
