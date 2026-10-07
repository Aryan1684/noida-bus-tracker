import math

from services.direction_service import LANDMARKS, ROUTES
from utils.distance import calculate_distance

OFF_ROUTE_WARNING_M = 100.0
OFF_ROUTE_HARD_M = 300.0


def _route_candidates(bus_id):
    matched = [route for route in ROUTES if bus_id in route.get("buses", set())]
    return matched or ROUTES


def _geometry(route):
    points = []
    for name in route.get("points", []):
        coordinate = LANDMARKS.get(name)
        if coordinate is not None:
            points.append((name, coordinate[0], coordinate[1]))
    return points if len(points) >= 2 else None


def _bearing(lat1, lon1, lat2, lon2):
    first = math.radians(lat1)
    second = math.radians(lat2)
    delta = math.radians(lon2 - lon1)
    y = math.sin(delta) * math.cos(second)
    x = (
        math.cos(first) * math.sin(second)
        - math.sin(first) * math.cos(second) * math.cos(delta)
    )
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _angle_difference(first, second):
    difference = abs(first - second)
    return 360 - difference if difference > 180 else difference


def _project(latitude, longitude, route):
    geometry = _geometry(route)
    if not geometry:
        return None

    cumulative = 0.0
    best = None

    for index in range(len(geometry) - 1):
        from_name, from_lat, from_lon = geometry[index]
        to_name, to_lat, to_lon = geometry[index + 1]

        lat_scale = 111.32
        lon_scale = 111.32 * math.cos(math.radians(latitude))

        ax = (from_lon - longitude) * lon_scale
        ay = (from_lat - latitude) * lat_scale
        bx = (to_lon - longitude) * lon_scale
        by = (to_lat - latitude) * lat_scale

        dx = bx - ax
        dy = by - ay
        length_sq = dx * dx + dy * dy

        projection = (
            0.0
            if length_sq == 0
            else max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
        )

        px = ax + projection * dx
        py = ay + projection * dy
        off_route_km = math.hypot(px, py)

        segment_km = calculate_distance(
            from_lat,
            from_lon,
            to_lat,
            to_lon,
        )

        candidate = {
            "segment_index": index,
            "from": from_name,
            "to": to_name,
            "projection": projection,
            "off_route_km": off_route_km,
            "along_km": cumulative + segment_km * projection,
            "latitude": from_lat + (to_lat - from_lat) * projection,
            "longitude": from_lon + (to_lon - from_lon) * projection,
        }

        if best is None or candidate["off_route_km"] < best["off_route_km"]:
            best = candidate

        cumulative += segment_km

    if best:
        best["route_length_km"] = cumulative
        best["progress"] = (
            max(0.0, min(1.0, best["along_km"] / cumulative))
            if cumulative > 0
            else 0.0
        )

    return best


def match_position(bus_id, latitude, longitude, heading=None):
    candidates = []

    for route in _route_candidates(bus_id):
        projection = _project(latitude, longitude, route)
        if projection is None:
            continue

        score = projection["off_route_km"]

        if heading is not None:
            index = projection["segment_index"]
            geometry = _geometry(route)
            if geometry and index + 1 < len(geometry):
                a = geometry[index]
                b = geometry[index + 1]
                route_heading = _bearing(a[1], a[2], b[1], b[2])
                score += min(_angle_difference(heading, route_heading), 90) / 3000.0

        candidates.append((score, route, projection))

    if not candidates:
        return {
            "route_match_status": "unavailable",
            "route_match_distance_m": None,
            "route_progress": None,
            "route_match_confidence": "none",
            "map_matched_latitude": latitude,
            "map_matched_longitude": longitude,
            "matched_route_id": None,
            "matched_route": None,
            "route_segment_from": None,
            "route_segment_to": None,
            "route_segment_index": None,
        }

    candidates.sort(key=lambda item: item[0])
    _, route, projection = candidates[0]
    distance_m = projection["off_route_km"] * 1000.0

    if distance_m <= 50:
        confidence = "high"
    elif distance_m <= OFF_ROUTE_WARNING_M:
        confidence = "medium"
    elif distance_m <= OFF_ROUTE_HARD_M:
        confidence = "low"
    else:
        confidence = "off_route"

    use_projection = distance_m <= OFF_ROUTE_WARNING_M

    return {
        "route_match_status": "matched" if use_projection else "off_route",
        "route_match_distance_m": round(distance_m, 1),
        "route_progress": round(projection["progress"], 4),
        "route_match_confidence": confidence,
        "map_matched_latitude": round(
            projection["latitude"] if use_projection else latitude,
            6,
        ),
        "map_matched_longitude": round(
            projection["longitude"] if use_projection else longitude,
            6,
        ),
        "matched_route_id": route.get("id"),
        "matched_route": route.get("name"),
        "route_segment_from": projection["from"],
        "route_segment_to": projection["to"],
        "route_segment_index": projection["segment_index"],
        "next_stop": projection["to"],
        "next_stops": route.get("points", [])[projection["segment_index"] + 1:projection["segment_index"] + 4],
    }


def match_history(bus_id, history):
    matches = []

    for point in list(history or [])[-10:]:
        result = match_position(
            bus_id,
            float(point["latitude"]),
            float(point["longitude"]),
        )
        matches.append({
            "time": point.get("time"),
            "latitude": point.get("latitude"),
            "longitude": point.get("longitude"),
            "route_match_status": result["route_match_status"],
            "route_match_distance_m": result["route_match_distance_m"],
            "route_progress": result["route_progress"],
            "route_match_confidence": result["route_match_confidence"],
        })

    return matches
