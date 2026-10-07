import os
import requests

from fastapi import FastAPI, Query, HTTPException, Header
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from services.gps_service import get_noida_electric_buses
from services.prediction_collector import collector_running, start_collector, stop_collector
from utils.distance import calculate_distance
from services.eta_service import calculate_eta
from services.analytics_service import dashboard as get_analytics_dashboard, record_consented_location, record_event, verify_admin_token

load_dotenv()

MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
WEB3FORMS_API = "https://api.web3forms.com/submit"
WEB3FORMS_FEEDBACK_KEY = os.getenv("WEB3FORMS_FEEDBACK_KEY")
WEB3FORMS_REPORT_KEY = os.getenv("WEB3FORMS_REPORT_KEY")


class FeedbackSubmission(BaseModel):
    rating: str
    feedback_type: str
    message: str
    time: str | None = None


class ReportSubmission(BaseModel):
    bus_id: str
    report_type: str
    value: str | None = None
    note: str | None = None
    consent: str
    time: str | None = None


def submit_web3forms(access_key: str | None, payload: dict):
    if not access_key:
        raise HTTPException(status_code=500, detail="Web3Forms is not configured")

    try:
        response = requests.post(
            WEB3FORMS_API,
            json={"access_key": access_key, **payload},
            headers={"Accept": "application/json"},
            timeout=10
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        raise HTTPException(status_code=502, detail="Unable to reach Web3Forms")

    if not response.ok or not data.get("success"):
        raise HTTPException(status_code=502, detail=data.get("message", "Web3Forms submission failed"))

    return {"success": True}

app = FastAPI(title="Noida Electric Bus Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_prediction_collector():
    start_collector()


@app.on_event("shutdown")
def shutdown_prediction_collector():
    stop_collector()


@app.get("/")
def root():
    return {
        "message": "Noida Electric Bus Tracker API is running",
        "prediction_collector_running": collector_running()
    }


@app.post("/api/feedback")
def submit_feedback(payload: FeedbackSubmission):
    return submit_web3forms(WEB3FORMS_FEEDBACK_KEY, {
        "subject": "Noida Bus Tracker - Feedback",
        "from_name": "Noida Bus Tracker",
        "rating": payload.rating,
        "feedback_type": payload.feedback_type,
        "message": payload.message,
        "time": payload.time or ""
    })


@app.post("/api/report")
def submit_report(payload: ReportSubmission):
    return submit_web3forms(WEB3FORMS_REPORT_KEY, {
        "subject": "Noida Bus Tracker - Bus Report",
        "from_name": "Noida Bus Tracker",
        "bus_id": payload.bus_id,
        "report_type": payload.report_type,
        "value": payload.value or "",
        "note": payload.note or "",
        "consent": payload.consent,
        "time": payload.time or ""
    })


class AnalyticsEvent(BaseModel):
    event_name: str
    path: str | None = None
    session_id: str | None = None
    visitor_id: str | None = None
    source: str | None = "web"
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
    language: str | None = None
    referrer: str | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    app_version: str | None = None
    metadata: dict | None = None


class AnalyticsLocation(BaseModel):
    latitude: float
    longitude: float
    path: str | None = None
    session_id: str | None = None
    visitor_id: str | None = None
    source: str | None = "web"


@app.post("/api/analytics/event")
def analytics_event(payload: AnalyticsEvent):
    accepted = record_event(
        payload.event_name,
        path=payload.path,
        session_id=payload.session_id,
        visitor_id=payload.visitor_id,
        source=payload.source or "web",
        device_type=payload.device_type,
        browser=payload.browser,
        os_name=payload.os,
        language=payload.language,
        referrer=payload.referrer,
        screen_width=payload.screen_width,
        screen_height=payload.screen_height,
        app_version=payload.app_version,
        metadata=payload.metadata,
    )
    return {"success": accepted}


@app.post("/api/analytics/location")
def analytics_location(payload: AnalyticsLocation):
    if not (-90 <= payload.latitude <= 90 and -180 <= payload.longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    return {
        "success": record_consented_location(
            payload.latitude,
            payload.longitude,
            path=payload.path,
            session_id=payload.session_id,
            visitor_id=payload.visitor_id,
            source=payload.source or "web",
        )
    }


@app.get("/api/admin/analytics")
def admin_analytics(
    days: int = Query(30, ge=1, le=365),
    x_admin_token: str | None = Header(default=None),
):
    if not verify_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    return get_analytics_dashboard(days)


@app.get("/api/admin/fleet")
def admin_fleet(
    x_admin_token: str | None = Header(default=None),
):
    if not verify_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    buses = get_processed_buses()

    total = len(buses)
    live = sum(1 for bus in buses if bus.get("vehicle_status") == "live")
    stationary = sum(1 for bus in buses if bus.get("vehicle_status") == "stationary")
    moving = sum(
        1 for bus in buses
        if bus.get("vehicle_status") == "live" and (float(bus.get("speed") or 0) > 3)
    )
    no_signal = sum(1 for bus in buses if bus.get("vehicle_status") == "no_signal")
    anomalies = sum(1 for bus in buses if bus.get("gps_anomaly"))
    predictions = sum(1 for bus in buses if bus.get("prediction_available"))
    corrected = sum(1 for bus in buses if bus.get("prediction_applied"))

    confidence_values = [
        float(bus["prediction_confidence"])
        for bus in buses
        if bus.get("prediction_available") and bus.get("prediction_confidence") is not None
    ]

    return {
        "total": total,
        "live": live,
        "stationary": stationary,
        "moving": moving,
        "no_signal": no_signal,
        "gps_anomalies": anomalies,
        "predictions_available": predictions,
        "predictions_applied": corrected,
        "average_prediction_confidence": round(
            sum(confidence_values) / len(confidence_values),
            3,
        ) if confidence_values else None,
        "buses": buses,
        "prediction_collector_running": collector_running(),
        "prediction_history_points_per_bus": 10,
    }


def get_processed_buses():
    buses = get_noida_electric_buses()

    if not buses:
        raise HTTPException(
            status_code=503,
            detail="Live bus data is not ready yet"
        )

    return buses


@app.get("/api/buses")
def get_buses():
    buses = get_processed_buses()

    return {
        "count": len(buses),
        "buses": buses
    }


@app.get("/api/buses/nearby")
def get_nearby_buses(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(5, gt=0, le=25)
):
    buses = get_processed_buses()

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
            bus.update(calculate_eta(bus, lat, lon))
            nearby_buses.append(bus)

    nearby_buses.sort(
        key=lambda bus: (
            0 if bus.get("eta_status") == "estimated" else
            1 if bus.get("eta_status") == "unavailable" else 2,
            bus.get("eta_minutes") if bus.get("eta_minutes") is not None else 9999,
            bus["distance_km"],
        )
    )

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
        "proximity": "77.3910,28.5355",
        "bbox": "77.20,28.35,77.65,28.80"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=8
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