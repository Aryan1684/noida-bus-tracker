import math
import time
from collections import defaultdict, deque

from utils.distance import calculate_distance

HISTORY_SECONDS = 240
MIN_MOVEMENT_KM = 0.08

bus_history = defaultdict(deque)

ROUTE_POINTS = [
    {
        "name": "Parthala",
        "latitude": 28.6075,
        "longitude": 77.3755
    },
    {
        "name": "Gaur Chowk",
        "latitude": 28.6155,
        "longitude": 77.4065
    },
    {
        "name": "Ek Murti",
        "latitude": 28.6063,
        "longitude": 77.4337
    },
    {
        "name": "Surajpur",
        "latitude": 28.5185,
        "longitude": 77.4990
    },
    {
        "name": "Pari Chowk",
        "latitude": 28.4652,
        "longitude": 77.5080
    }
]


def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    y = math.sin(delta_lon) * math.cos(lat2)

    x = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1)
        * math.cos(lat2)
        * math.cos(delta_lon)
    )

    bearing = math.degrees(
        math.atan2(y, x)
    )

    return (bearing + 360) % 360


def calculate_bearing_difference(a, b):
    difference = abs(a - b)

    if difference > 180:
        difference = 360 - difference

    return difference


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

    index = int(
        (bearing + 22.5) // 45
    ) % 8

    return directions[index]


def get_nearest_route_point(latitude, longitude):
    nearest = None
    nearest_distance = float("inf")

    for point in ROUTE_POINTS:
        distance = calculate_distance(
            latitude,
            longitude,
            point["latitude"],
            point["longitude"]
        )

        if distance < nearest_distance:
            nearest_distance = distance
            nearest = point

    return nearest, nearest_distance


def get_next_route_point(
    latitude,
    longitude,
    bearing
):
    candidates = []

    for point in ROUTE_POINTS:
        distance = calculate_distance(
            latitude,
            longitude,
            point["latitude"],
            point["longitude"]
        )

        point_bearing = calculate_bearing(
            latitude,
            longitude,
            point["latitude"],
            point["longitude"]
        )

        bearing_difference = calculate_bearing_difference(
            bearing,
            point_bearing
        )

        if bearing_difference <= 70:
            candidates.append(
                (
                    bearing_difference,
                    distance,
                    point
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1]
        )
    )

    return candidates[0][2]


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

    while history and (
        now - history[0]["time"]
        > HISTORY_SECONDS
    ):
        history.popleft()

    if len(history) < 2:
        return {
            "direction": None,
            "heading": None,
            "likely_towards": None,
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

    history_minutes = (
        last["time"] -
        first["time"]
    ) / 60

    if movement_km < MIN_MOVEMENT_KM:
        return {
            "direction": None,
            "heading": None,
            "likely_towards": None,
            "movement_km": round(
                movement_km,
                2
            ),
            "history_minutes": round(
                history_minutes,
                1
            )
        }

    bearing = calculate_bearing(
        first["latitude"],
        first["longitude"],
        last["latitude"],
        last["longitude"]
    )

    next_point = get_next_route_point(
        last["latitude"],
        last["longitude"],
        bearing
    )

    return {
        "direction": get_direction_name(
            bearing
        ),
        "heading": round(
            bearing,
            1
        ),
        "likely_towards": (
            next_point["name"]
            if next_point
            else None
        ),
        "movement_km": round(
            movement_km,
            2
        ),
        "history_minutes": round(
            history_minutes,
            1
        )
    }