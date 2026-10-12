import os
import requests

from fastapi import FastAPI, Query, HTTPException, Header, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

from services.gps_service import get_cached_direct_live_buses
from services.prediction_collector import collector_running, start_collector, stop_collector
from utils.distance import calculate_distance
from services.direction_service import ROUTES, LANDMARKS
from services.analytics_service import dashboard as get_analytics_dashboard, record_consented_location, record_event, verify_admin_token
from services.gps_service import get_ingestion_stats, get_direct_snapshot_status

load_dotenv()

MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
WEB3FORMS_API = "https://api.web3forms.com/submit"
WEB3FORMS_FEEDBACK_KEY = os.getenv("WEB3FORMS_FEEDBACK_KEY")
WEB3FORMS_REPORT_KEY = os.getenv("WEB3FORMS_REPORT_KEY")


class FeedbackSubmission(BaseModel):
    rating: str = Field(max_length=20)
    feedback_type: str = Field(max_length=50)
    message: str = Field(max_length=1500)
    time: str | None = Field(default=None, max_length=80)


class ReportSubmission(BaseModel):
    bus_id: str = Field(max_length=80)
    report_type: str = Field(max_length=50)
    value: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=500)
    consent: str = Field(max_length=20)
    time: str | None = Field(default=None, max_length=80)


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
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://noidabus.netlify.app",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Cache-Control", "X-Admin-Token"],
)


@app.middleware("http")
async def disable_api_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/buses"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
def startup_live_gps_collector():
    start_collector()


@app.on_event("shutdown")
def shutdown_live_gps_collector():
    stop_collector()


@app.get("/")
def root():
    return {
        "message": "Noida Electric Bus Tracker API is running",
        "status": "ok",
        "data_source": "MARGDARSHI",
        "live_gps_collector_running": collector_running(),
        "features": {
            "nearby_buses": True,
            "gps_freshness": True,
            "route_matching": True,
            "eta_estimates": True,
            "location_search": True,
            "feedback": bool(WEB3FORMS_FEEDBACK_KEY),
            "bus_reports": bool(WEB3FORMS_REPORT_KEY),
            "admin_analytics": bool(os.getenv("ADMIN_TOKEN")),
        },
    }


@app.get("/api/livez")
async def api_livez():
    return {"status": "ok"}


@app.get("/api/health")
async def api_health():
    snapshot = get_direct_snapshot_status()
    stale_after = max(120, int(os.getenv("PREDICTION_COLLECT_INTERVAL_SECONDS", "60")) * 2)
    data_healthy = (
        snapshot["state"] == "available"
        and snapshot["snapshot_age_seconds"] is not None
        and snapshot["snapshot_age_seconds"] <= stale_after
    )
    collector_healthy = collector_running()
    return {
        "status": "ok" if data_healthy and collector_healthy else "degraded",
        "data_source": "MARGDARSHI",
        "snapshot_state": snapshot["state"],
        "snapshot_age_seconds": snapshot["snapshot_age_seconds"],
        "bus_count": snapshot["bus_count"],
        "last_feed_check_at": snapshot["last_feed_check_at"],
        "max_snapshot_age_seconds": snapshot["max_age_seconds"],
        "stale_after_seconds": stale_after,
        "database_configured": bool(os.getenv("DATABASE_URL")),
        "feedback_configured": bool(WEB3FORMS_FEEDBACK_KEY),
        "reports_configured": bool(WEB3FORMS_REPORT_KEY),
        "admin_configured": bool(os.getenv("ADMIN_TOKEN")),
        "live_gps_collector_running": collector_healthy,
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
    event_name: str = Field(max_length=80)
    path: str | None = Field(default=None, max_length=500)
    session_id: str | None = Field(default=None, max_length=100)
    visitor_id: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default="web", max_length=30)
    device_type: str | None = Field(default=None, max_length=30)
    browser: str | None = Field(default=None, max_length=50)
    os: str | None = Field(default=None, max_length=50)
    language: str | None = Field(default=None, max_length=20)
    referrer: str | None = Field(default=None, max_length=300)
    screen_width: int | None = None
    screen_height: int | None = None
    app_version: str | None = Field(default=None, max_length=40)
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

    confidence_counts = {
        "high": sum(1 for bus in buses if bus.get("position_confidence") == "high"),
        "medium": sum(1 for bus in buses if bus.get("position_confidence") == "medium"),
        "low": sum(1 for bus in buses if bus.get("position_confidence") == "low"),
    }

    return {
        "total": total,
        "live": live,
        "stationary": stationary,
        "moving": moving,
        "no_signal": no_signal,
        "gps_anomalies": anomalies,
        "predictions_available": predictions,
        "predictions_applied": corrected,
        "position_confidence_counts": confidence_counts,
        "buses": buses,
        "prediction_collector_running": collector_running(),
        "prediction_history_points_per_bus": 10,
    }


@app.get("/api/admin/ingestion")
def admin_ingestion(
    x_admin_token: str | None = Header(default=None),
):
    if not verify_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    return get_ingestion_stats()

def get_processed_buses():
    snapshot = get_direct_snapshot_status()
    buses = get_cached_direct_live_buses()
    if snapshot["state"] == "empty":
        return []
    if snapshot["state"] in {"warming", "expired"} or not buses:
        raise HTTPException(
            status_code=503,
            detail={
                "code": snapshot["state"],
                "message": (
                    "Bus data is warming up. Please retry shortly."
                    if snapshot["state"] == "warming"
                    else "The last bus snapshot has expired. Live data is temporarily unavailable."
                ),
                "snapshot_age_seconds": snapshot["snapshot_age_seconds"],
            },
        )
    return buses

@app.get("/api/buses")
def get_buses():
    buses = get_processed_buses()

    return {
        "count": len(buses),
        "feed_state": get_direct_snapshot_status()["state"],
        "buses": buses
    }

@app.get("/api/buses/nearby")
def get_nearby_buses(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(5, gt=0, le=25)
):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    buses = get_processed_buses()
    nearby_buses = []

    for source_bus in buses:
        distance = calculate_distance(
            lat,
            lon,
            source_bus["latitude"],
            source_bus["longitude"]
        )

        if distance <= radius:
            bus = dict(source_bus)
            bus["distance_km"] = round(distance, 2)
            bus["eta_minutes"] = None
            bus["eta_min"] = None
            bus["eta_max"] = None
            bus["eta_label"] = "ETA disabled"
            bus["eta_status"] = "disabled"
            nearby_buses.append(bus)

    nearby_buses.sort(key=lambda bus: bus["distance_km"])

    return {
        "count": len(nearby_buses),
        "total_buses": len(buses),
        "feed_state": get_direct_snapshot_status()["state"],
        "radius_km": radius,
        "data_source": "MARGDARSHI",
        "prediction_enabled": False,
        "buses": nearby_buses
    }


@app.get("/api/routes")
def get_routes():
    routes = []
    for route in ROUTES:
        points = []
        for name in route.get("points", []):
            coordinate = LANDMARKS.get(name)
            if coordinate:
                points.append({"name": name, "latitude": coordinate[0], "longitude": coordinate[1]})
        if len(points) >= 2:
            routes.append({"id": route.get("id"), "name": route.get("name"), "points": points})
    return {"routes": routes}


@app.get("/api/search-location")
def search_location(
    q: str = Query(..., min_length=2)
):
    if not MAPTILER_API_KEY:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "format": "jsonv2",
                    "q": q,
                    "countrycodes": "in",
                    "limit": 5,
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": "NoidaBusTracker/1.0 (independent project)",
                    "Accept": "application/json",
                },
                timeout=8,
            )
            response.raise_for_status()
            results = []
            for item in response.json():
                latitude = float(item["lat"])
                longitude = float(item["lon"])
                if not (28.10 <= latitude <= 28.80 and 77.20 <= longitude <= 77.75):
                    continue
                results.append({
                    "name": item.get("display_name", q),
                    "latitude": latitude,
                    "longitude": longitude,
                })
            return {"count": len(results), "results": results}
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            raise HTTPException(status_code=502, detail=f"Location search failed: {error}")

    url = f"https://api.maptiler.com/geocoding/{requests.utils.quote(q)}.json"

    params = {
        "key": MAPTILER_API_KEY,
        "country": "IN",
        "language": "en",
        "autocomplete": "true",
        "limit": 5,
        "proximity": "77.3910,28.5355",
        "bbox": "77.20,28.10,77.75,28.80"
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

            if not (28.10 <= coordinates[1] <= 28.80 and 77.20 <= coordinates[0] <= 77.75):
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