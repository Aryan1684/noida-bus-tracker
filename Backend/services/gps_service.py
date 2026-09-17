import requests

from services.direction_service import update_bus_history

GPS_API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"


def get_noida_electric_buses():
    response = requests.post(
        GPS_API_URL,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    buses = []

    for bus in data:
        if bus.get("depot_name") != "NOIDA ELECTRIC":
            continue

        latitude = bus.get("latitude")
        longitude = bus.get("longitude")

        if latitude is None or longitude is None:
            continue

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError):
            continue

        result = {
            "bus_id": bus.get("bus_id"),
            "latitude": latitude,
            "longitude": longitude,
            "speed": bus.get("speed"),
            "timestamp": bus.get("timestamp"),
            "vehicle_status": bus.get("vehicle_status")
        }

        direction = update_bus_history(result)

        if direction:
            result.update(direction)

        buses.append(result)

    return buses