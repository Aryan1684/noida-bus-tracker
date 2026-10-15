import math
import os
import requests
import time

from fastapi import FastAPI, Query, HTTPException, Header, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

from services.gps_service import get_cached_direct_live_buses, refresh_direct_snapshot
from services.prediction_collector import collector_running, start_collector, stop_collector
from utils.distance import calculate_distance
from services.direction_service import ROUTES, LANDMARKS, update_bus_history
from services.ml_prediction_service import load_histories
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
            "movement_prediction": True,
            "last_stop_estimates": True,
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
    stale_after = max(120, int(os.getenv("GPS_REFRESH_INTERVAL_SECONDS", "60")) * 2)
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
        "live_gps_collector_running": collector_running(),
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
        try:
            buses = refresh_direct_snapshot()
        except Exception as error:
            print(f"Direct GPS refresh failed: {error}", flush=True)
            buses = get_cached_direct_live_buses()

        if buses:
            return buses

        snapshot = get_direct_snapshot_status()
        raise HTTPException(
            status_code=503,
            detail={
                "code": snapshot["state"],
                "message": "Live bus data is temporarily unavailable. Please retry shortly.",
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


def _finite_bus_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _recent_bus_history(bus, stored_history):
    age_seconds = _finite_bus_number(bus.get("gps_age_seconds"))
    sample_time = time.time() - max(0.0, age_seconds or 0.0)
    try:
        latitude = float(bus.get("latitude"))
        longitude = float(bus.get("longitude"))
        speed = max(0.0, float(bus.get("speed") or 0.0))
    except (TypeError, ValueError):
        return [], sample_time

    history = []
    for point in stored_history or []:
        try:
            point_time = float(point.get("time"))
            point_lat = float(point.get("latitude"))
            point_lon = float(point.get("longitude"))
            point_speed = max(0.0, float(point.get("speed") or 0.0))
        except (TypeError, ValueError, AttributeError):
            continue

        if not all(math.isfinite(value) for value in (point_time, point_lat, point_lon, point_speed)):
            continue
        if not (-90 <= point_lat <= 90 and -180 <= point_lon <= 180):
            continue
        if sample_time - 1200 <= point_time <= sample_time + 5:
            history.append({
                "time": point_time,
                "latitude": point_lat,
                "longitude": point_lon,
                "speed": point_speed,
            })

    history.sort(key=lambda point: point["time"])
    current_point = {
        "time": sample_time,
        "latitude": latitude,
        "longitude": longitude,
        "speed": speed,
    }

    if not history:
        history.append(current_point)
    elif sample_time > history[-1]["time"] + 2:
        history.append(current_point)
    elif abs(sample_time - history[-1]["time"]) <= 2:
        history[-1] = current_point

    return history[-10:], sample_time


def _set_eta_estimate(bus, history):
    bus["eta_minutes"] = None
    bus["eta_min"] = None
    bus["eta_max"] = None
    bus["eta_status"] = "unavailable"
    bus["eta_label"] = "ETA unavailable"

    age_seconds = _finite_bus_number(bus.get("gps_age_seconds"))
    if (
        age_seconds is None
        or age_seconds > 120
        or bus.get("data_stale")
        or bus.get("is_stale")
        or str(bus.get("vehicle_status") or "").lower() == "no_signal"
    ):
        bus["eta_label"] = "ETA unavailable · GPS update delayed"
        return

    if len(history) < 3 or history[-1]["time"] - history[0]["time"] < 60:
        bus["eta_label"] = "ETA unavailable · collecting movement history"
        return

    if str(bus.get("movement_status") or "").lower() != "moving":
        bus["eta_label"] = "ETA unavailable · bus not confirmed moving"
        return

    route_id = bus.get("route_path_id") or bus.get("route_id")
    confidence = str(bus.get("route_confidence") or "").strip().lower()
    next_stop = str(bus.get("likely_towards") or "").strip()
    if not route_id or confidence not in {"high", "medium"} or next_stop not in LANDMARKS:
        bus["eta_label"] = "ETA unavailable · next stop not confirmed"
        return

    try:
        latitude = float(bus.get("latitude"))
        longitude = float(bus.get("longitude"))
    except (TypeError, ValueError):
        bus["eta_label"] = "ETA unavailable · location missing"
        return

    stop_latitude, stop_longitude = LANDMARKS[next_stop]
    distance_km = calculate_distance(latitude, longitude, stop_latitude, stop_longitude)
    if not math.isfinite(distance_km) or distance_km < 0 or distance_km > 15:
        bus["eta_label"] = "ETA unavailable · next stop distance uncertain"
        return

    if distance_km <= 0.15:
        bus["eta_minutes"] = 0
        bus["eta_min"] = 0
        bus["eta_max"] = 1
        bus["eta_status"] = "arriving"
        bus["eta_label"] = "Arriving at " + next_stop
        bus["eta_distance_km"] = round(distance_km, 2)
        return

    current_speed = _finite_bus_number(bus.get("speed"))
    valid_speeds = []
    recent_history = history[-6:]
    for previous, current in zip(recent_history, recent_history[1:]):
        elapsed = current["time"] - previous["time"]
        if elapsed < 5:
            continue
        segment_distance = calculate_distance(
            previous["latitude"],
            previous["longitude"],
            current["latitude"],
            current["longitude"],
        )
        implied_speed = segment_distance * 3600 / elapsed
        if 3 <= implied_speed <= 85:
            valid_speeds.append(implied_speed)

    if current_speed is not None and 3 <= current_speed <= 85:
        speed_kmh = current_speed
    elif valid_speeds:
        valid_speeds.sort()
        speed_kmh = valid_speeds[len(valid_speeds) // 2]
    else:
        bus["eta_label"] = "ETA unavailable · speed not reliable"
        return

    estimated_minutes = max(1, math.ceil(distance_km * 1.2 / speed_kmh * 60))
    if estimated_minutes > 120:
        bus["eta_label"] = "ETA unavailable · travel time uncertain"
        return

    bus["eta_minutes"] = estimated_minutes
    bus["eta_min"] = max(1, math.floor(estimated_minutes * 0.8))
    bus["eta_max"] = max(estimated_minutes, math.ceil(estimated_minutes * 1.4))
    bus["eta_status"] = "estimated"
    bus["eta_label"] = "~" + str(estimated_minutes) + " min to " + next_stop
    bus["eta_distance_km"] = round(distance_km, 2)
    bus["eta_speed_kmh"] = round(speed_kmh, 1)


def _enrich_nearby_buses_with_history(buses):
    if not buses:
        return buses

    bus_ids = [str(bus.get("bus_id") or "").strip().upper() for bus in buses if bus.get("bus_id")]
    try:
        histories = load_histories(bus_ids)
    except Exception as error:
        print(f"Movement history unavailable; serving live GPS without route estimates: {error}", flush=True)
        histories = {}

    for bus in buses:
        bus_id = str(bus.get("bus_id") or "").strip().upper()
        history, _sample_time = _recent_bus_history(bus, histories.get(bus_id, []))
        bus["history_points_used"] = len(history)
        bus["history_span_minutes"] = round((history[-1]["time"] - history[0]["time"]) / 60, 1) if len(history) >= 2 else 0

        if len(history) >= 2:
            movement = update_bus_history(bus, history)
            if movement:
                bus.update(movement)

        speed = _finite_bus_number(bus.get("speed"))
        status = str(bus.get("vehicle_status") or "").strip().lower()
        if status != "no_signal" and speed is not None and speed >= 5:
            bus["movement_status"] = "moving"
        elif status != "no_signal" and len(history) < 2 and status == "stationary":
            bus["movement_status"] = "stationary"

        _set_eta_estimate(bus, history)

    return buses


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
        try:
            bus_lat = float(source_bus.get("latitude"))
            bus_lon = float(source_bus.get("longitude"))
            if not (-90 <= bus_lat <= 90 and -180 <= bus_lon <= 180):
                continue
            distance = calculate_distance(lat, lon, bus_lat, bus_lon)
        except (TypeError, ValueError, KeyError):
            continue

        if distance <= radius:
            bus = dict(source_bus)
            bus["latitude"] = bus_lat
            bus["longitude"] = bus_lon
            bus["distance_km"] = round(distance, 2)
            bus["prediction_enabled"] = False
            nearby_buses.append(bus)

    nearby_buses.sort(key=lambda bus: bus["distance_km"])
    nearby_buses = _enrich_nearby_buses_with_history(nearby_buses)

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