import math
import os
import sqlite3
from datetime import datetime, timezone

from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge

from utils.distance import calculate_distance

DB_PATH = os.getenv("PREDICTION_DB_PATH", "/tmp/noidabus_prediction_history.sqlite3")
MAX_HISTORY = 30
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
        _initialized = True
        connection.commit()
    return connection


def _parse_timestamp(value):
    if not value:
        return None

    text = str(value).strip()
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def _safe_float(value, default=0.0):
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return default


def record_position(bus):
    bus_id = str(bus.get("bus_id") or "").strip().upper()
    if not bus_id:
        return

    latitude = _safe_float(bus.get("latitude"), math.nan)
    longitude = _safe_float(bus.get("longitude"), math.nan)

    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return

    source_timestamp = bus.get("timestamp")
    event_time = _parse_timestamp(source_timestamp)

    if event_time is None:
        import time
        event_time = time.time()
        source_timestamp = f"fallback-{event_time:.3f}"

    speed = _safe_float(bus.get("speed"), 0.0)

    connection = _connection()
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO bus_positions
            (bus_id, source_timestamp, event_time, latitude, longitude, speed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                bus_id,
                str(source_timestamp or ""),
                event_time,
                latitude,
                longitude,
                speed,
            ),
        )
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


def load_history(bus_id):
    connection = _connection()
    try:
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
    finally:
        connection.close()

    return [
        {
            "time": float(row[0]),
            "latitude": float(row[1]),
            "longitude": float(row[2]),
            "speed": float(row[3] or 0.0),
        }
        for row in rows
    ]


def _all_recent_histories():
    connection = _connection()
    try:
        bus_ids = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT bus_id FROM bus_positions"
            ).fetchall()
        ]
    finally:
        connection.close()

    return {bus_id: load_history(bus_id) for bus_id in bus_ids}


def _bearing(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (
        math.cos(lat1_rad) * math.sin(lat2_rad)
        - math.sin(lat1_rad)
        * math.cos(lat2_rad)
        * math.cos(delta_lon)
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


def _fleet_anomaly_score(history):
    current_features = _transition_features(history)

    if not current_features:
        return None, None

    latest = current_features[-1]
    all_features = []

    for other_history in _all_recent_histories().values():
        all_features.extend(_transition_features(other_history))

    if len(all_features) < 20:
        return None, latest

    model = IsolationForest(
        n_estimators=100,
        contamination="auto",
        random_state=42,
    )
    model.fit(all_features)

    score = float(model.decision_function([latest])[0])
    return score, latest


def _fit_trajectory(history):
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

    future = {}
    current_x = x_values[-1][0]

    for horizon_minutes in (1, 3, 5):
        future_x = [[current_x + horizon_minutes]]
        predicted_latitude = float(latitude_model.predict(future_x)[0])
        predicted_longitude = float(longitude_model.predict(future_x)[0])

        current = points[-1]
        displacement = calculate_distance(
            current["latitude"],
            current["longitude"],
            predicted_latitude,
            predicted_longitude,
        )

        observed_speeds = [
            point["speed"]
            for point in points[-5:]
            if point["speed"] > 0
        ]
        speed_reference = (
            sum(observed_speeds) / len(observed_speeds)
            if observed_speeds
            else 25.0
        )

        maximum_displacement = max(
            0.35,
            speed_reference * horizon_minutes / 60.0 * 1.7 + 0.3
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

    confidence = 0.35
    confidence += min(0.25, len(points) * 0.025)
    confidence += min(0.2, span_minutes * 0.03)
    confidence += 0.2 * max(
        0.0,
        1.0 - min(residual_km / 0.30, 1.0),
    )
    confidence = max(0.0, min(0.98, confidence))

    return {
        "predicted_1m": future[1],
        "predicted_3m": future[3],
        "predicted_5m": future[5],
        "confidence": round(confidence, 2),
        "residual_km": round(residual_km, 3),
        "history_points": len(points),
        "history_span_minutes": round(span_minutes, 1),
    }


def analyze_bus(bus):
    record_position(bus)

    bus_id = str(bus.get("bus_id") or "").strip().upper()
    history = load_history(bus_id)

    prediction = _fit_trajectory(history)
    anomaly_score, latest_features = _fleet_anomaly_score(history)

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

    invalid_region = not (
        27.70 <= float(bus["latitude"]) <= 29.20
        and 76.70 <= float(bus["longitude"]) <= 78.10
    )

    model_outlier = anomaly_score is not None and anomaly_score < 0.0
    gps_anomaly = bool(hard_teleport or invalid_region or model_outlier)

    prediction_confidence = prediction["confidence"] if prediction else 0.0
    prediction_applied = bool(
        gps_anomaly
        and prediction
        and prediction_confidence >= 0.72
    )

    output = {
        "gps_anomaly": gps_anomaly,
        "gps_anomaly_score": round(anomaly_score, 3) if anomaly_score is not None else None,
        "gps_anomaly_reason": (
            "invalid_region"
            if invalid_region
            else "teleport"
            if hard_teleport
            else "fleet_outlier"
            if model_outlier
            else None
        ),
        "prediction_available": bool(prediction),
        "prediction_confidence": prediction_confidence,
        "prediction_applied": prediction_applied,
        "prediction_source": "ML_Ridge" if prediction else None,
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
        output["display_latitude"] = prediction["predicted_1m"]["latitude"]
        output["display_longitude"] = prediction["predicted_1m"]["longitude"]
    else:
        output["display_latitude"] = float(bus["latitude"])
        output["display_longitude"] = float(bus["longitude"])

    return output
