import math
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge

from utils.distance import calculate_distance

DB_PATH = os.getenv("PREDICTION_DB_PATH", "/tmp/noidabus_prediction_history.sqlite3")
MAX_HISTORY = 40
MODEL_HISTORY = 12
MIN_MODEL_POINTS = 5
_initialized = False


def _connection():
    global _initialized
    connection = sqlite3.connect(DB_PATH, timeout=10)
    if not _initialized:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bus_positions (
                bus_id TEXT NOT NULL,
                source_timestamp TEXT,
                event_time REAL NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed REAL,
                PRIMARY KEY (bus_id, source_timestamp, latitude, longitude)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_bus_positions_bus_time ON bus_positions(bus_id, event_time)"
        )
        connection.commit()
        _initialized = True
    return connection


def _parse_timestamp(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def _safe_float(value, default=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def record_positions(buses):
    rows = []

    import time

    fallback_now = time.time()

    for bus in buses:
        bus_id = str(bus.get("bus_id") or "").strip().upper()
        latitude = _safe_float(bus.get("latitude"), math.nan)
        longitude = _safe_float(bus.get("longitude"), math.nan)

        if not bus_id or not math.isfinite(latitude) or not math.isfinite(longitude):
            continue

        source_timestamp = bus.get("timestamp")
        event_time = _parse_timestamp(source_timestamp)

        if event_time is None:
            event_time = fallback_now

        rows.append(
            (
                bus_id,
                str(source_timestamp or ""),
                event_time,
                latitude,
                longitude,
                _safe_float(bus.get("speed"), 0.0),
            )
        )

    if not rows:
        return

    connection = _connection()
    try:
        connection.executemany(
            """
            INSERT OR REPLACE INTO bus_positions
            (bus_id, source_timestamp, event_time, latitude, longitude, speed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        bus_ids = sorted({row[0] for row in rows})

        for bus_id in bus_ids:
            connection.execute(
                """
                DELETE FROM bus_positions
                WHERE bus_id = ?
                  AND rowid NOT IN (
                      SELECT rowid
                      FROM bus_positions
                      WHERE bus_id = ?
                      ORDER BY event_time DESC
                      LIMIT ?
                  )
                """,
                (bus_id, bus_id, MAX_HISTORY),
            )

        connection.commit()
    finally:
        connection.close()


def load_histories(bus_ids):
    connection = _connection()
    histories = {}

    try:
        for bus_id in bus_ids:
            rows = connection.execute(
                """
                SELECT event_time, latitude, longitude, speed
                FROM bus_positions
                WHERE bus_id = ?
                ORDER BY event_time ASC
                LIMIT ?
                """,
                (str(bus_id).strip().upper(), MAX_HISTORY),
            ).fetchall()

            histories[str(bus_id).strip().upper()] = [
                {
                    "time": float(row[0]),
                    "latitude": float(row[1]),
                    "longitude": float(row[2]),
                    "speed": float(row[3] or 0.0),
                }
                for row in rows
            ]
    finally:
        connection.close()

    return histories


def _bearing(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (
        math.cos(lat1_rad) * math.sin(lat2_rad)
        - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    )

    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _angle_difference(first, second):
    difference = abs(first - second)
    return 360 - difference if difference > 180 else difference


def _transition_features(history):
    features = []

    for index in range(1, len(history)):
        previous = history[index - 1]
        current = history[index]
        delta_seconds = current["time"] - previous["time"]

        if delta_seconds < 2:
            continue

        distance = calculate_distance(
            previous["latitude"],
            previous["longitude"],
            current["latitude"],
            current["longitude"],
        )
        implied_speed = distance / (delta_seconds / 3600)

        speed_delta = abs(current["speed"] - previous["speed"])
        turn_change = 0.0

        if index >= 2:
            before = history[index - 2]
            first_bearing = _bearing(
                before["latitude"],
                before["longitude"],
                previous["latitude"],
                previous["longitude"],
            )
            second_bearing = _bearing(
                previous["latitude"],
                previous["longitude"],
                current["latitude"],
                current["longitude"],
            )
            turn_change = _angle_difference(first_bearing, second_bearing)

        features.append(
            [distance, implied_speed, speed_delta, turn_change]
        )

    return features


def _build_anomaly_model(histories):
    training_rows = []

    for history in histories.values():
        training_rows.extend(_transition_features(history))

    if len(training_rows) < 30:
        return None

    model = IsolationForest(
        n_estimators=80,
        contamination="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(training_rows)
    return model


def _trajectory_prediction(history):
    if len(history) < MIN_MODEL_POINTS:
        return None

    points = history[-MODEL_HISTORY:]
    first_time = points[0]["time"]
    x_values = [[(point["time"] - first_time) / 60.0] for point in points]
    span_minutes = x_values[-1][0] - x_values[0][0]

    if span_minutes < 1.5:
        return None

    latitude_model = Ridge(alpha=0.0001)
    longitude_model = Ridge(alpha=0.0001)

    latitude_model.fit(x_values, [point["latitude"] for point in points])
    longitude_model.fit(x_values, [point["longitude"] for point in points])

    residuals = []

    for x_value, point in zip(x_values, points):
        predicted_latitude = float(latitude_model.predict([x_value])[0])
        predicted_longitude = float(longitude_model.predict([x_value])[0])
        residuals.append(
            calculate_distance(
                point["latitude"],
                point["longitude"],
                predicted_latitude,
                predicted_longitude,
            )
        )

    residual_km = sum(residuals) / len(residuals)
    current = points[-1]
    observed_speeds = [point["speed"] for point in points[-5:] if point["speed"] > 0]
    speed_reference = sum(observed_speeds) / len(observed_speeds) if observed_speeds else 25.0

    future = {}

    for horizon_minutes in (1, 3, 5):
        current_x = x_values[-1][0]
        future_x = [[current_x + horizon_minutes]]
        predicted_latitude = float(latitude_model.predict(future_x)[0])
        predicted_longitude = float(longitude_model.predict(future_x)[0])

        displacement = calculate_distance(
            current["latitude"],
            current["longitude"],
            predicted_latitude,
            predicted_longitude,
        )

        maximum_displacement = max(
            0.35,
            speed_reference * horizon_minutes / 60.0 * 1.65 + 0.25,
        )

        if displacement > maximum_displacement and displacement > 0:
            ratio = maximum_displacement / displacement
            predicted_latitude = current["latitude"] + (
                predicted_latitude - current["latitude"]
            ) * ratio
            predicted_longitude = current["longitude"] + (
                predicted_longitude - current["longitude"]
            ) * ratio

        future[horizon_minutes] = {
            "latitude": round(predicted_latitude, 6),
            "longitude": round(predicted_longitude, 6),
        }

    confidence = 0.25
    confidence += min(0.25, len(points) * 0.025)
    confidence += min(0.20, span_minutes * 0.03)
    confidence += 0.30 * max(0.0, 1.0 - min(residual_km / 0.30, 1.0))
    confidence = max(0.0, min(0.97, confidence))

    return {
        "predicted_1m": future[1],
        "predicted_3m": future[3],
        "predicted_5m": future[5],
        "confidence": round(confidence, 2),
        "residual_km": round(residual_km, 3),
        "history_points": len(points),
        "history_span_minutes": round(span_minutes, 1),
    }


def _analyze_single(bus, history, anomaly_model):
    transition_features = _transition_features(history)
    latest_features = transition_features[-1] if transition_features else None

    anomaly_score = None
    if anomaly_model is not None and latest_features:
        anomaly_score = float(anomaly_model.decision_function([latest_features])[0])

    implied_speed = latest_features[1] if latest_features else None
    current_speed = _safe_float(bus.get("speed"), 0.0)

    hard_teleport = False
    if implied_speed is not None:
        hard_teleport = (
            implied_speed > 120.0
            or (
                implied_speed > max(current_speed + 70.0, 100.0)
                and latest_features[0] > 1.5
            )
        )

    latitude = _safe_float(bus.get("latitude"), math.nan)
    longitude = _safe_float(bus.get("longitude"), math.nan)

    invalid_region = not (
        27.70 <= latitude <= 29.20
        and 76.70 <= longitude <= 78.10
    )

    fleet_outlier = anomaly_score is not None and anomaly_score < 0.0
    gps_anomaly = bool(hard_teleport or invalid_region or fleet_outlier)

    prediction = _trajectory_prediction(history)
    confidence = prediction["confidence"] if prediction else 0.0

    prediction_applied = bool(
        gps_anomaly and prediction and confidence >= 0.72
    )

    result = {
        "gps_anomaly": gps_anomaly,
        "gps_anomaly_score": round(anomaly_score, 3) if anomaly_score is not None else None,
        "gps_anomaly_reason": (
            "invalid_region"
            if invalid_region
            else "impossible_jump"
            if hard_teleport
            else "fleet_motion_outlier"
            if fleet_outlier
            else None
        ),
        "prediction_available": bool(prediction),
        "prediction_confidence": confidence,
        "prediction_applied": prediction_applied,
        "prediction_source": "ML_Ridge_Trajectory" if prediction else None,
        "predicted_latitude": prediction["predicted_1m"]["latitude"] if prediction else None,
        "predicted_longitude": prediction["predicted_1m"]["longitude"] if prediction else None,
        "predicted_3m": prediction["predicted_3m"] if prediction else None,
        "predicted_5m": prediction["predicted_5m"] if prediction else None,
        "prediction_residual_km": prediction["residual_km"] if prediction else None,
        "prediction_history_points": prediction["history_points"] if prediction else len(history),
        "prediction_history_minutes": prediction["history_span_minutes"] if prediction else 0,
        "implied_speed_kmh": round(implied_speed, 1) if implied_speed is not None else None,
        "gps_history_points": len(history),
    }

    if prediction_applied:
        result["display_latitude"] = prediction["predicted_1m"]["latitude"]
        result["display_longitude"] = prediction["predicted_1m"]["longitude"]
    else:
        result["display_latitude"] = latitude
        result["display_longitude"] = longitude

    return result


def analyze_buses(buses):
    record_positions(buses)

    bus_ids = [
        str(bus.get("bus_id") or "").strip().upper()
        for bus in buses
        if bus.get("bus_id")
    ]
    histories = load_histories(bus_ids)
    anomaly_model = _build_anomaly_model(histories)

    analysis = {}

    for bus in buses:
        bus_id = str(bus.get("bus_id") or "").strip().upper()
        if not bus_id:
            continue
        analysis[bus_id] = _analyze_single(
            bus,
            histories.get(bus_id, []),
            anomaly_model,
        )

    return analysis
