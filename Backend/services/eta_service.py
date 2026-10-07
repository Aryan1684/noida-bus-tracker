import math
from datetime import datetime

from services.direction_service import LANDMARKS, ROUTES, nearest_segment
from utils.distance import calculate_distance

MIN_SPEED_KMH = 3.0
MAX_REASONABLE_SPEED_KMH = 90.0
MAX_HISTORY_GAP_SECONDS = 600.0


def _parse_time(value):
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )
        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def historical_speed_kmh(history):
    if not isinstance(history, list) or len(history) < 2:
        return 0.0

    total_km = 0.0
    total_hours = 0.0

    for previous, current in zip(history, history[1:]):
        previous_time = _parse_time(previous.get("time"))
        current_time = _parse_time(current.get("time"))

        if previous_time is None or current_time is None:
            continue

        delta_seconds = current_time - previous_time

        if delta_seconds <= 0 or delta_seconds > MAX_HISTORY_GAP_SECONDS:
            continue

        try:
            previous_lat = float(previous["latitude"])
            previous_lon = float(previous["longitude"])
            current_lat = float(current["latitude"])
            current_lon = float(current["longitude"])
        except (KeyError, TypeError, ValueError):
            continue

        distance_km = calculate_distance(
            previous_lat,
            previous_lon,
            current_lat,
            current_lon,
        )

        if distance_km > 0.01:
            implied_speed = distance_km / (delta_seconds / 3600.0)

            if implied_speed > MAX_REASONABLE_SPEED_KMH:
                continue

            total_km += distance_km

        total_hours += delta_seconds / 3600.0

    if total_km > 0.03 and total_hours > 0:
        return total_km / total_hours

    observed = []

    for point in history:
        try:
            speed = float(point.get("speed") or 0.0)
        except (TypeError, ValueError):
            continue

        if MIN_SPEED_KMH <= speed <= MAX_REASONABLE_SPEED_KMH:
            observed.append(speed)

    return sum(observed) / len(observed) if observed else 0.0


def _route_projection(route, latitude, longitude):
    if not route:
        return None

    try:
        points = [LANDMARKS[name] for name in route["points"]]
    except KeyError:
        return None

    cumulative_km = 0.0
    best = None

    for index in range(len(points) - 1):
        segment = nearest_segment(
            latitude,
            longitude,
            {"points": route["points"][index:index + 2]},
        )

        if segment is None:
            continue

        segment_length_km = calculate_distance(
            points[index][0],
            points[index][1],
            points[index + 1][0],
            points[index + 1][1],
        )

        candidate = {
            "along_km": cumulative_km + segment_length_km * segment["projection"],
            "off_route_km": segment["distance"],
        }

        if best is None or candidate["off_route_km"] < best["off_route_km"]:
            best = candidate

        cumulative_km += segment_length_km

    return best


def _route_distance_to_target(bus, latitude, longitude):
    route_name = str(bus.get("route") or "").strip()

    if not route_name or route_name.startswith("Towards "):
        return None, None

    route = next(
        (candidate for candidate in ROUTES if candidate["name"] == route_name),
        None,
    )

    if route is None:
        return None, None

    try:
        bus_latitude = float(bus["latitude"])
        bus_longitude = float(bus["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, None

    bus_projection = _route_projection(route, bus_latitude, bus_longitude)
    target_projection = _route_projection(route, latitude, longitude)

    if bus_projection is None or target_projection is None:
        return None, None

    if bus_projection["off_route_km"] > 3.0 or target_projection["off_route_km"] > 3.0:
        return None, None

    route_delta = target_projection["along_km"] - bus_projection["along_km"]

    if route_delta < -0.20:
        return None, "not_ahead"

    history = bus.get("prediction_history") or []
    direction_sign = _route_travel_direction(route, history)

    if direction_sign is not None and route_delta * direction_sign < -0.20:
        return None, "not_ahead"

    if direction_sign is None and route_delta < -0.20:
        return None, "not_ahead"

    return max(0.0, route_delta), "route_projection"


def _route_travel_direction(route, history):
    if not isinstance(history, list) or len(history) < 2:
        return None

    projections = []

    for point in history[-6:]:
        try:
            projection = _route_projection(
                route,
                float(point["latitude"]),
                float(point["longitude"]),
            )
        except (KeyError, TypeError, ValueError):
            continue

        if projection is None or projection["off_route_km"] > 3.0:
            continue

        projections.append(projection["along_km"])

    if len(projections) < 2:
        return None

    delta = projections[-1] - projections[0]

    if abs(delta) < 0.05:
        return None

    return 1 if delta > 0 else -1


def calculate_eta(bus, latitude, longitude):
    history = bus.get("prediction_history") or []
    speed_kmh = historical_speed_kmh(history)

    if speed_kmh < MIN_SPEED_KMH:
        try:
            reported_speed = float(bus.get("speed") or 0.0)
        except (TypeError, ValueError):
            reported_speed = 0.0

        if MIN_SPEED_KMH <= reported_speed <= MAX_REASONABLE_SPEED_KMH:
            speed_kmh = reported_speed

    if speed_kmh < MIN_SPEED_KMH:
        return {
            "eta_minutes": None,
            "eta_status": "unavailable",
            "eta_source": None,
        }

    direct_distance_km = calculate_distance(
        float(bus["latitude"]),
        float(bus["longitude"]),
        latitude,
        longitude,
    )

    route_distance_km, route_status = _route_distance_to_target(
        bus,
        latitude,
        longitude,
    )

    if route_status == "not_ahead":
        return {
            "eta_minutes": None,
            "eta_status": "not_ahead",
            "eta_source": "route_projection",
        }

    if route_distance_km is not None and route_distance_km > 0.01:
        travel_distance_km = route_distance_km
        source = "route_projection"
    else:
        travel_distance_km = direct_distance_km
        source = "gps_distance"

    minutes = max(1, math.ceil(travel_distance_km / speed_kmh * 60.0))

    return {
        "eta_minutes": minutes,
        "eta_status": "estimated",
        "eta_source": source,
    }
