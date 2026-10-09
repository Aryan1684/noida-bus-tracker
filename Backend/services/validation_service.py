import math
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from utils.distance import calculate_distance

MAX_SPEED_KMH = 90.0
MAX_JUMP_DISTANCE_KM = 0.5
MAX_JUMP_INTERVAL_SECONDS = 5.0


def _parse_timestamp(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
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
    trackable = []
    rejected = []
    seen = set()
    last_trackable = {
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

        status = (
            str(bus.get("vehicle_status") or "")
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )
        if status in {"no_signal", "nosignal", "offline", "unavailable"}:
            rejected.append(_reject(bus, "no_signal"))
            continue
        stages.append("signal_available")

        timestamp = bus.get("timestamp")
        parsed_event_time = _parse_timestamp(timestamp)
        event_time = parsed_event_time
        timestamp_status = "valid"

        if event_time is None:
            event_time = time.time()
            timestamp_status = "missing_or_invalid"
            history_trackable = False
        elif event_time > time.time() + 300:
            event_time = time.time()
            timestamp_status = "future_normalized"
            history_trackable = False

        stages.append("timestamp_received")

        latitude = _safe_float(bus.get("latitude"))
        longitude = _safe_float(bus.get("longitude"))

        if latitude is None or longitude is None:
            rejected.append(_reject(bus, "invalid_coordinates"))
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

        temporal_status = "accepted"
        history_trackable = locals().get("history_trackable", True)
        previous = last_trackable.get(bus_id)

        if previous is not None:
            previous_time = float(previous["event_time"])
            delta_seconds = event_time - previous_time
            distance_km = calculate_distance(
                previous["latitude"],
                previous["longitude"],
                latitude,
                longitude,
            )

            if delta_seconds < -120:
                current_age = time.time() - event_time
                previous_age = time.time() - previous_time
                if current_age <= 600 and previous_age < -300:
                    temporal_status = "baseline_reset"
                    history_trackable = True
                    stages.append("future_baseline_reset")
                else:
                    rejected.append(
                        _reject(
                            bus,
                            "out_of_order",
                            previous_timestamp=previous.get("timestamp"),
                            regression_seconds=round(abs(delta_seconds), 2),
                        )
                    )
                    continue
            elif delta_seconds < 0:
                current_age = time.time() - event_time
                previous_age = time.time() - previous_time
                if current_age <= 600 and previous_age < -300:
                    temporal_status = "baseline_reset"
                    history_trackable = True
                    stages.append("future_baseline_reset")
                else:
                    rejected.append(
                        _reject(
                            bus,
                            "out_of_order",
                            previous_timestamp=previous.get("timestamp"),
                            regression_seconds=round(abs(delta_seconds), 2),
                        )
                    )
                    continue
            elif delta_seconds == 0:
                temporal_status = "unchanged_fix"
                history_trackable = False
                stages.append("unchanged")
            else:
                stages.append("ordered")
                implied_speed = distance_km / (delta_seconds / 3600.0)

                if implied_speed > max(MAX_SPEED_KMH, speed + 90.0):
                    rejected.append(
                        _reject(
                            bus,
                            "impossible_speed_transition",
                            distance_km=round(distance_km, 3),
                            interval_seconds=round(delta_seconds, 2),
                            implied_speed_kmh=round(implied_speed, 1),
                        )
                    )
                    continue

                if (
                    delta_seconds < MAX_JUMP_INTERVAL_SECONDS
                    and distance_km > MAX_JUMP_DISTANCE_KM
                ):
                    rejected.append(
                        _reject(
                            bus,
                            "impossible_jump",
                            distance_km=round(distance_km, 3),
                            interval_seconds=round(delta_seconds, 2),
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
            "timestamp_status": timestamp_status,
            "fix_unchanged": temporal_status == "unchanged_fix",
            "validation_status": temporal_status,
            "history_trackable": history_trackable,
            "event_time": event_time,
            "vehicle_status": bus.get("vehicle_status"),
            "validation_trace": _trace(bus_id, stages + ["visible"]),
        }

        accepted.append(normalized)

        if history_trackable:
            trackable.append(normalized)
            last_trackable[bus_id] = normalized

    reason_counts = {}
    for item in rejected:
        reason_counts[item["reason"]] = reason_counts.get(item["reason"], 0) + 1

    return {
        "accepted": accepted,
        "trackable": trackable,
        "rejected": rejected,
        "stats": {
            "received": len(raw_buses),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "reject_reasons": reason_counts,
            "visible_untrackable": sum(
                1 for item in accepted if not item.get("history_trackable")
            ),
        },
    }
