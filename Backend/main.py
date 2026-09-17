import os
import requests

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from services.gps_service import get_noida_electric_buses
from utils.distance import calculate_distance

load_dotenv()

MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")

app = FastAPI(title="Noida Electric Bus Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Noida Electric Bus Tracker API is running"
    }


@app.get("/api/buses")
def get_buses():
    buses = get_noida_electric_buses()

    return {
        "count": len(buses),
        "buses": buses
    }


@app.get("/api/buses/nearby")
def get_nearby_buses(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(5)
):
    buses = get_noida_electric_buses()

    nearby_buses = []

    for bus in buses:
        distance = calculate_distance(
            lat,
            lon,
            bus["latitude"],
            bus["longitude"]
        )

        if distance <= radius:
            bus["distance_km"] = round(distance, 2)
            nearby_buses.append(bus)

    nearby_buses.sort(key=lambda bus: bus["distance_km"])

    return {
        "count": len(nearby_buses),
        "radius_km": radius,
        "buses": nearby_buses
    }


@app.get("/api/search-location")
def search_location(
    q: str = Query(..., min_length=2)
):
    if not MAPTILER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="MAPTILER_API_KEY is missing"
        )

    url = f"https://api.maptiler.com/geocoding/{requests.utils.quote(q)}.json"

    params = {
        "key": MAPTILER_API_KEY,
        "country": "IN",
        "language": "en",
        "autocomplete": "true",
        "limit": 5,
        "proximity": "77.3910,28.5355"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=999
        )

        response.raise_for_status()

        data = response.json()

        results = []

        for feature in data.get("features", []):
            coordinates = feature.get("geometry", {}).get("coordinates", [])

            if len(coordinates) < 2:
                continue

            properties = feature.get("properties", {})

            name = properties.get("name", "")
            place_formatted = properties.get("place_formatted", "")

            if place_formatted and name:
                label = f"{name}, {place_formatted}"
            else:
                label = name or place_formatted or feature.get("place_name", "")

            results.append({
                "name": label,
                "latitude": coordinates[1],
                "longitude": coordinates[0]
            })

        return {
            "count": len(results),
            "results": results
        }

    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"MapTiler request failed: {str(error)}"
        )