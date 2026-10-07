import math
from datetime import datetime, timezone

from utils.distance import calculate_distance

MAX_SPEED_KMH = 90.0
MAX_JUMP_DISTANCE_KM = 0.5
MAX_JUMP_INTERVAL_SECONDS = 5.0

NOIDA_BOUNDS = {
    "min_latitude": 28.30,
    "max_latitude": 28.70,
    "min_longitude": 77.24,
    "max_longitude": 77.64,
}


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


def _safe_float(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _reject(bus, reason, **details):
    return {
        "bus_id": str(bus.get("bus_id") or "").strip().upper() or None,
        "upstream_id": bus.get("bus_id"),
        "reason": reason,
        "details": details,
        "timestamp": bus.get("timestamp"),
    }


def _trace(bus_id, stages):
    return {"bus_id": bus_id, "stages": stages}


def validate_gps_batch(raw_buses, previous_points=None):
    previous_points = previous_points or {}
    accepted = []
    rejected = []
    seen = set()
    last_accepted = {
        str(key).strip().upper(): dict(value)
        for key, value in previous_points.items()
    }

    for raw in raw_buses:
        bus = dict(raw or {})
        stages = []

        if str(bus.get("depot_name") or "").strip().upper() != "NOIDA ELECTRIC":
            rejected.append(_reject(bus, "wrong_depot"))
            continue

        bus_id = str(bus.get("bus_id") or "").strip().upper()
        if not bus_id:
            rejected.append(_reject(bus, "missing_bus_id"))
            continue
        stages.append("identity_valid")

        timestamp = bus.get("timestamp")
        event_time = _parse_timestamp(timestamp)
        if event_time is None:
            rejected.append(_reject(bus, "invalid_timestamp"))
            continue
        stages.append("timestamp_valid")

        latitude = _safe_float(bus.get("latitude"))
        longitude = _safe_float(bus.get("longitude"))

        if latitude is None or longitude is None:
            rejected.append(_reject(bus, "invalid_coordinates"))
            continue

        if not (
            NOIDA_BOUNDS["min_latitude"] <= latitude <= NOIDA_BOUNDS["max_latitude"]
            and NOIDA_BOUNDS["min_longitude"] <= longitude <= NOIDA_BOUNDS["max_longitude"]
        ):
            rejected.append(
                _reject(
                    bus,
                    "outside_noida_bounds",
                    latitude=latitude,
                    longitude=longitude,
                )
            )
            continue
        stages.append("coordinates_valid")

        speed = _safe_float(bus.get("speed"))
        if speed is None or speed < 0 or speed > MAX_SPEED_KMH:
            rejected.append(
                _reject(
                    bus,
                    "impossible_speed",
                    value=speed,
                    threshold=MAX_SPEED_KMH,
                )
            )
            continue
        stages.append("speed_valid")

        duplicate_key = (
            bus_id,
            str(timestamp).strip(),
            round(latitude, 7),
            round(longitude, 7),
        )
        if duplicate_key in seen:
            rejected.append(_reject(bus, "duplicate_point"))
            continue
        seen.add(duplicate_key)
        stages.append("deduplicated")

        previous = last_accepted.get(bus_id)
        if previous is not None:
            previous_time = float(previous["event_time"])
            delta_seconds = event_time - previous_time

            if delta_seconds <= 0:
                rejected.append(
                    _reject(
                        bus,
                        "out_of_order",
                        previous_timestamp=previous.get("timestamp"),
                    )
                )
                continue
            stages.append("ordered")

            distance_km = calculate_distance(
                previous["latitude"],
                previous["longitude"],
                latitude,
                longitude,
            )

            if (
                delta_seconds < MAX_JUMP_INTERVAL_SECONDS
                and distance_km > MAX_JUMP_DISTANCE_KM
            ):
                rejected.append(
                    _reject(
                        bus,
                        "impossible_jump",
                        distance_km=round(distance_km, 3),
                        threshold_km=MAX_JUMP_DISTANCE_KM,
                        interval_seconds=round(delta_seconds, 2),
                        threshold_seconds=MAX_JUMP_INTERVAL_SECONDS,
                    )
                )
                continue

        stages.append("plausible_transition")

        normalized = {
            "bus_id": bus_id,
            "upstream_id": bus.get("bus_id"),
            "latitude": latitude,
            "longitude": longitude,
            "speed": round(speed, 1),
            "speed_valid": True,
            "timestamp": timestamp,
            "event_time": event_time,
            "vehicle_status": bus.get("vehicle_status"),
            "validation_trace": _trace(bus_id, stages + ["accepted"]),
        }

        accepted.append(normalized)
        last_accepted[bus_id] = normalized

    reason_counts = {}
    for item in rejected:
        reason_counts[item["reason"]] = reason_counts.get(item["reason"], 0) + 1

    return {
        "accepted": accepted,
        "rejected": rejected,
        "stats": {
            "received": len(raw_buses),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "reject_reasons": reason_counts,
        },
    }
