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
    "Chaar Murti": (28.6070, 77.4350),
    "Ek Murti": (28.6063, 77.4337),
    "Surajpur": (28.5185, 77.4990),
    "Pari Chowk": (28.4652, 77.5080),
    "GIMS": (28.4400, 77.5030),
    "Galgotias University": (28.36715, 77.54208),
    "Noida International Airport": (28.17556, 77.60500)
}

ROUTES = [
    {
        "id": "N1",
        "name": "Botanical Garden - Ek Murti - Pari Chowk",
        "points": [
            "Botanical Garden",
            "Noida City Center",
            "Parthala",
            "Ek Murti",
            "Surajpur",
            "Pari Chowk"
        ]
    },
    {
        "id": "N2",
        "name": "Botanical Garden - Pari Chowk - Airport",
        "points": [
            "Botanical Garden",
            "Pari Chowk",
            "Galgotias University",
            "Noida International Airport"
        ]
    },
    {
        "id": "N3",
        "name": "Botanical Garden - Sector 37 - Surajpur",
        "points": [
            "Botanical Garden",
            "Sector 37",
            "Surajpur"
        ]
    },
    {
        "id": "N4",
        "name": "Botanical Garden - Sector 52 - Ghaziabad",
        "points": [
            "Botanical Garden",
            "Noida City Center",
            "Sector 52"
        ]
    },
    {
        "id": "G1",
        "name": "Chaar Murti - Surajpur - Pari Chowk - Airport",
        "points": [
            "Chaar Murti",
            "Surajpur",
            "Pari Chowk",
            "Galgotias University",
            "Noida International Airport"
        ]
    },
    {
        "id": "G2",
        "name": "Chaar Murti - Surajpur - GIMS - Airport",
        "points": [
            "Chaar Murti",
            "Surajpur",
            "GIMS",
            "Galgotias University",
            "Noida International Airport"
        ]
    },
    {
        "id": "G3",
        "name": "Ek Murti - Surajpur - GIMS - Airport",
        "points": [
            "Ek Murti",
            "Surajpur",
            "GIMS",
            "Galgotias University",
            "Noida International Airport"
        ]
    },
    {
        "id": "G4",
        "name": "Makora - GIMS - Airport",
        "points": [
            "Surajpur",
            "GIMS",
            "Galgotias University",
            "Noida International Airport"
        ]
    },
    {
        "id": "Y1",
        "name": "Pari Chowk - GBU - Dankaur - Airport",
        "points": [
            "Pari Chowk",
            "GIMS",
            "Galgotias University",
            "Noida International Airport"
        ]
    },
    {
        "id": "Y2",
        "name": "Pari Chowk - Surajpur",
        "points": [
            "Pari Chowk",
            "Surajpur"
        ]
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
        "North",
        "North-East",
        "East",
        "South-East",
        "South",
        "South-West",
        "West",
        "North-West"
    ]
    return directions[int((bearing + 22.5) // 45) % 8]

def get_nearest_landmark(latitude, longitude):
    nearest = None
    nearest_distance = float("inf")

    for name, coordinates in LANDMARKS.items():
        distance = calculate_distance(
            latitude,
            longitude,
            coordinates[0],
            coordinates[1]
        )

        if distance < nearest_distance:
            nearest_distance = distance
            nearest = name

    return nearest, nearest_distance

def get_route_candidates(latitude, longitude, bearing):
    candidates = []

    for route in ROUTES:
        points = route["points"]

        for index, name in enumerate(points[:-1]):
            if name not in LANDMARKS or points[index + 1] not in LANDMARKS:
                continue

            next_name = points[index + 1]
            next_coordinates = LANDMARKS[next_name]

            distance = calculate_distance(
                latitude,
                longitude,
                next_coordinates[0],
                next_coordinates[1]
            )

            target_bearing = calculate_bearing(
                latitude,
                longitude,
                next_coordinates[0],
                next_coordinates[1]
            )

            difference = calculate_bearing_difference(
                bearing,
                target_bearing
            )

            if difference <= 75:
                candidates.append({
                    "route": route,
                    "next": next_name,
                    "distance": distance,
                    "bearing_difference": difference
                })

    candidates.sort(
        key=lambda item: (
            item["bearing_difference"],
            item["distance"]
        )
    )

    return candidates

def get_route_prediction(latitude, longitude, bearing):
    candidates = get_route_candidates(latitude, longitude, bearing)

    if not candidates:
        return None

    best = candidates[0]
    agreeing_routes = [
        item for item in candidates
        if item["next"] == best["next"]
        and item["bearing_difference"] <= 45
    ]

    if len(agreeing_routes) >= 2:
        confidence = "High"
    elif len(candidates) >= 2:
        confidence = "Medium"
    else:
        confidence = "Medium"

    return {
        "likely_towards": best["next"],
        "route": best["route"]["name"],
        "route_confidence": confidence,
        "route_distance_km": round(best["distance"], 2)
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
