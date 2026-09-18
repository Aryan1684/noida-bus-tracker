import math
import time
from collections import defaultdict, deque

from utils.distance import calculate_distance

HISTORY_SECONDS = 600
MIN_MOVEMENT_KM = 0.08

bus_history = defaultdict(deque)

LANDMARKS = {
    "Botanical Garden": (28.5641, 77.3358),
    "Sector 37": (28.5626, 77.3402),
    "Noida City Center": (28.5745, 77.3560),
    "Sector 52": (28.5850, 77.3640),
    "Parthala": (28.6075, 77.3755),
    "Chaar Murti": (28.6020, 77.4180),
    "Ek Murti": (28.6063, 77.4337),
    "Surajpur": (28.5185, 77.4990),
    "Pari Chowk": (28.4652, 77.5080),
    "GIMS": (28.4400, 77.5030),
    "Galgotias University": (28.36715, 77.54208),
    "Noida International Airport": (28.17556, 77.60500)
}

ROUTES = [
    {
        "id": "R1_OUT",
        "name": "Botanical Garden → Ek Murti → Surajpur → Pari Chowk",
        "points": ["Botanical Garden", "Noida City Center", "Parthala", "Ek Murti", "Surajpur", "Pari Chowk"],
        "vehicle_prefixes": ["UP70", "UP80"]
    },
    {
        "id": "R1_RETURN",
        "name": "Pari Chowk → Surajpur → Ek Murti → Botanical Garden",
        "points": ["Pari Chowk", "Surajpur", "Ek Murti", "Parthala", "Noida City Center", "Botanical Garden"],
        "vehicle_prefixes": ["UP70", "UP80"]
    },
    {
        "id": "R2_OUT",
        "name": "Chaar Murti → Surajpur → Pari Chowk → Airport",
        "points": ["Chaar Murti", "Surajpur", "Pari Chowk", "Galgotias University", "Noida International Airport"],
        "vehicle_prefixes": ["UP14"]
    },
    {
        "id": "R2_RETURN",
        "name": "Airport → Pari Chowk → Surajpur → Chaar Murti",
        "points": ["Noida International Airport", "Galgotias University", "Pari Chowk", "Surajpur", "Chaar Murti"],
        "vehicle_prefixes": ["UP14"]
    },
    {
        "id": "R3_OUT",
        "name": "Chaar Murti → GIMS → Airport",
        "points": ["Chaar Murti", "GIMS", "Galgotias University", "Noida International Airport"],
        "vehicle_prefixes": ["UP14"]
    },
    {
        "id": "R3_RETURN",
        "name": "Airport → GIMS → Chaar Murti",
        "points": ["Noida International Airport", "Galgotias University", "GIMS", "Chaar Murti"],
        "vehicle_prefixes": ["UP14"]
    },
    {
        "id": "R4_OUT",
        "name": "Botanical Garden → Sector 37 → Surajpur",
        "points": ["Botanical Garden", "Sector 37", "Surajpur"],
        "vehicle_prefixes": ["UP70", "UP80"]
    },
    {
        "id": "R4_RETURN",
        "name": "Surajpur → Sector 37 → Botanical Garden",
        "points": ["Surajpur", "Sector 37", "Botanical Garden"],
        "vehicle_prefixes": ["UP70", "UP80"]
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

def prefix_matches(bus_id, route):
    if not bus_id:
        return False
    return any(bus_id.upper().startswith(prefix) for prefix in route["vehicle_prefixes"])

def nearest_route_segment(latitude, longitude, route):
    best = None

    for index in range(len(route["points"]) - 1):
        a_name = route["points"][index]
        b_name = route["points"][index + 1]

        if a_name not in LANDMARKS or b_name not in LANDMARKS:
            continue

        a = LANDMARKS[a_name]
        b = LANDMARKS[b_name]

        da = calculate_distance(latitude, longitude, a[0], a[1])
        db = calculate_distance(latitude, longitude, b[0], b[1])

        if best is None or min(da, db) < best["distance"]:
            best = {
                "index": index,
                "from": a_name,
                "to": b_name,
                "distance": min(da, db)
            }

    return best

def route_candidate_score(bus_id, latitude, longitude, bearing, route):
    segment = nearest_route_segment(latitude, longitude, route)

    if not segment:
        return None

    target = LANDMARKS[segment["to"]]
    target_bearing = calculate_bearing(latitude, longitude, target[0], target[1])
    bearing_difference = calculate_bearing_difference(bearing, target_bearing)

    score = segment["distance"] * 10 + bearing_difference / 10

    if prefix_matches(bus_id, route):
        score -= 8

    return score, segment, bearing_difference

def get_route_prediction(bus_id, latitude, longitude, bearing):
    candidates = []

    for route in ROUTES:
        result = route_candidate_score(
            bus_id,
            latitude,
            longitude,
            bearing,
            route
        )

        if result:
            candidates.append((result[0], route, result[1], result[2]))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    best_score, best_route, segment, bearing_difference = candidates[0]

    confidence = "Low"

    if prefix_matches(bus_id, best_route):
        confidence = "High" if bearing_difference <= 50 else "Medium"
    elif bearing_difference <= 35:
        confidence = "Medium"

    if confidence == "Low":
        return None

    return {
        "likely_towards": segment["to"],
        "route": best_route["name"],
        "route_confidence": confidence,
        "route_distance_km": round(segment["distance"], 2)
    }

def update_bus_history(bus):
    bus_id = bus.get("bus_id")

    if not bus_id:
        return None

    now = time.time()
    history = bus_history[bus_id]

    history.append({
        "latitude": bus["latitude"],
        "longitude": bus["longitude"],
        "time": now
    })

    while history and now - history[0]["time"] > HISTORY_SECONDS:
        history.popleft()

    if len(history) < 2:
        return {
            "direction": None,
            "heading": None,
            "likely_towards": None,
            "route": None,
            "route_confidence": None,
            "route_distance_km": None,
            "movement_km": 0,
            "history_minutes": 0
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

    if movement_km < MIN_MOVEMENT_KM:
        return {
            "direction": None,
            "heading": None,
            "likely_towards": None,
            "route": None,
            "route_confidence": None,
            "route_distance_km": None,
            "movement_km": round(movement_km, 2),
            "history_minutes": round(history_minutes, 1)
        }

    bearing = calculate_bearing(
        first["latitude"],
        first["longitude"],
        last["latitude"],
        last["longitude"]
    )

    prediction = get_route_prediction(
        bus_id,
        last["latitude"],
        last["longitude"],
        bearing
    )

    result = {
        "direction": get_direction_name(bearing),
        "heading": round(bearing, 1),
        "likely_towards": None,
        "route": None,
        "route_confidence": None,
        "route_distance_km": None,
        "movement_km": round(movement_km, 2),
        "history_minutes": round(history_minutes, 1)
    }

    if prediction:
        result.update(prediction)

    return result
