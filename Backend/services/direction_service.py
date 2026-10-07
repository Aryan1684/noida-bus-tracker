import math
from utils.distance import calculate_distance

MIN_MOVEMENT_KM = 0.08

LANDMARKS = {
    "Sector 90": (28.5350, 77.3890),
    "Botanical Garden": (28.5641, 77.3358),
    "Golf Course": (28.5678, 77.3420),
    "Sector 37": (28.5626, 77.3402),
    "Noida City Center": (28.5745, 77.3560),
    "Hoshiyarpur": (28.5925, 77.3575),
    "Sector 51": (28.5855, 77.3608),
    "Sector 52": (28.5850, 77.3640),
    "Sector 62": (28.6280, 77.3770),
    "Parthala": (28.6075, 77.3755),
    "Gaur Chowk": (28.6150, 77.4350),
    "Kisan Chowk": (28.6050, 77.4370),
    "Chaar Murti": (28.603653, 77.425343),
    "Ek Murti": (28.600000, 77.447500),
    "Advant": (28.6205, 77.3785),
    "Surajpur Collectorate": (28.5095, 77.4770),
    "Surajpur": (28.5185, 77.4990),
    "Kasna Village": (28.4300, 77.5150),
    "Pari Chowk": (28.4652, 77.5080),
    "GIMS": (28.4400, 77.5030),
    "Noida Entry Gate": (28.5680, 77.3235),
    "Sector 14A": (28.5715, 77.3185),
    "Akshardham": (28.6127, 77.2773),
    "Kaushambi": (28.6450, 77.3210),
    "Anand Vihar Bus Station": (28.6469, 77.3168),
    "Noida International Airport": (28.17556, 77.60500)
}



CITY_ROUTES = {
    "R1": {
        "name": "Botanical Garden ↔ Pari Chowk via Surajpur",
        "stops": [
            "Botanical Garden", "Golf Course", "Noida City Center",
            "Hoshiyarpur", "Sector 51", "Parthala", "Gaur Chowk",
            "Ek Murti", "Surajpur Collectorate", "Pari Chowk"
        ]
    },
    "R2": {
        "name": "Botanical Garden ↔ Jewar Airport",
        "stops": [
            "Botanical Garden", "Sector 44", "Chhalera", "Amity School",
            "Expressway", "Pari Chowk", "Galgotias University",
            "Dankaur", "Rabupura", "Jewar Airport"
        ]
    },
    "R3": {
        "name": "Botanical Garden ↔ Surajpur via Sector 37",
        "stops": [
            "Botanical Garden", "Sector 37", "Chhalera", "Agahpur",
            "Barola", "Sector 50", "Sector 75", "Sector 75 North",
            "Sector 116", "Sector 78", "Samshang Phase 2",
            "Phulmundi", "Kulesara", "Surajpur"
        ]
    },
    "R4": {
        "name": "Botanical Garden ↔ New Bus Adda Ghaziabad",
        "stops": [
            "Botanical Garden", "Golf Course", "Noida City Center",
            "Sector 52", "Sain Mandir", "Sector 61", "Sector 62",
            "Pratap Vihar Ghaziabad", "RRTS Ghaziabad", "New Bus Adda Ghaziabad"
        ]
    },
    "R5": {
        "name": "Botanical Garden ↔ Anand Vihar Bus Station",
        "stops": [
            "Botanical Garden", "Sector 16", "Noida Entry Gate",
            "Sector 14A", "Akshardham", "Kaushambi", "Anand Vihar Bus Station"
        ]
    }
}

R01_BUSES = {
    "UP80KT3702", "UP80KT4582", "UP70PT6077", "UP70PT6268",
    "UP80LT4113", "UP80LT4117", "UP80LT4126",
    "UP80KT3630", "UP80KT3703", "UP70PT6330",
    "UP80LT4114", "UP80LT4120"
}

GR01_BUSES = {
    "UP14ST3546", "UP14TT1668",
    "UP14TT1667", "UP14TT1671",
    "UP14TT1679", "UP14TT1680"
}

ROUTES = [
    {
        "id": "N-R01-OUT",
        "name": "Sector 90 ↔ Botanical ↔ Ek Murti ↔ Pari Chowk",
        "points": [
            "Sector 90",
            "Botanical Garden",
            "Golf Course",
            "Noida City Center",
            "Hoshiyarpur",
            "Sector 51",
            "Parthala",
            "Gaur Chowk",
            "Ek Murti",
            "Surajpur Collectorate",
            "Pari Chowk"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "N-R01-RETURN",
        "name": "Pari Chowk ↔ Ek Murti ↔ Botanical ↔ Sector 90",
        "points": [
            "Pari Chowk",
            "Surajpur Collectorate",
            "Ek Murti",
            "Gaur Chowk",
            "Parthala",
            "Sector 51",
            "Hoshiyarpur",
            "Noida City Center",
            "Golf Course",
            "Botanical Garden",
            "Sector 90"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "N-R01-BOTANICAL-OUT",
        "name": "Botanical ↔ Ek Murti ↔ Pari Chowk",
        "points": [
            "Botanical Garden",
            "Golf Course",
            "Noida City Center",
            "Hoshiyarpur",
            "Sector 51",
            "Parthala",
            "Gaur Chowk",
            "Ek Murti",
            "Surajpur Collectorate",
            "Pari Chowk"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "N-R01-PARI-RETURN",
        "name": "Pari Chowk ↔ Ek Murti ↔ Botanical",
        "points": [
            "Pari Chowk",
            "Surajpur Collectorate",
            "Ek Murti",
            "Gaur Chowk",
            "Parthala",
            "Sector 51",
            "Hoshiyarpur",
            "Noida City Center",
            "Golf Course",
            "Botanical Garden"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "GR01-OUT",
        "name": "Sector 90 ↔ Botanical ↔ Chaar Murti ↔ Surajpur ↔ Kasna Village",
        "points": [
            "Sector 90",
            "Botanical Garden",
            "Chaar Murti",
            "Surajpur",
            "Kasna Village"
        ],
        "buses": GR01_BUSES
    },
    {
        "id": "GR01-RETURN",
        "name": "Kasna Village ↔ Surajpur ↔ Chaar Murti ↔ Botanical ↔ Sector 90",
        "points": [
            "Kasna Village",
            "Surajpur",
            "Chaar Murti",
            "Botanical Garden",
            "Sector 90"
        ],
        "buses": GR01_BUSES
    },
    {
        "id": "GR01-LOOP",
        "name": "Botanical ↔ Chaar Murti ↔ Surajpur ↔ Kasna Village",
        "points": [
            "Botanical Garden",
            "Chaar Murti",
            "Surajpur",
            "Kasna Village"
        ],
        "buses": GR01_BUSES
    },
    {
        "id": "GR01-LOOP-RETURN",
        "name": "Kasna Village ↔ Surajpur ↔ Chaar Murti ↔ Botanical",
        "points": [
            "Kasna Village",
            "Surajpur",
            "Chaar Murti",
            "Botanical Garden"
        ],
        "buses": GR01_BUSES
    }
]

def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    y = math.sin(delta_lon) * math.cos(lat2)
    x = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
        * 0 + math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon) * -1
    )
    x = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
    )
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def calculate_bearing_difference(a, b):
    difference = abs(a - b)
    return 360 - difference if difference > 180 else difference

def get_direction_name(bearing):
    directions = [
        "North", "North-East", "East", "South-East",
        "South", "South-West", "West", "North-West"
    ]
    return directions[int((bearing + 22.5) // 45) % 8]

def route_applies(bus_id, route):
    return bus_id in route["buses"]

def nearest_segment(latitude, longitude, route):
    best = None
    latitude_scale = 111.32
    longitude_scale = 111.32 * math.cos(math.radians(latitude))

    for index in range(len(route["points"]) - 1):
        a_name = route["points"][index]
        b_name = route["points"][index + 1]

        a = LANDMARKS[a_name]
        b = LANDMARKS[b_name]

        ax = (a[1] - longitude) * longitude_scale
        ay = (a[0] - latitude) * latitude_scale
        bx = (b[1] - longitude) * longitude_scale
        by = (b[0] - latitude) * latitude_scale

        dx = bx - ax
        dy = by - ay
        segment_length_sq = dx * dx + dy * dy

        if segment_length_sq == 0:
            projection = 0.0
        else:
            projection = max(0.0, min(1.0, -(ax * dx + ay * dy) / segment_length_sq))

        px = ax + projection * dx
        py = ay + projection * dy
        segment_distance = math.hypot(px, py)

        candidate = {
            "index": index,
            "from": a_name,
            "to": b_name,
            "distance": segment_distance,
            "projection": projection
        }

        if best is None or candidate["distance"] < best["distance"]:
            best = candidate

    return best

def _history_movement_bearing(history):
    if len(history) < 2:
        return None

    for index in range(len(history) - 1, 0, -1):
        previous = history[index - 1]
        current = history[index]
        distance_km = calculate_distance(
            previous["latitude"],
            previous["longitude"],
            current["latitude"],
            current["longitude"],
        )

        if distance_km >= 0.03:
            return calculate_bearing(
                previous["latitude"],
                previous["longitude"],
                current["latitude"],
                current["longitude"],
            )

    first = history[0]
    last = history[-1]
    distance_km = calculate_distance(
        first["latitude"],
        first["longitude"],
        last["latitude"],
        last["longitude"],
    )

    if distance_km < 0.03:
        return None

    return calculate_bearing(
        first["latitude"],
        first["longitude"],
        last["latitude"],
        last["longitude"],
    )


def get_route_prediction(bus_id, latitude, longitude, bearing, previous_bearing=None, history_points=None):
    candidates = []

    for route in ROUTES:
        if not route_applies(bus_id, route):
            continue

        route_points = route["points"]
        route_bearings = []

        for index in range(len(route_points) - 1):
            a = LANDMARKS[route_points[index]]
            b = LANDMARKS[route_points[index + 1]]
            route_bearings.append(
                calculate_bearing(a[0], a[1], b[0], b[1])
            )

        history_indices = []

        if history_points:
            recent_points = list(history_points)[-10:]

            for point in recent_points:
                best_index = None
                best_distance = None

                for candidate_index in range(len(route_points) - 1):
                    candidate_segment = nearest_segment(
                        point["latitude"],
                        point["longitude"],
                        {"points": route_points[candidate_index:candidate_index + 2]},
                    )

                    if (
                        best_distance is None
                        or candidate_segment["distance"] < best_distance
                    ):
                        best_distance = candidate_segment["distance"]
                        best_index = candidate_index

                if best_index is not None and best_distance <= 5.0:
                    history_indices.append(best_index)

        latest_history_index = history_indices[-1] if history_indices else None
        forward_steps = 0
        backward_steps = 0

        for previous_index, current_index in zip(history_indices, history_indices[1:]):
            delta = current_index - previous_index
            if delta > 0:
                forward_steps += delta
            elif delta < 0:
                backward_steps += abs(delta)

        for segment_index in range(len(route_points) - 1):
            segment = nearest_segment(
                latitude,
                longitude,
                {"points": route_points[segment_index:segment_index + 2]},
            )

            if not segment or segment["distance"] > 4.0:
                continue

            segment["index"] = segment_index
            segment["from"] = route_points[segment_index]
            segment["to"] = route_points[segment_index + 1]

            segment_bearing = route_bearings[segment_index]
            difference = calculate_bearing_difference(
                bearing,
                segment_bearing
            )

            score = segment["distance"] * 12 + difference / 5

            if latest_history_index is not None:
                score += min(12.0, abs(segment_index - latest_history_index) * 1.5)

            if backward_steps:
                score += min(12.0, backward_steps * 2.0)

            if forward_steps and segment_index >= (latest_history_index or 0):
                score -= min(4.0, forward_steps * 0.15)

            if previous_bearing is not None:
                turn_change = calculate_bearing_difference(
                    previous_bearing,
                    segment_bearing
                )
                score += min(turn_change, 90) / 25

            candidates.append(
                (score, route, segment, difference)
            )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    best_score, best_route, segment, difference = candidates[0]

    if difference > 90 or segment["distance"] > 4.0:
        return None

    if difference <= 30 and segment["distance"] <= 1.0:
        confidence = "High"
    elif difference <= 55 and segment["distance"] <= 2.0:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "route_id": "R1" if best_route["id"].startswith("N-R01") else (
            "GR01" if best_route["id"].startswith("GR01") else best_route["id"]
        ),
        "likely_towards": segment["to"],
        "route": best_route["name"],
        "route_confidence": confidence,
        "route_distance_km": round(segment["distance"], 2)
    }


def _infer_nearest_destination(latitude, longitude, bearing, history_points=None):
    candidates = []

    for name, (target_latitude, target_longitude) in LANDMARKS.items():
        distance_km = calculate_distance(
            latitude,
            longitude,
            target_latitude,
            target_longitude
        )

        if distance_km < 0.20 or distance_km > 15.0:
            continue

        target_bearing = calculate_bearing(
            latitude,
            longitude,
            target_latitude,
            target_longitude
        )

        difference = calculate_bearing_difference(
            bearing,
            target_bearing
        )

        if difference > 75:
            continue

        score = distance_km + (difference / 20.0)

        if history_points:
            recent_points = list(history_points)[-6:]
            aligned = 0

            for point in recent_points:
                point_distance = calculate_distance(
                    latitude,
                    longitude,
                    point["latitude"],
                    point["longitude"]
                )

                if point_distance < 0.20:
                    continue

                historical_bearing = calculate_bearing(
                    latitude,
                    longitude,
                    point["latitude"],
                    point["longitude"]
                )

                if calculate_bearing_difference(
                    historical_bearing,
                    target_bearing
                ) <= 60:
                    aligned += 1

            score -= min(1.5, aligned * 0.25)

        candidates.append(
            (score, name, distance_km, difference)
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    _, destination, distance_km, difference = candidates[0]

    if difference <= 30 and distance_km <= 8:
        confidence = "High"
    elif difference <= 50 and distance_km <= 12:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "likely_towards": destination,
        "route": "Towards " + destination,
        "route_id": None,
        "route_confidence": confidence,
        "route_distance_km": round(distance_km, 2)
    }


def _safe_speed(value):
    try:
        speed = float(value)
        return speed if math.isfinite(speed) else 0.0
    except (TypeError, ValueError):
        return 0.0


def update_bus_history(bus, history_points=None):
    bus_id = bus.get("bus_id")

    if not bus_id:
        return None

    history = list(history_points or [])

    if len(history) < 2:
        return {
            "direction": None,
            "heading": None,
            "likely_towards": None,
            "route": None,
            "route_id": None,
            "route_confidence": None,
            "route_distance_km": None,
            "movement_km": 0,
            "history_minutes": 0,
            "movement_status": "unknown"
        }

    first = history[0]
    last = history[-1]

    movement_km = calculate_distance(
        first["latitude"],
        first["longitude"],
        last["latitude"],
        last["longitude"]
    )

    history_minutes = (last["time"] - first["time"]) / 60
    current_speed = _safe_speed(bus.get("speed"))
    current_status = str(bus.get("vehicle_status") or "").strip().lower()

    bearing = _history_movement_bearing(history)

    if current_status == "stationary" or current_speed < 3:
        return {
            "direction": get_direction_name(bearing) if bearing is not None else "Stationary",
            "heading": round(bearing, 1) if bearing is not None else None,
            "likely_towards": None,
            "route": None,
            "route_id": None,
            "route_confidence": None,
            "route_distance_km": None,
            "movement_km": round(movement_km, 2),
            "history_minutes": round(history_minutes, 1),
            "movement_status": "stationary"
        }

    if movement_km < MIN_MOVEMENT_KM:
        return {
            "direction": None,
            "heading": None,
            "likely_towards": None,
            "route": None,
            "route_confidence": None,
            "route_distance_km": None,
            "movement_km": round(movement_km, 2),
            "history_minutes": round(history_minutes, 1),
            "movement_status": "stationary"
        }

    if bearing is None:
        return {
            "direction": None,
            "heading": None,
            "likely_towards": None,
            "route": None,
            "route_id": None,
            "route_confidence": None,
            "route_distance_km": None,
            "movement_km": round(movement_km, 2),
            "history_minutes": round(history_minutes, 1),
            "movement_status": "unknown"
        }

    previous_bearing = None

    if len(history) >= 3:
        previous = history[-3]
        middle = history[-2]
        previous_bearing = calculate_bearing(
            previous["latitude"],
            previous["longitude"],
            middle["latitude"],
            middle["longitude"]
        )

    prediction = get_route_prediction(
        bus_id,
        last["latitude"],
        last["longitude"],
        bearing,
        previous_bearing,
        history
    )

    result = {
        "direction": get_direction_name(bearing),
        "heading": round(bearing, 1),
        "likely_towards": None,
        "route": None,
        "route_id": None,
        "route_confidence": None,
        "route_distance_km": None,
        "movement_km": round(movement_km, 2),
        "history_minutes": round(history_minutes, 1),
        "movement_status": "moving"
    }

    if prediction:
        result.update(prediction)

    if not result.get("likely_towards"):
        destination_prediction = _infer_nearest_destination(
            last["latitude"],
            last["longitude"],
            bearing,
            history
        )
        if destination_prediction:
            result.update(destination_prediction)

    return result
