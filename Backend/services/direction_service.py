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
    "Golf Course": (28.5678, 77.3420),
    "Sector 37": (28.5626, 77.3402),
    "Noida City Center": (28.5745, 77.3560),
    "Hoshiyarpur": (28.5925, 77.3575),
    "Sector 51": (28.5855, 77.3608),
    "Sector 52": (28.5850, 77.3640),
    "Parthala": (28.6075, 77.3755),
    "Gaur Chowk": (28.6150, 77.4350),
    "Chaar Murti": (28.6020, 77.4180),
    "Ek Murti": (28.6063, 77.4337),
    "Surajpur Collectorate": (28.5095, 77.4770),
    "Surajpur": (28.5185, 77.4990),
    "Kasna Village": (28.4300, 77.5150),
    "Pari Chowk": (28.4652, 77.5080),
    "GIMS": (28.4400, 77.5030),
    "Noida International Airport": (28.17556, 77.60500)
}



CITY_ROUTES = {
    "R1": {
        "name": "Botanical Garden → Pari Chowk via Surajpur",
        "stops": [
            "Botanical Garden", "Golf Course", "Noida City Center",
            "Hoshiyarpur", "Sector 51", "Parthala", "Gaur Chowk",
            "Ek Murti", "Surajpur Collectorate", "Pari Chowk"
        ]
    },
    "R2": {
        "name": "Botanical Garden → Jewar Airport",
        "stops": [
            "Botanical Garden", "Sector 44", "Chhalera", "Amity School",
            "Expressway", "Pari Chowk", "Galgotias University",
            "Dankaur", "Rabupura", "Jewar Airport"
        ]
    },
    "R3": {
        "name": "Botanical Garden → Surajpur via Sector 37",
        "stops": [
            "Botanical Garden", "Sector 37", "Chhalera", "Agahpur",
            "Barola", "Sector 50", "Sector 75", "Sector 75 North",
            "Sector 116", "Sector 78", "Samshang Phase 2",
            "Phulmundi", "Kulesara", "Surajpur"
        ]
    },
    "R4": {
        "name": "Botanical Garden → New Bus Adda Ghaziabad",
        "stops": [
            "Botanical Garden", "Golf Course", "Noida City Center",
            "Sector 52", "Sain Mandir", "Sector 61", "Sector 62",
            "Pratap Vihar Ghaziabad", "RRTS Ghaziabad", "New Bus Adda Ghaziabad"
        ]
    },
    "R5": {
        "name": "Botanical Garden → Anand Vihar Bus Station",
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
        "name": "Sector 90 → Botanical → Ek Murti → Pari Chowk",
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
        "name": "Pari Chowk → Ek Murti → Botanical → Sector 90",
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
        "name": "Botanical → Ek Murti → Pari Chowk",
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
        "name": "Pari Chowk → Ek Murti → Botanical",
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

def get_route_prediction(bus_id, latitude, longitude, bearing, previous_bearing=None, history_points=None):
    candidates = []

    for route in ROUTES:
        if not route_applies(bus_id, route):
            continue

        segment = nearest_segment(latitude, longitude, route)
        if not segment or segment["distance"] > 2.5:
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

        score = segment["distance"] * 10 + difference / 6

        if history_points:
            recent_points = list(history_points)[-5:]
            matched = 0
            jumps = 0
            previous_index = None

            for point in recent_points:
                history_segment = nearest_segment(
                    point["latitude"],
                    point["longitude"],
                    route
                )
                if history_segment["distance"] <= 3.0:
                    matched += 1
                    if previous_index is not None and abs(history_segment["index"] - previous_index) > 2:
                        jumps += 1
                    previous_index = history_segment["index"]

            history_ratio = matched / len(recent_points)
            score += (1 - history_ratio) * 18 + jumps * 4
            if history_ratio < 0.4:
                continue

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

    if difference > 70 or segment["distance"] > 2.0:
        return None

    confidence = "High" if difference <= 30 and segment["distance"] <= 0.8 else "Medium"

    return {
        "route_id": best_route["id"].split("-")[1] if "-" in best_route["id"] else best_route["id"],
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
            "route_id": None,
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
        "history_minutes": round(history_minutes, 1)
    }

    if prediction:
        result.update(prediction)

    return result
