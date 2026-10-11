import copy
import math
import os
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import socket
import ssl
from http.client import HTTPResponse
from io import BytesIO

import dns.resolver

from services.direction_service import update_bus_history
from services.ml_prediction_service import analyze_buses, load_latest_points, load_recent_points, prepare_histories, record_ingestion_log, record_validation_audit
from services.validation_service import validate_gps_batch
from utils.distance import calculate_distance
from services.position_trust_service import match_history, match_position

GPS_API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"

_last_good_buses = []
_last_good_at = None
_latest_processed_buses = []
_latest_processed_at = None
_latest_raw_electric_buses = []
_latest_raw_electric_at = None
_cache_lock = threading.Lock()
_direct_history = {}
_direct_snapshot = []
_direct_snapshot_at = None
DIRECT_SNAPSHOT_MAX_AGE_SECONDS = max(300, int(os.getenv("DIRECT_SNAPSHOT_MAX_AGE_SECONDS", "300")))
_ingestion_stats = {
    "cycles": 0,
    "buses_received": 0,
    "buses_accepted": 0,
    "buses_rejected": 0,
    "reject_reasons": {},
    "last_cycle_at": None,
    "last_upstream_latency_ms": None,
    "last_source_health": "unknown",
    "last_avg_gps_age_seconds": None,
    "last_buses_disappeared": [],
}
_previous_seen_bus_ids = set()
_validation_last_points = {}
_identity_last_seen = {}
_identity_warnings = []
_validation_previous_points = {}
MAX_CACHE_SECONDS = 3600
PROCESSED_CACHE_SECONDS = max(120, int(int(os.getenv("PREDICTION_COLLECT_INTERVAL_SECONDS", "60")) * 2.5))

NOIDA_POLYGON = [
    (28.69, 77.28),
    (28.70, 77.39),
    (28.63, 77.49),
    (28.54, 77.47),
    (28.45, 77.38),
    (28.40, 77.30),
    (28.52, 77.27),
    (28.62, 77.24)
]

GREATER_NOIDA_POLYGON = [
    (28.63, 77.39),
    (28.62, 77.51),
    (28.55, 77.59),
    (28.45, 77.64),
    (28.34, 77.61),
    (28.30, 77.49),
    (28.33, 77.40),
    (28.45, 77.36),
    (28.54, 77.39)
]


def _point_in_polygon(latitude, longitude, polygon):
    inside = False
    j = len(polygon) - 1

    for i in range(len(polygon)):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]

        crosses = (lat_i > latitude) != (lat_j > latitude)

        if crosses:
            lon_at_lat = (
                (lon_j - lon_i) * (latitude - lat_i) / (lat_j - lat_i)
                + lon_i
            )

            if longitude < lon_at_lat:
                inside = not inside

        j = i

    return inside


def _in_noida_region(latitude, longitude):
    return (
        _point_in_polygon(latitude, longitude, NOIDA_POLYGON)
        or _point_in_polygon(latitude, longitude, GREATER_NOIDA_POLYGON)
    )


def _parse_timestamp(value):
    if not value:
        return None

    raw = str(value).strip()

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))

        if raw.upper().endswith("Z") and parsed.timestamp() > time.time() + 300:
            local_value = raw[:-1].strip()
            local_parsed = datetime.fromisoformat(local_value)
            parsed = local_parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def _fix_age_seconds(timestamp, now=None):
    event_time = _parse_timestamp(timestamp)

    if event_time is None:
        return None

    age = (time.time() if now is None else now) - event_time

    if not math.isfinite(age):
        return None

    return max(0, int(age))


def _post_with_dns_fallback(url, headers, timeout=(4, 8)):
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    try:
        return requests.post(
            url,
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as first_error:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ["1.1.1.1", "8.8.8.8"]
        resolver.lifetime = 3

        addresses = []
        for record_type in ("A", "AAAA"):
            try:
                answers = resolver.resolve(host, record_type)
                addresses.extend(str(answer) for answer in answers)
            except Exception:
                continue

        if not addresses:
            raise first_error

        body = b""
        request_headers = {
            key: value
            for key, value in headers.items()
            if key.lower() not in {"content-length", "accept-encoding"}
        }
        request_headers["Host"] = host
        request_headers["Accept-Encoding"] = "identity"
        request_headers["Content-Length"] = str(len(body))

        last_error = first_error

        for address in addresses:
            try:
                family = socket.AF_INET6 if ":" in address else socket.AF_INET
                raw_socket = socket.socket(family, socket.SOCK_STREAM)
                raw_socket.settimeout(timeout[1])
                raw_socket.connect((address, port))
                context = ssl.create_default_context()
                tls_socket = context.wrap_socket(raw_socket, server_hostname=host)

                request_lines = [f"POST {path} HTTP/1.1"]
                request_lines.extend(f"{key}: {value}" for key, value in request_headers.items())
                request_data = ("\r\n".join(request_lines) + "\r\n\r\n").encode() + body
                tls_socket.sendall(request_data)

                response = HTTPResponse(tls_socket)
                response.begin()
                payload = response.read()

                class ResponseAdapter:
                    def __init__(self, status, reason, content):
                        self.status_code = status
                        self.ok = 200 <= status < 300
                        self.content = content
                        self.reason = reason

                    def raise_for_status(self):
                        if not self.ok:
                            raise requests.HTTPError(
                                f"{self.status_code} {self.reason}"
                            )

                    def json(self):
                        import json
                        return json.loads(self.content.decode("utf-8"))

                tls_socket.close()
                return ResponseAdapter(response.status, response.reason, payload)
            except Exception as error:
                last_error = error

        raise last_error


def get_direct_live_buses(data=None):
    if data is None:
        response = _post_with_dns_fallback(
            GPS_API_URL,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://margdarshi.upsrtcvlt.com",
                "Referer": "https://margdarshi.upsrtcvlt.com/",
            },
            timeout=(4, 8),
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected MARGDARSHI response")

    latest = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        if str(item.get("depot_name") or "").strip().upper() != "NOIDA ELECTRIC":
            continue
        bus_id = str(item.get("bus_id") or "").strip().upper()
        if not bus_id:
            continue
        status = str(item.get("vehicle_status") or "").strip().lower().replace(" ", "_").replace("-", "_")
        try:
            latitude = float(item.get("latitude"))
            longitude = float(item.get("longitude"))
            speed = float(item.get("speed") or 0)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        source_status = "stationary" if status == "stationary" else "no_signal" if status in {"no_signal", "nosignal", "offline", "unavailable"} else "live"
        source_timestamp = item.get("timestamp")
        age_seconds = _fix_age_seconds(source_timestamp)
        if age_seconds is None:
            freshness = "unknown"
        elif age_seconds <= 120:
            freshness = "fresh"
        elif age_seconds <= 600:
            freshness = "delayed"
        else:
            freshness = "stale"
        bus = dict(item)
        bus.update({
            "bus_id": bus_id,
            "latitude": latitude,
            "longitude": longitude,
            "speed": max(0.0, speed) if math.isfinite(speed) else 0.0,
            "vehicle_status": source_status,
            "source_vehicle_status": item.get("vehicle_status"),
            "source_timestamp": source_timestamp,
            "gps_age_seconds": age_seconds,
            "gps_freshness": freshness,
            "is_stale": freshness in {"stale", "unknown"} or source_status == "no_signal",
            "location_label": "Last known location" if source_status == "no_signal" or freshness in {"stale", "unknown"} else "GPS location",
            "position_confidence": "high" if source_status == "live" and freshness == "fresh" else "medium" if source_status == "live" and freshness == "delayed" else "low",
            "movement_status": "unknown",
            "direction": None,
            "heading": None,
            "likely_towards": None,
            "movement_km": None,
            "history_minutes": None,
            "prediction_available": False,
            "prediction_applied": False,
            "source": "MARGDARSHI",
        })
        try:
            route_match = match_position(bus_id, latitude, longitude)
            bus.update(route_match)
        except Exception as error:
            print(f"Route matching failed for {bus_id}: {error}", flush=True)
            bus.update({
                "route_match_status": "unavailable",
                "route_match_distance_m": None,
                "route_progress": None,
                "route_match_confidence": "none",
                "matched_route_id": None,
                "matched_route": None,
                "next_stop": None,
                "next_stops": [],
            })
        event_time = _parse_timestamp(source_timestamp)
        if event_time is None or event_time > time.time() + 300:
            event_time = time.time()
        point = {
            "time": event_time,
            "timestamp": source_timestamp,
            "latitude": latitude,
            "longitude": longitude,
            "speed": bus["speed"],
        }
        with _cache_lock:
            history = _direct_history.setdefault(bus_id, [])
            while len(_direct_history) > 300:
                stale_bus_id = next(
                    (key for key in _direct_history if key != bus_id),
                    None,
                )
                if stale_bus_id is None:
                    break
                _direct_history.pop(stale_bus_id, None)
            if not history or (
                history[-1].get("timestamp") != source_timestamp
                or round(history[-1]["latitude"], 7) != round(latitude, 7)
                or round(history[-1]["longitude"], 7) != round(longitude, 7)
            ):
                if not history or event_time > history[-1]["time"]:
                    history.append(point)
                    del history[:-10]
            history_snapshot = [dict(entry) for entry in history]
        bus["movement_history"] = history_snapshot
        bus["history_points"] = len(history_snapshot)
        if len(history_snapshot) >= 2:
            movement = update_bus_history(bus, history_snapshot)
            bus.update(movement)
            bus["historical_movement_status"] = movement.get("movement_status")
            if bus.get("is_stale") or bus.get("vehicle_status") == "no_signal":
                bus["movement_status"] = "unknown"
                bus["direction"] = None
                bus["heading"] = None
                bus["likely_towards"] = None
        else:
            bus["historical_movement_status"] = "unknown"
        old = latest.get(bus_id)
        if old is None or str(bus.get("timestamp") or "") > str(old.get("timestamp") or ""):
            latest[bus_id] = bus

    buses = list(latest.values())
    try:
        persisted_histories = load_recent_points([bus.get("bus_id") for bus in buses], limit=10)
    except Exception as error:
        print(f"Persisted movement history unavailable; using in-memory history: {error}", flush=True)
        persisted_histories = {}

    for bus in buses:
        bus_id = str(bus.get("bus_id") or "").strip().upper()
        persisted = persisted_histories.get(bus_id, [])
        in_memory = bus.get("movement_history") or []
        merged = {}
        for point in list(persisted) + list(in_memory):
            try:
                event_time = float(point.get("time", point.get("event_time")))
                latitude_point = float(point["latitude"])
                longitude_point = float(point["longitude"])
            except (TypeError, ValueError, KeyError):
                continue
            key = (round(event_time, 3), round(latitude_point, 6), round(longitude_point, 6))
            merged[key] = {
                "time": event_time,
                "timestamp": point.get("timestamp"),
                "latitude": latitude_point,
                "longitude": longitude_point,
                "speed": float(point.get("speed") or 0.0),
            }
        history = sorted(merged.values(), key=lambda point: point["time"])[-10:]
        bus["movement_history"] = history
        bus["history_points"] = len(history)
        if len(history) >= 2:
            movement = update_bus_history(bus, history)
            if movement:
                bus.update(movement)
                bus["historical_movement_status"] = movement.get("movement_status")
                bus["movement_source"] = "recent GPS history"
        else:
            bus["historical_movement_status"] = "unknown"
            bus["movement_source"] = "insufficient GPS history"

        if bus.get("is_stale") or bus.get("vehicle_status") == "no_signal":
            bus["movement_is_current"] = False
            bus["movement_label"] = "Last known movement"
        else:
            bus["movement_is_current"] = True
            bus["movement_label"] = "Recent movement"

    status_counts = {}
    for bus in buses:
        status = str(bus.get("vehicle_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    sample = [
        {
            "bus_id": bus.get("bus_id"),
            "timestamp": bus.get("timestamp"),
            "latitude": bus.get("latitude"),
            "longitude": bus.get("longitude"),
            "status": bus.get("vehicle_status"),
        }
        for bus in buses[:5]
    ]
    unique_positions = len({
        (round(bus["latitude"], 5), round(bus["longitude"], 5))
        for bus in buses
    })
    global _direct_snapshot, _direct_snapshot_at
    if buses:
        with _cache_lock:
            _direct_snapshot = copy.deepcopy(buses)
            _direct_snapshot_at = time.time()

    print(
        f"Direct MARGDARSHI feed: buses={len(buses)} "
        f"unique_positions={unique_positions} statuses={status_counts}",
        flush=True,
    )
    return buses


def get_cached_direct_live_buses():
    with _cache_lock:
        if not _direct_snapshot or _direct_snapshot_at is None:
            return []
        age = time.time() - _direct_snapshot_at
        if age > DIRECT_SNAPSHOT_MAX_AGE_SECONDS:
            return []
        buses = copy.deepcopy(_direct_snapshot)

    snapshot_stale = age > max(120, int(os.getenv("PREDICTION_COLLECT_INTERVAL_SECONDS", "60")) * 2)
    for bus in buses:
        bus["snapshot_age_seconds"] = int(age)
        bus["snapshot_stale"] = snapshot_stale
        if snapshot_stale:
            bus["is_stale"] = True
            bus["data_stale"] = True
            bus["position_confidence"] = "low"
            bus["location_label"] = "Last known location"
            bus["movement_is_current"] = False
            bus["movement_label"] = "Last known movement"
    return buses


def _fetch_live_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://margdarshi.upsrtcvlt.com",
        "Referer": "https://margdarshi.upsrtcvlt.com/",
    }

    last_error = None

    for attempt in range(2):
        try:
            response = _post_with_dns_fallback(
                GPS_API_URL,
                headers=headers,
                timeout=(4, 8),
            )
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list):
                raise ValueError("MARGDARSHI returned an unexpected response")

            print(f"MARGDARSHI returned {len(data)} raw buses", flush=True)
            return data

        except (requests.RequestException, ValueError) as error:
            last_error = error

            if attempt < 1:
                time.sleep(1)

    raise RuntimeError(f"MARGDARSHI live GPS request failed: {last_error}")


def _process_live_buses(data, upstream_latency_ms=None):
    electric_buses = [
        item
        for item in data
        if isinstance(item, dict)
        and str(item.get("depot_name") or "").strip().upper() == "NOIDA ELECTRIC"
    ]

    raw_electric_count = len(electric_buses)
    latest_by_bus = {}

    for item in electric_buses:
        bus_id = str(item.get("bus_id") or "").strip().upper()
        if not bus_id:
            continue

        status = (
            str(item.get("vehicle_status") or "")
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )
        current = latest_by_bus.get(bus_id)

        if current is None:
            latest_by_bus[bus_id] = item
            continue

        current_status = (
            str(current.get("vehicle_status") or "")
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )
        item_time = _parse_timestamp(item.get("timestamp"))
        current_time = _parse_timestamp(current.get("timestamp"))
        item_online = status not in {"no_signal", "nosignal", "offline", "unavailable"}
        current_online = current_status not in {"no_signal", "nosignal", "offline", "unavailable"}

        if item_online and not current_online:
            latest_by_bus[bus_id] = item
        elif item_online == current_online and item_time is not None and (
            current_time is None or item_time > current_time
        ):
            latest_by_bus[bus_id] = item

    electric_buses = list(latest_by_bus.values())

    print(
        f"GPS feed received {len(data)} raw records; "
        f"{raw_electric_count} NOIDA ELECTRIC records; "
        f"{len(electric_buses)} unique buses after dedupe",
        flush=True,
    )

    if not electric_buses:
        return []

    global _validation_last_points

    with _cache_lock:
        previous_points = {
            bus_id: dict(point)
            for bus_id, point in _validation_last_points.items()
        }

    validation = validate_gps_batch(
        electric_buses,
        previous_points=previous_points,
    )

    buses = validation["accepted"]
    trackable_buses = validation["trackable"]

    with _cache_lock:
        _validation_last_points = {
            item["bus_id"]: dict(item)
            for item in trackable_buses
        }

    print(
        f"GPS validation: received={validation['stats']['received']} "
        f"accepted={validation['stats']['accepted']} "
        f"rejected={validation['stats']['rejected']} "
        f"reasons={validation['stats']['reject_reasons']}",
        flush=True,
    )

    try:
        record_validation_audit(validation)
    except Exception as error:
        print(f"GPS audit write failed; continuing: {error}", flush=True)

    now = time.time()

    with _cache_lock:
        _ingestion_stats["cycles"] += 1
        _ingestion_stats["buses_received"] += validation["stats"]["received"]
        _ingestion_stats["buses_accepted"] += validation["stats"]["accepted"]
        _ingestion_stats["buses_rejected"] += validation["stats"]["rejected"]
        accepted_ids = {item["bus_id"] for item in trackable_buses}
        disappeared = sorted(_previous_seen_bus_ids - accepted_ids)
        _previous_seen_bus_ids.clear()
        _previous_seen_bus_ids.update(accepted_ids)
        ages = [
            int(_fix_age_seconds(item.get("timestamp"), now))
            for item in buses
            if _fix_age_seconds(item.get("timestamp"), now) is not None
        ]

        _ingestion_stats["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
        _ingestion_stats["last_avg_gps_age_seconds"] = (
            round(sum(ages) / len(ages), 1) if ages else None
        )
        _ingestion_stats["last_buses_disappeared"] = disappeared
        current_time = time.time()
        for item in trackable_buses:
            bus_id = item["bus_id"]
            previous_identity = _identity_last_seen.get(bus_id)
            if previous_identity:
                gap_seconds = current_time - previous_identity["seen_at"]
                distance_km = calculate_distance(
                    previous_identity["latitude"],
                    previous_identity["longitude"],
                    item["latitude"],
                    item["longitude"],
                )
                if gap_seconds > 4 * 3600 and distance_km > 15:
                    _identity_warnings.append({
                        "bus_id": bus_id,
                        "upstream_id": item["upstream_id"],
                        "gap_hours": round(gap_seconds / 3600, 1),
                        "distance_km": round(distance_km, 2),
                        "warning": "identity_reappeared_with_discontinuity",
                    })
                    del _identity_warnings[:-50]

            _identity_last_seen[bus_id] = {
                "seen_at": current_time,
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "upstream_id": item["upstream_id"],
            }

        if len(_identity_last_seen) > 500:
            for stale_id, _ in sorted(
                _identity_last_seen.items(),
                key=lambda entry: entry[1].get("seen_at", 0),
            )[:len(_identity_last_seen) - 500]:
                _identity_last_seen.pop(stale_id, None)

        for reason, count in validation["stats"]["reject_reasons"].items():
            _ingestion_stats["reject_reasons"][reason] = (
                _ingestion_stats["reject_reasons"].get(reason, 0) + count
            )

    try:
        record_ingestion_log(
            recorded_at=_ingestion_stats["last_cycle_at"],
            buses_received=validation["stats"]["received"],
            buses_accepted=validation["stats"]["accepted"],
            buses_rejected=validation["stats"]["rejected"],
            avg_gps_age_seconds=_ingestion_stats["last_avg_gps_age_seconds"],
            upstream_latency_ms=upstream_latency_ms,
            anomalies_detected=len(validation["rejected"]),
        )
    except Exception as error:
        print(f"Ingestion log write failed; continuing: {error}", flush=True)

    if not buses:
        return []

    trackable_buses = validation["trackable"]

    for result in buses:
        fix_age = _fix_age_seconds(result.get("timestamp"), now)
        result["fix_age_seconds"] = fix_age
        result["gps_age_seconds"] = fix_age
        result["data_stale"] = bool(
            result.get("fix_unchanged")
            or fix_age is None
            or fix_age > 180
        )
        result["source_health"] = (
            "fresh" if not result.get("fix_unchanged") and fix_age is not None and fix_age <= 90
            else "aging" if not result.get("fix_unchanged") and fix_age is not None and fix_age <= 180
            else "stale"
        )

    try:
        histories = prepare_histories(trackable_buses)
    except Exception as error:
        print(f"GPS history processing failed; continuing without history: {error}", flush=True)
        histories = {}

    for result in buses:
        bus_id = str(result.get("bus_id") or "").strip().upper()
        history = histories.get(bus_id, [])
        direction = update_bus_history(result, history)

        if direction:
            result.update(direction)

        heading = result.get("heading")
        try:
            heading = float(heading) if heading is not None else None
        except (TypeError, ValueError):
            heading = None

        result.update(
            match_position(
                bus_id,
                result["latitude"],
                result["longitude"],
                heading,
            )
        )
        result["route_match_history"] = match_history(bus_id, history)

        if result.get("route_match_status") == "off_route":
            result["gps_route_anomaly"] = True

        if history:
            result["validated_latitude"] = history[-1]["latitude"]
            result["validated_longitude"] = history[-1]["longitude"]
            result["canonical_latitude"] = history[-1]["latitude"]
            result["canonical_longitude"] = history[-1]["longitude"]
        else:
            result["validated_latitude"] = result["latitude"]
            result["validated_longitude"] = result["longitude"]
            result["canonical_latitude"] = result["latitude"]
            result["canonical_longitude"] = result["longitude"]

    try:
        ml_analysis = analyze_buses(buses, histories=histories)
    except Exception as error:
        print(f"ML analysis failed; continuing with live GPS data: {error}", flush=True)
        ml_analysis = {}

    for result in buses:
        prediction = ml_analysis.get(
            str(result.get("bus_id") or "").strip().upper()
        )

        if prediction:
            result.update(prediction)

    return buses


def get_ingestion_stats():
    with _cache_lock:
        return {
            **_ingestion_stats,
            "reject_reasons": dict(_ingestion_stats["reject_reasons"]),
            "last_buses_disappeared": list(_ingestion_stats["last_buses_disappeared"]),
            "identity_warnings": list(_identity_warnings[-50:]),
        }



def refresh_noida_electric_buses():
    global _last_good_buses, _last_good_at
    global _latest_processed_buses, _latest_processed_at
    global _latest_raw_electric_buses, _latest_raw_electric_at

    started_at = time.perf_counter()

    try:
        data = _fetch_live_data()
        try:
            get_direct_live_buses(data)
        except Exception as direct_error:
            print(f"Direct GPS snapshot refresh failed: {direct_error}", flush=True)
        upstream_latency_ms = round((time.perf_counter() - started_at) * 1000, 1)
        raw_electric_buses = [
            dict(item)
            for item in data
            if isinstance(item, dict)
            and str(item.get("depot_name") or "").strip().upper() == "NOIDA ELECTRIC"
        ]

        with _cache_lock:
            _latest_raw_electric_buses = [dict(bus) for bus in raw_electric_buses]
            _latest_raw_electric_at = time.time()

        buses = _process_live_buses(data, upstream_latency_ms=upstream_latency_ms)

        with _cache_lock:
            _ingestion_stats["last_upstream_latency_ms"] = upstream_latency_ms
            _ingestion_stats["last_source_health"] = (
                "healthy" if buses else "empty_after_validation"
            )

        if buses:
            now = time.time()

            with _cache_lock:
                _latest_processed_buses = [dict(bus) for bus in buses]
                _latest_processed_at = now
                _last_good_buses = [dict(bus) for bus in buses]
                _last_good_at = now

        return buses

    except Exception as error:
        raise RuntimeError(f"Noida bus refresh failed: {error}") from error


def get_latest_raw_electric_buses():
    with _cache_lock:
        if _latest_raw_electric_buses:
            return [dict(bus) for bus in _latest_raw_electric_buses]
    return []


def get_noida_electric_buses(force_refresh=False):
    with _cache_lock:
        if (
            _latest_processed_buses
            and _latest_processed_at
            and time.time() - _latest_processed_at <= PROCESSED_CACHE_SECONDS
        ):
            return [dict(bus) for bus in _latest_processed_buses]

        if _last_good_buses and _last_good_at:
            age = time.time() - _last_good_at

            if age <= MAX_CACHE_SECONDS:
                cached = [dict(bus) for bus in _last_good_buses]

                for bus in cached:
                    bus["cache_age_seconds"] = int(age)

                    fix_age = bus.get("fix_age_seconds")
                    bus["data_stale"] = bool(
                        bus.get("data_stale")
                        or (
                            fix_age is not None
                            and fix_age > 180
                        )
                        or age > PROCESSED_CACHE_SECONDS
                    )

                return cached

    return []
