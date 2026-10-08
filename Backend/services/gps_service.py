import math
import os
import threading
import time
from datetime import datetime, timezone

import requests
import socket
import ssl
from http.client import HTTPResponse
from io import BytesIO

import dns.resolver

from services.direction_service import update_bus_history
from services.ml_prediction_service import analyze_buses, load_latest_points, prepare_histories, record_ingestion_log, record_validation_audit
from services.validation_service import validate_gps_batch
from utils.distance import calculate_distance
from services.position_trust_service import match_history, match_position

GPS_API_URL = "https://margdarshi.upsrtcvlt.com/php/getGpsLiveData.php"

_last_good_buses = []
_last_good_at = None
_latest_processed_buses = []
_latest_processed_at = None
_cache_lock = threading.Lock()
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
_identity_last_seen = {}
_identity_warnings = []
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

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

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
        if str(item.get("depot_name") or "").strip().upper() == "NOIDA ELECTRIC"
    ]

    print(
        f"GPS feed received {len(data)} raw records; "
        f"{len(electric_buses)} match NOIDA ELECTRIC",
        flush=True,
    )

    if not electric_buses:
        return []

    raw_ids = [
        str(item.get("bus_id") or "").strip().upper()
        for item in electric_buses
        if item.get("bus_id")
    ]

    try:
        previous_points = load_latest_points(raw_ids)
    except Exception as error:
        print(f"GPS history read failed; continuing without history: {error}", flush=True)
        previous_points = {}

    validation = validate_gps_batch(
        electric_buses,
        previous_points=previous_points,
    )

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
        accepted_ids = {item["bus_id"] for item in validation["accepted"]}
        disappeared = sorted(_previous_seen_bus_ids - accepted_ids)
        _previous_seen_bus_ids.clear()
        _previous_seen_bus_ids.update(accepted_ids)

        ages = [
            int(_fix_age_seconds(item.get("timestamp"), now))
            for item in validation["accepted"]
            if _fix_age_seconds(item.get("timestamp"), now) is not None
        ]

        _ingestion_stats["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
        _ingestion_stats["last_avg_gps_age_seconds"] = (
            round(sum(ages) / len(ages), 1) if ages else None
        )
        _ingestion_stats["last_buses_disappeared"] = disappeared
        current_time = time.time()
        for item in validation["accepted"]:
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

        for reason, count in validation["stats"]["reject_reasons"].items():
            _ingestion_stats["reject_reasons"][reason] = (
                _ingestion_stats["reject_reasons"].get(reason, 0) + count
            )

    buses = validation["accepted"]

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

    for result in buses:
        fix_age = _fix_age_seconds(result.get("timestamp"), now)
        result["fix_age_seconds"] = fix_age
        result["gps_age_seconds"] = fix_age
        result["data_stale"] = bool(
            fix_age is None or fix_age > 180
        )
        result["source_health"] = (
            "fresh" if fix_age is not None and fix_age <= 90
            else "aging" if fix_age is not None and fix_age <= 180
            else "stale"
        )

    try:
        histories = prepare_histories(buses)
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

    started_at = time.perf_counter()

    try:
        data = _fetch_live_data()
        upstream_latency_ms = round((time.perf_counter() - started_at) * 1000, 1)
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
