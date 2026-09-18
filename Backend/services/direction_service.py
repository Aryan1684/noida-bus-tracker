import math
import time
from collections import defaultdict, deque

from utils.distance import calculate_distance

HISTORY_SECONDS = 600
MIN_MOVEMENT_KM = 0.08

bus_history = defaultdict(deque)

LANDMARKS = {
    "Sector 90": (28.5350, 77.3890),
    "Botanical Garden": (28.5641, 77.3358),
    "Sector 37": (28.5626, 77.3402),
    "Noida City Center": (28.5745, 77.3560),
    "Sector 52": (28.5850, 77.3640),
    "Parthala": (28.6075, 77.3755),
    "Chaar Murti": (28.6020, 77.4180),
    "Ek Murti": (28.6063, 77.4337),
    "Surajpur": (28.5185, 77.4990),
    "Kasna Village": (28.4300, 77.5150),
    "Pari Chowk": (28.4652, 77.5080),
    "GIMS": (28.4400, 77.5030),
    "Noida International Airport": (28.17556, 77.60500)
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
        "name": "Sector 90 → Botanical → Ek Murti → Pari Chowk",
        "points": [
            "Sector 90",
            "Botanical Garden",
            "Ek Murti",
            "Pari Chowk"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "N-R01-RETURN",
        "name": "Pari Chowk → Ek Murti → Botanical → Sector 90",
        "points": [
            "Pari Chowk",
            "Ek Murti",
            "Botanical Garden",
            "Sector 90"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "N-R01-BOTANICAL-OUT",
        "name": "Botanical → Ek Murti → Pari Chowk",
        "points": [
            "Botanical Garden",
            "Ek Murti",
            "Pari Chowk"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "N-R01-PARI-RETURN",
        "name": "Pari Chowk → Ek Murti → Botanical",
        "points": [
            "Pari Chowk",
            "Ek Murti",
            "Botanical Garden"
        ],
        "buses": R01_BUSES
    },
    {
        "id": "GR01-OUT",
        "name": "Sector 90 → Botanical → Chaar Murti → Surajpur → Kasna Village",
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
        "name": "Kasna Village → Surajpur → Chaar Murti → Botanical → Sector 90",
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
        "name": "Botanical → Chaar Murti → Surajpur → Kasna Village",
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
        "name": "Kasna Village → Surajpur → Chaar Murti → Botanical",
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

    for index in range(len(route["points"]) - 1):
        a_name = route["points"][index]
        b_name = route["points"][index + 1]

        a = LANDMARKS[a_name]
        b = LANDMARKS[b_name]

        da = calculate_distance(latitude, longitude, a[0], a[1])
        db = calculate_distance(latitude, longitude, b[0], b[1])

        candidate = {
            "index": index,
            "from": a_name,
            "to": b_name,
            "distance": min(da, db)
        }

        if best is None or candidate["distance"] < best["distance"]:
            best = candidate

    return best

def get_route_prediction(bus_id, latitude, longitude, bearing, previous_bearing=None):
    candidates = []

    for route in ROUTES:
        if not route_applies(bus_id, route):
            continue

        segment = nearest_segment(latitude, longitude, route)
        if not segment:
            continue

        target = LANDMARKS[segment["to"]]
        target_bearing = calculate_bearing(
            latitude,
            longitude,
            target[0],
            target[1]
        )

        difference = calculate_bearing_difference(
            bearing,
            target_bearing
        )

        score = segment["distance"] * 8 + difference / 8

        if previous_bearing is not None:
            turn_change = calculate_bearing_difference(
                previous_bearing,
                target_bearing
            )
            score += min(turn_change, 90) / 20

        candidates.append(
            (score, route, segment, difference)
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    best_score, best_route, segment, difference = candidates[0]

    if difference > 75:
        return None

    confidence = "High" if difference <= 35 else "Medium"

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
        previous_bearing
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
