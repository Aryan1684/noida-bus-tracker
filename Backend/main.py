import math
import os
import requests
import threading
import time

from fastapi import FastAPI, Query, HTTPException, Header, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

from services.gps_service import get_cached_direct_live_buses, get_direct_bus_histories, refresh_direct_snapshot
from services.prediction_collector import collector_running, start_collector, stop_collector
from utils.distance import calculate_distance
from services.direction_service import ROUTES, LANDMARKS, update_bus_history
from services.analytics_service import dashboard as get_analytics_dashboard, record_consented_location, record_event, verify_admin_token, _connect as analytics_connect, _init_db as init_analytics_db, DATABASE_URL as ANALYTICS_DATABASE_URL
from services.gps_service import get_ingestion_stats, get_direct_snapshot_status

load_dotenv()

MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
WEB3FORMS_API = "https://api.web3forms.com/submit"
_location_label_cache = {}
_location_label_cache_lock = threading.Lock()
_last_nominatim_lookup_at = 0.0
LOCATION_LABEL_CACHE_SECONDS = 1800
LOCATION_LABEL_CACHE_LIMIT = 300
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
        "https://nimble-cocada-1c8db5.netlify.app",
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




class MaintenanceUpdate(BaseModel):
    enabled: bool
    message: str | None = Field(default=None, max_length=300)
    duration_minutes: int | None = Field(default=60, ge=1, le=10080)


def _ensure_maintenance_table(connection):
    if ANALYTICS_DATABASE_URL:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    message VARCHAR(300) NOT NULL DEFAULT 'We are making a few improvements. Please check back shortly.',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at BIGINT
                )
            """)
            cursor.execute("ALTER TABLE maintenance_settings ADD COLUMN IF NOT EXISTS expires_at BIGINT")
            cursor.execute("""
                INSERT INTO maintenance_settings (id, enabled)
                VALUES (1, FALSE) ON CONFLICT (id) DO NOTHING
            """)
    else:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT 'We are making a few improvements. Please check back shortly.',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at INTEGER
            )
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(maintenance_settings)").fetchall()}
        if "expires_at" not in columns:
            connection.execute("ALTER TABLE maintenance_settings ADD COLUMN expires_at INTEGER")
        connection.execute("INSERT OR IGNORE INTO maintenance_settings (id, enabled) VALUES (1, 0)")


def _maintenance_row():
    init_analytics_db()
    connection = analytics_connect()
    try:
        _ensure_maintenance_table(connection)
        connection.commit()
        with connection.cursor() if ANALYTICS_DATABASE_URL else _sqlite_cursor(connection) as cursor:
            cursor.execute("SELECT enabled, message, updated_at, expires_at FROM maintenance_settings WHERE id = 1")
            row = cursor.fetchone()
        if row is None:
            return {"enabled": False, "message": "We are making a few improvements. Please check back shortly.", "updated_at": None, "expires_at": None}
        enabled, message, updated_at, expires_at = bool(row[0]), row[1], row[2], row[3]
        now_ms = int(time.time() * 1000)
        if enabled and expires_at is not None and int(expires_at) <= now_ms:
            if ANALYTICS_DATABASE_URL:
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE maintenance_settings SET enabled = FALSE, updated_at = NOW() WHERE id = 1")
            else:
                connection.execute("UPDATE maintenance_settings SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE id = 1")
            connection.commit()
            enabled = False
        return {"enabled": enabled, "message": message, "updated_at": str(updated_at), "expires_at": int(expires_at) if expires_at is not None else None}
    finally:
        connection.close()


def read_maintenance_settings():
    return _maintenance_row()


class _sqlite_cursor:
    def __init__(self, connection):
        self.connection = connection
    def __enter__(self):
        self.cursor = self.connection.cursor()
        return self.cursor
    def __exit__(self, exc_type, exc, tb):
        self.cursor.close()


def write_maintenance_settings(enabled: bool, message: str | None, duration_minutes: int | None = 60):
    init_analytics_db()
    connection = analytics_connect()
    clean_message = (message or "We are making a few improvements. Please check back shortly.").strip()[:300]
    if not clean_message:
        clean_message = "We are making a few improvements. Please check back shortly."
    expires_at = int(time.time() * 1000) + int(duration_minutes or 60) * 60 * 1000 if enabled else None
    try:
        _ensure_maintenance_table(connection)
        if ANALYTICS_DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO maintenance_settings (id, enabled, message, updated_at, expires_at)
                    VALUES (1, %s, %s, NOW(), %s)
                    ON CONFLICT (id) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        message = EXCLUDED.message,
                        updated_at = NOW(),
                        expires_at = EXCLUDED.expires_at
                """, (enabled, clean_message, expires_at))
        else:
            connection.execute("""
                INSERT INTO maintenance_settings (id, enabled, message, updated_at, expires_at)
                VALUES (1, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled = excluded.enabled,
                    message = excluded.message,
                    updated_at = CURRENT_TIMESTAMP,
                    expires_at = excluded.expires_at
            """, (1 if enabled else 0, clean_message, expires_at))
        connection.commit()
    finally:
        connection.close()
    return read_maintenance_settings()


@app.get("/api/maintenance")
def public_maintenance_status():
    return read_maintenance_settings()


@app.get("/api/admin/maintenance")
def admin_maintenance_status(x_admin_token: str | None = Header(default=None)):
    if not verify_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return read_maintenance_settings()


@app.post("/api/admin/maintenance")
def admin_update_maintenance(payload: MaintenanceUpdate, x_admin_token: str | None = Header(default=None)):
    if not verify_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return write_maintenance_settings(payload.enabled, payload.message, payload.duration_minutes)

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
    period: str | None = Query(default=None, max_length=5),
    days: int | None = Query(default=None, ge=1, le=365),
    x_admin_token: str | None = Header(default=None),
):
    if not verify_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    hour_windows = {"12h": 12, "24h": 24, "36h": 36, "48h": 48}
    day_windows = {"7d": 7, "15d": 15, "30d": 30, "180d": 180, "365d": 365}

    if period in hour_windows:
        return get_analytics_dashboard(hours=hour_windows[period])
    if period in day_windows:
        return get_analytics_dashboard(days=day_windows[period])
    if period is not None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported reporting window. Use 12h, 24h, 36h, 48h, 7d, 15d, 30d, 180d or 365d.",
        )

    return get_analytics_dashboard(days=days or 30)


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
    sample_time = time.time()
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
        if sample_time - 1800 <= point_time <= sample_time + 5:
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

    return history[-36:], sample_time


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
    histories = get_direct_bus_histories(bus_ids, limit=36)
    try:
        from services.ml_prediction_service import load_histories
        stored_histories = load_histories(bus_ids)
        for bus_id, points in stored_histories.items():
            combined = {}
            for point in list(histories.get(bus_id, [])) + list(points or []):
                key = (
                    round(float(point.get("time", 0)), 1),
                    round(float(point.get("latitude", 0)), 6),
                    round(float(point.get("longitude", 0)), 6),
                )
                combined[key] = point
            histories[bus_id] = sorted(combined.values(), key=lambda point: float(point.get("time", 0)))[-36:]
    except Exception as error:
        print(f"Stored GPS history unavailable; using in-memory recent fixes: {error}", flush=True)

    for bus in buses:
        bus_id = str(bus.get("bus_id") or "").strip().upper()
        history, _sample_time = _recent_bus_history(bus, histories.get(bus_id, []))
        bus["history_points_used"] = len(history)
        bus["history_span_minutes"] = round((history[-1]["time"] - history[0]["time"]) / 60, 1) if len(history) >= 2 else 0

        latitude = _finite_bus_number(bus.get("latitude"))
        longitude = _finite_bus_number(bus.get("longitude"))
        if latitude is not None and longitude is not None:
            place = _nearest_landmark_label(latitude, longitude)
            bus["nearby_place"] = place["label"]
            bus["nearby_place_source"] = place["source"]
            bus["nearby_landmark"] = place.get("landmark")

        if len(history) >= 2:
            movement = update_bus_history(bus, history)
            if movement:
                bus.update(movement)

        speed = _finite_bus_number(bus.get("speed"))
        status = str(bus.get("vehicle_status") or "").strip().lower()
        if status != "no_signal" and speed is not None and speed >= 3:
            bus["movement_status"] = "moving"
        elif status != "no_signal" and speed is not None and speed <= 1.5 and len(history) >= 2:
            bus["movement_status"] = "stationary"

        bus["last_passed_stop"] = bus.get("last_passed_stop") or bus.get("last_stop")
        bus["likely_next_stop"] = bus.get("likely_next_stop") or bus.get("likely_towards")
        _set_eta_estimate(bus, history)

    return buses


def _nearest_landmark_label(latitude, longitude):
    candidates = []
    for name, (point_latitude, point_longitude) in LANDMARKS.items():
        distance = calculate_distance(latitude, longitude, point_latitude, point_longitude)
        candidates.append((distance, name))
    candidates.sort(key=lambda item: item[0])

    distance, name = candidates[0] if candidates else (None, None)
    is_greater_noida_west = 28.58 <= latitude <= 28.66 and 77.36 <= longitude <= 77.47
    area = "Greater Noida West" if is_greater_noida_west else "Noida / Greater Noida"

    if name and distance is not None and distance <= 2.5:
        return {"label": f"Near {name}, {area}", "source": "route_landmark", "landmark": name, "distance_km": round(distance, 2)}
    return {"label": area, "source": "area_fallback", "landmark": name, "distance_km": round(distance, 2) if distance is not None else None}


def _normalise_place_label(name, locality, latitude, longitude):
    name = " ".join(str(name or "").replace(",", " ").split()).strip()
    locality = " ".join(str(locality or "").replace(",", " ").split()).strip()
    fallback = _nearest_landmark_label(latitude, longitude)
    is_greater_noida_west = 28.58 <= latitude <= 28.66 and 77.36 <= longitude <= 77.47
    area = "Greater Noida West" if is_greater_noida_west else ""

    if not name or name.lower() in {"road", "residential area", "unnamed road", "unknown"}:
        return fallback["label"]
    if area and locality and area.casefold() not in locality.casefold():
        locality = locality + ", " + area
    elif area and not locality:
        locality = area
    if locality and locality.casefold() != name.casefold():
        return f"Near {name}, {locality}"
    return f"Near {name}"


def _fetch_reverse_place_label(latitude, longitude):
    if MAPTILER_API_KEY:
        try:
            url = f"https://api.maptiler.com/geocoding/{longitude},{latitude}.json"
            response = requests.get(
                url,
                params={"key": MAPTILER_API_KEY, "language": "en", "limit": 1},
                headers={"Accept": "application/json"},
                timeout=4,
            )
            response.raise_for_status()
            features = response.json().get("features", [])
            if features:
                feature = features[0]
                properties = feature.get("properties", {})
                name = feature.get("text") or properties.get("name") or feature.get("place_name", "").split(",")[0]
                context_items = feature.get("context", []) or []
                locality = next((str(item.get("text") or "") for item in context_items if any(token in str(item.get("id") or "") for token in ("neighborhood", "locality", "place", "district"))), "")
                label = _normalise_place_label(name, locality, latitude, longitude)
                if label:
                    return {"label": label, "source": "reverse_geocoded", "landmark": None}
        except (requests.RequestException, ValueError, TypeError, KeyError) as error:
            print(f"MapTiler reverse lookup unavailable: {error}", flush=True)

    global _last_nominatim_lookup_at
    now = time.time()
    with _location_label_cache_lock:
        can_query_nominatim = now - _last_nominatim_lookup_at >= 1.0
        if can_query_nominatim:
            _last_nominatim_lookup_at = now

    if can_query_nominatim:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "jsonv2",
                    "lat": latitude,
                    "lon": longitude,
                    "zoom": 18,
                    "addressdetails": 1,
                    "namedetails": 1,
                },
                headers={
                    "User-Agent": "NoidaBusTracker/1.0 (independent project)",
                    "Accept": "application/json",
                },
                timeout=4,
            )
            response.raise_for_status()
            data = response.json()
            address = data.get("address", {}) or {}
            name = (
                data.get("name")
                or address.get("amenity")
                or address.get("shop")
                or address.get("tourism")
                or address.get("leisure")
                or address.get("building")
            )
            if not name:
                named = data.get("namedetails", {}) or {}
                name = named.get("name:en") or named.get("name")
            locality = (
                address.get("neighbourhood")
                or address.get("suburb")
                or address.get("residential")
                or address.get("quarter")
                or address.get("city_district")
                or address.get("town")
                or address.get("city")
            )
            if not name:
                parts = [part.strip() for part in str(data.get("display_name") or "").split(",") if part.strip()]
                name = parts[0] if parts else ""
                if not locality and len(parts) > 1:
                    locality = parts[1]
            if name:
                return {
                    "label": _normalise_place_label(name, locality, latitude, longitude),
                    "source": "reverse_geocoded",
                    "landmark": None,
                }
        except (requests.RequestException, ValueError, TypeError, KeyError) as error:
            print(f"Reverse geocoding unavailable: {error}", flush=True)

    return _nearest_landmark_label(latitude, longitude)


@app.get("/api/location-label")
def get_location_label(
    lat: float = Query(...),
    lon: float = Query(...),
):
    if not (28.10 <= lat <= 28.80 and 77.20 <= lon <= 77.75):
        raise HTTPException(status_code=400, detail="Coordinates are outside the supported area")

    key = (round(lat, 4), round(lon, 4))
    now = time.time()
    with _location_label_cache_lock:
        cached = _location_label_cache.get(key)
        if cached and now - cached["cached_at"] <= LOCATION_LABEL_CACHE_SECONDS:
            return {**cached["result"], "cached": True}

    result = _fetch_reverse_place_label(lat, lon)
    result.update({"latitude": lat, "longitude": lon})
    with _location_label_cache_lock:
        _location_label_cache[key] = {"cached_at": now, "result": result}
        if len(_location_label_cache) > LOCATION_LABEL_CACHE_LIMIT:
            oldest = sorted(_location_label_cache, key=lambda item: _location_label_cache[item]["cached_at"])
            for stale_key in oldest[:len(oldest) - LOCATION_LABEL_CACHE_LIMIT]:
                _location_label_cache.pop(stale_key, None)

    return {**result, "cached": False}


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