import io
import math
import os
import pickle
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sklearn.ensemble import RandomForestRegressor

from services.ml_prediction_service import DATABASE_URL, PERSISTED_HISTORY_LIMIT, _connect

MODEL_KEY = "noida_bus_forecast_3m_v1"
FEATURE_VERSION = 1
HORIZON_SECONDS = 180
TARGET_TOLERANCE_SECONDS = 90
LOOKBACK_SECONDS = 48 * 3600
MIN_SAMPLES = 500
MIN_TRAINING_SAMPLES = 300
MIN_VALIDATION_SAMPLES = 100
MIN_HISTORY_SPAN_SECONDS = 20 * 60
MAX_TRAINING_SAMPLES = 6000
MAX_VALIDATION_SAMPLES = 2000
RETRAIN_INTERVAL_SECONDS = max(3600, int(os.getenv("FORECAST_RETRAIN_INTERVAL_SECONDS", "21600")))
NON_PROMOTION_RETRY_SECONDS = max(3600, int(os.getenv("FORECAST_NON_PROMOTION_RETRY_SECONDS", "3600")))
TRAINING_ERROR_RETRY_SECONDS = max(900, int(os.getenv("FORECAST_TRAINING_ERROR_RETRY_SECONDS", "1800")))
MODEL_CACHE_SECONDS = 300
LAG_COUNT = 4

_model_cache = None
_model_cache_checked_at = 0.0
_model_cache_lock = threading.Lock()
_training_lock = threading.Lock()


def _ensure_schema(connection):
    if DATABASE_URL:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS forecast_model_artifacts (
                    model_key VARCHAR(80) PRIMARY KEY,
                    model_payload BYTEA,
                    model_trained_at DOUBLE PRECISION,
                    training_samples INTEGER NOT NULL DEFAULT 0,
                    validation_samples INTEGER NOT NULL DEFAULT 0,
                    model_mae_km DOUBLE PRECISION,
                    baseline_mae_km DOUBLE PRECISION,
                    last_attempt_at DOUBLE PRECISION,
                    last_attempt_status VARCHAR(50),
                    last_attempt_samples INTEGER,
                    last_attempt_model_mae_km DOUBLE PRECISION,
                    last_attempt_baseline_mae_km DOUBLE PRECISION
                )
                """
            )
            cursor.execute("ALTER TABLE public.forecast_model_artifacts ENABLE ROW LEVEL SECURITY")
    else:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS forecast_model_artifacts (
                model_key TEXT PRIMARY KEY,
                model_payload BLOB,
                model_trained_at REAL,
                training_samples INTEGER NOT NULL DEFAULT 0,
                validation_samples INTEGER NOT NULL DEFAULT 0,
                model_mae_km REAL,
                baseline_mae_km REAL,
                last_attempt_at REAL,
                last_attempt_status TEXT,
                last_attempt_samples INTEGER,
                last_attempt_model_mae_km REAL,
                last_attempt_baseline_mae_km REAL
            )
            """
        )
    connection.commit()


def _read_artifact():
    connection = _connect()
    try:
        _ensure_schema(connection)
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT model_payload, model_trained_at, training_samples,
                           validation_samples, model_mae_km, baseline_mae_km,
                           last_attempt_at, last_attempt_status, last_attempt_samples,
                           last_attempt_model_mae_km, last_attempt_baseline_mae_km
                    FROM forecast_model_artifacts
                    WHERE model_key = %s
                    """,
                    (MODEL_KEY,),
                )
                row = cursor.fetchone()
        else:
            row = connection.execute(
                """
                SELECT model_payload, model_trained_at, training_samples,
                       validation_samples, model_mae_km, baseline_mae_km,
                       last_attempt_at, last_attempt_status, last_attempt_samples,
                       last_attempt_model_mae_km, last_attempt_baseline_mae_km
                FROM forecast_model_artifacts
                WHERE model_key = ?
                """,
                (MODEL_KEY,),
            ).fetchone()
    finally:
        connection.close()

    if not row:
        return None

    return {
        "model_payload": row[0],
        "model_trained_at": row[1],
        "training_samples": int(row[2] or 0),
        "validation_samples": int(row[3] or 0),
        "model_mae_km": row[4],
        "baseline_mae_km": row[5],
        "last_attempt_at": row[6],
        "last_attempt_status": row[7],
        "last_attempt_samples": row[8],
        "last_attempt_model_mae_km": row[9],
        "last_attempt_baseline_mae_km": row[10],
    }


def forecast_model_status():
    try:
        artifact = _read_artifact()
    except Exception as error:
        return {
            "status": "storage_unavailable",
            "active": False,
            "error": type(error).__name__,
            "minimum_samples": MIN_SAMPLES,
        }

    if not artifact:
        return {
            "status": "collecting_data",
            "active": False,
            "model_type": "RandomForestRegressor",
            "horizon_minutes": HORIZON_SECONDS // 60,
            "minimum_samples": MIN_SAMPLES,
            "training_history_points_per_bus": PERSISTED_HISTORY_LIMIT,
        }

    active = artifact["model_payload"] is not None
    model_mae = artifact["model_mae_km"]
    baseline_mae = artifact["baseline_mae_km"]
    improvement = None
    if model_mae is not None and baseline_mae is not None and baseline_mae > 0:
        improvement = round((baseline_mae - model_mae) / baseline_mae * 100, 2)

    return {
        "status": "active" if active else (artifact["last_attempt_status"] or "collecting_data"),
        "active": active,
        "model_type": "RandomForestRegressor",
        "horizon_minutes": HORIZON_SECONDS // 60,
        "model_version": FEATURE_VERSION,
        "trained_at": artifact["model_trained_at"],
        "training_samples": artifact["training_samples"],
        "validation_samples": artifact["validation_samples"],
        "model_mae_km": model_mae,
        "baseline_mae_km": baseline_mae,
        "improvement_percent": improvement,
        "last_attempt_at": artifact["last_attempt_at"],
        "last_attempt_status": artifact["last_attempt_status"],
        "last_attempt_samples": artifact["last_attempt_samples"],
        "last_attempt_model_mae_km": artifact["last_attempt_model_mae_km"],
        "last_attempt_baseline_mae_km": artifact["last_attempt_baseline_mae_km"],
        "minimum_samples": MIN_SAMPLES,
        "training_history_points_per_bus": PERSISTED_HISTORY_LIMIT,
    }


def _clean_history(points):
    cleaned = []
    for point in sorted(points, key=lambda item: float(item.get("time", 0.0))):
        try:
            timestamp = float(point["time"])
            latitude = float(point["latitude"])
            longitude = float(point["longitude"])
            speed = float(point.get("speed") or 0.0)
        except (TypeError, ValueError, KeyError):
            continue

        if not all(math.isfinite(value) for value in (timestamp, latitude, longitude, speed)):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue

        cleaned_point = {
            "time": timestamp,
            "latitude": latitude,
            "longitude": longitude,
            "speed": max(0.0, min(120.0, speed)),
        }
        if cleaned and timestamp == cleaned[-1]["time"]:
            cleaned[-1] = cleaned_point
        elif not cleaned or timestamp > cleaned[-1]["time"]:
            cleaned.append(cleaned_point)
    return cleaned


def _local_displacement(current, previous):
    latitude = float(current["latitude"])
    north_m = (latitude - float(previous["latitude"])) * 111320.0
    east_m = (
        (float(current["longitude"]) - float(previous["longitude"]))
        * 111320.0
        * math.cos(math.radians(latitude))
    )
    return north_m, east_m


def _feature_vector(history, index):
    current = history[index]
    features = [
        float(current["latitude"]),
        float(current["longitude"]),
        max(0.0, min(120.0, float(current.get("speed") or 0.0))),
    ]

    for offset in range(1, LAG_COUNT + 1):
        previous_index = index - offset
        if previous_index < 0:
            features.extend([0.0, 0.0, 0.0, 0.0])
            continue

        previous = history[previous_index]
        elapsed = float(current["time"]) - float(previous["time"])
        if elapsed <= 0 or elapsed > 300:
            features.extend([0.0, 0.0, 0.0, 0.0])
            continue

        north_m, east_m = _local_displacement(current, previous)
        features.extend([
            max(-5000.0, min(5000.0, north_m)),
            max(-5000.0, min(5000.0, east_m)),
            min(5.0, elapsed / 60.0),
            max(0.0, min(120.0, float(previous.get("speed") or 0.0))),
        ])

    local_time = datetime.fromtimestamp(float(current["time"]), ZoneInfo("Asia/Kolkata"))
    day_angle = 2 * math.pi * (
        local_time.hour * 3600 + local_time.minute * 60 + local_time.second
    ) / 86400
    week_angle = 2 * math.pi * local_time.weekday() / 7
    features.extend([
        math.sin(day_angle),
        math.cos(day_angle),
        math.sin(week_angle),
        math.cos(week_angle),
    ])
    return features


def _future_index(history, index):
    target_time = float(history[index]["time"]) + HORIZON_SECONDS
    earliest = target_time - TARGET_TOLERANCE_SECONDS
    latest = target_time + TARGET_TOLERANCE_SECONDS
    candidates = []

    for future_index in range(index + 1, len(history)):
        future_time = float(history[future_index]["time"])
        if future_time > latest:
            break
        if earliest <= future_time <= latest:
            candidates.append(future_index)

    if not candidates:
        return None
    return min(candidates, key=lambda item: abs(float(history[item]["time"]) - target_time))


def _linear_baseline(history, index):
    if index <= 0:
        return [0.0, 0.0]

    current = history[index]
    previous = history[index - 1]
    elapsed = float(current["time"]) - float(previous["time"])
    if elapsed < 15 or elapsed > 300:
        return [0.0, 0.0]

    north_m, east_m = _local_displacement(current, previous)
    north_m *= HORIZON_SECONDS / elapsed
    east_m *= HORIZON_SECONDS / elapsed

    speed_kmh = max(
        float(current.get("speed") or 0.0),
        float(previous.get("speed") or 0.0),
    )
    max_distance_m = max(350.0, min(120.0, speed_kmh) * 50.0 * 1.6 + 200.0)
    distance_m = math.hypot(north_m, east_m)
    if distance_m > max_distance_m and distance_m > 0:
        scale = max_distance_m / distance_m
        north_m *= scale
        east_m *= scale
    return [north_m, east_m]


def build_training_samples(histories):
    samples = []
    for bus_id, raw_points in histories.items():
        history = _clean_history(raw_points)
        if len(history) < LAG_COUNT + 2:
            continue

        for index in range(LAG_COUNT, len(history) - 1):
            future_index = _future_index(history, index)
            if future_index is None:
                continue

            target_north, target_east = _local_displacement(history[future_index], history[index])
            if not all(math.isfinite(value) for value in (target_north, target_east)):
                continue
            if math.hypot(target_north, target_east) > 6000:
                continue

            samples.append({
                "time": float(history[future_index]["time"]),
                "bus_id": str(bus_id),
                "features": _feature_vector(history, index),
                "target": [target_north, target_east],
                "baseline": _linear_baseline(history, index),
            })

    samples.sort(key=lambda item: item["time"])
    return samples


def _load_training_histories():
    connection = _connect()
    try:
        cutoff = time.time() - LOOKBACK_SECONDS
        end = time.time() + 120
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT bus_id, event_time, latitude, longitude, speed
                    FROM bus_positions
                    WHERE event_time >= %s AND event_time <= %s
                    ORDER BY bus_id, event_time ASC, id ASC
                    """,
                    (cutoff, end),
                )
                rows = cursor.fetchall()
        else:
            rows = connection.execute(
                """
                SELECT bus_id, event_time, latitude, longitude, speed
                FROM bus_positions
                WHERE event_time >= ? AND event_time <= ?
                ORDER BY bus_id, event_time ASC, id ASC
                """,
                (cutoff, end),
            ).fetchall()

        histories = {}
        for row in rows:
            bus_id = str(row[0] or "").strip().upper()
            if not bus_id:
                continue
            histories.setdefault(bus_id, []).append({
                "time": float(row[1]),
                "latitude": float(row[2]),
                "longitude": float(row[3]),
                "speed": float(row[4] or 0.0),
            })
        return {bus_id: _clean_history(points) for bus_id, points in histories.items()}
    finally:
        connection.close()


def _even_sample(items, maximum):
    if len(items) <= maximum:
        return items
    step = (len(items) - 1) / (maximum - 1)
    return [items[round(index * step)] for index in range(maximum)]


def _mean_error_m(predictions, samples, key):
    errors = [
        math.hypot(float(prediction[0]) - sample[key][0], float(prediction[1]) - sample[key][1])
        for prediction, sample in zip(predictions, samples)
    ]
    return sum(errors) / len(errors) if errors else None


def _write_attempt(status, sample_count, training_count=0, validation_count=0, model_mae_km=None, baseline_mae_km=None, payload=None):
    now = time.time()
    connection = _connect()
    try:
        _ensure_schema(connection)
        values = (
            MODEL_KEY, payload, now if payload is not None else None, int(training_count),
            int(validation_count), model_mae_km, baseline_mae_km, now, status,
            int(sample_count), model_mae_km, baseline_mae_km,
        )
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO forecast_model_artifacts
                    (model_key, model_payload, model_trained_at, training_samples, validation_samples,
                     model_mae_km, baseline_mae_km, last_attempt_at, last_attempt_status,
                     last_attempt_samples, last_attempt_model_mae_km, last_attempt_baseline_mae_km)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (model_key) DO UPDATE SET
                      model_payload = COALESCE(EXCLUDED.model_payload, forecast_model_artifacts.model_payload),
                      model_trained_at = COALESCE(EXCLUDED.model_trained_at, forecast_model_artifacts.model_trained_at),
                      training_samples = CASE WHEN EXCLUDED.model_payload IS NOT NULL THEN EXCLUDED.training_samples ELSE forecast_model_artifacts.training_samples END,
                      validation_samples = CASE WHEN EXCLUDED.model_payload IS NOT NULL THEN EXCLUDED.validation_samples ELSE forecast_model_artifacts.validation_samples END,
                      model_mae_km = CASE WHEN EXCLUDED.model_payload IS NOT NULL THEN EXCLUDED.model_mae_km ELSE forecast_model_artifacts.model_mae_km END,
                      baseline_mae_km = CASE WHEN EXCLUDED.model_payload IS NOT NULL THEN EXCLUDED.baseline_mae_km ELSE forecast_model_artifacts.baseline_mae_km END,
                      last_attempt_at = EXCLUDED.last_attempt_at,
                      last_attempt_status = EXCLUDED.last_attempt_status,
                      last_attempt_samples = EXCLUDED.last_attempt_samples,
                      last_attempt_model_mae_km = EXCLUDED.last_attempt_model_mae_km,
                      last_attempt_baseline_mae_km = EXCLUDED.last_attempt_baseline_mae_km
                    """,
                    values,
                )
        else:
            connection.execute(
                """
                INSERT INTO forecast_model_artifacts
                (model_key, model_payload, model_trained_at, training_samples, validation_samples,
                 model_mae_km, baseline_mae_km, last_attempt_at, last_attempt_status,
                 last_attempt_samples, last_attempt_model_mae_km, last_attempt_baseline_mae_km)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_key) DO UPDATE SET
                  model_payload = COALESCE(excluded.model_payload, forecast_model_artifacts.model_payload),
                  model_trained_at = COALESCE(excluded.model_trained_at, forecast_model_artifacts.model_trained_at),
                  training_samples = CASE WHEN excluded.model_payload IS NOT NULL THEN excluded.training_samples ELSE forecast_model_artifacts.training_samples END,
                  validation_samples = CASE WHEN excluded.model_payload IS NOT NULL THEN excluded.validation_samples ELSE forecast_model_artifacts.validation_samples END,
                  model_mae_km = CASE WHEN excluded.model_payload IS NOT NULL THEN excluded.model_mae_km ELSE forecast_model_artifacts.model_mae_km END,
                  baseline_mae_km = CASE WHEN excluded.model_payload IS NOT NULL THEN excluded.baseline_mae_km ELSE forecast_model_artifacts.baseline_mae_km END,
                  last_attempt_at = excluded.last_attempt_at,
                  last_attempt_status = excluded.last_attempt_status,
                  last_attempt_samples = excluded.last_attempt_samples,
                  last_attempt_model_mae_km = excluded.last_attempt_model_mae_km,
                  last_attempt_baseline_mae_km = excluded.last_attempt_baseline_mae_km
                """,
                values,
            )
        connection.commit()
    finally:
        connection.close()


def train_forecast_model(force=False):
    if not _training_lock.acquire(blocking=False):
        return {"status": "training_in_progress", "active": False}

    try:
        artifact = _read_artifact()
        now = time.time()
        if not force and artifact:
            last_attempt_at = float(artifact["last_attempt_at"] or 0.0)
            last_attempt_status = artifact["last_attempt_status"]
            elapsed_since_attempt = now - last_attempt_at

            if (
                last_attempt_status == "not_promoted_baseline_better"
                and elapsed_since_attempt < NON_PROMOTION_RETRY_SECONDS
            ):
                return {
                    "status": "skipped_recently_evaluated",
                    "active": artifact["model_payload"] is not None,
                    "last_attempt_status": last_attempt_status,
                }

            if (
                last_attempt_status == "training_error"
                and elapsed_since_attempt < TRAINING_ERROR_RETRY_SECONDS
            ):
                return {
                    "status": "skipped_recent_training_error",
                    "active": artifact["model_payload"] is not None,
                    "last_attempt_status": last_attempt_status,
                }

            if artifact["model_payload"] is not None:
                trained_at = float(artifact["model_trained_at"] or 0.0)
                if now - trained_at < RETRAIN_INTERVAL_SECONDS:
                    return {"status": "skipped_recently_trained", "active": True, "trained_at": trained_at}

        histories = _load_training_histories()
        span = max((points[-1]["time"] - points[0]["time"] for points in histories.values() if len(points) > 1), default=0.0)
        samples = build_training_samples(histories)

        if len(samples) < MIN_SAMPLES or span < MIN_HISTORY_SPAN_SECONDS:
            _write_attempt("collecting_data", len(samples))
            return {
                "status": "collecting_data",
                "active": bool(artifact and artifact["model_payload"] is not None),
                "samples": len(samples),
                "minimum_samples": MIN_SAMPLES,
                "history_span_minutes": round(span / 60.0, 1),
                "minimum_history_minutes": MIN_HISTORY_SPAN_SECONDS // 60,
            }

        unique_times = sorted({sample["time"] for sample in samples})
        cutoff = unique_times[max(1, min(int(len(unique_times) * 0.8), len(unique_times) - 1))]
        training_pool = [sample for sample in samples if sample["time"] < cutoff]
        validation_pool = [sample for sample in samples if sample["time"] >= cutoff]
        training_samples = _even_sample(training_pool, MAX_TRAINING_SAMPLES)
        validation_samples = _even_sample(validation_pool, MAX_VALIDATION_SAMPLES)

        if len(training_samples) < MIN_TRAINING_SAMPLES or len(validation_samples) < MIN_VALIDATION_SAMPLES:
            _write_attempt("collecting_data", len(samples), len(training_samples), len(validation_samples))
            return {
                "status": "collecting_data",
                "active": bool(artifact and artifact["model_payload"] is not None),
                "samples": len(samples),
                "training_samples": len(training_samples),
                "validation_samples": len(validation_samples),
            }

        model = RandomForestRegressor(
            n_estimators=60,
            max_depth=16,
            min_samples_leaf=4,
            max_features=0.9,
            random_state=42,
            n_jobs=1,
        )
        model.fit(
            [sample["features"] for sample in training_samples],
            [sample["target"] for sample in training_samples],
        )

        predictions = model.predict([sample["features"] for sample in validation_samples])
        model_error = _mean_error_m(predictions, validation_samples, "target")
        baseline_error = _mean_error_m(
            [sample["baseline"] for sample in validation_samples],
            validation_samples,
            "target",
        )
        model_mae_km = round(model_error / 1000.0, 4)
        baseline_mae_km = round(baseline_error / 1000.0, 4)

        if model_error > baseline_error * 0.97:
            _write_attempt(
                "not_promoted_baseline_better", len(samples), len(training_samples),
                len(validation_samples), model_mae_km, baseline_mae_km,
            )
            return {
                "status": "not_promoted_baseline_better",
                "active": bool(artifact and artifact["model_payload"] is not None),
                "samples": len(samples),
                "training_samples": len(training_samples),
                "validation_samples": len(validation_samples),
                "model_mae_km": model_mae_km,
                "baseline_mae_km": baseline_mae_km,
                "required_improvement_percent": 3.0,
            }

        bundle = {
            "model": model,
            "feature_version": FEATURE_VERSION,
            "trained_at": time.time(),
            "training_samples": len(training_samples),
            "validation_samples": len(validation_samples),
            "model_mae_km": model_mae_km,
            "baseline_mae_km": baseline_mae_km,
        }
        buffer = io.BytesIO()
        pickle.dump(bundle, buffer, protocol=pickle.HIGHEST_PROTOCOL)
        payload = buffer.getvalue()
        _write_attempt(
            "promoted", len(samples), len(training_samples), len(validation_samples),
            model_mae_km, baseline_mae_km, payload,
        )

        global _model_cache, _model_cache_checked_at
        with _model_cache_lock:
            _model_cache = bundle
            _model_cache_checked_at = time.monotonic()

        return {
            "status": "promoted",
            "active": True,
            "samples": len(samples),
            "training_samples": len(training_samples),
            "validation_samples": len(validation_samples),
            "model_mae_km": model_mae_km,
            "baseline_mae_km": baseline_mae_km,
            "improvement_percent": round((baseline_mae_km - model_mae_km) / baseline_mae_km * 100, 2) if baseline_mae_km > 0 else None,
            "trained_at": bundle["trained_at"],
            "horizon_minutes": HORIZON_SECONDS // 60,
        }
    except Exception as error:
        try:
            _write_attempt("training_error", 0)
        except Exception:
            pass
        return {"status": "training_error", "active": False, "error": type(error).__name__}
    finally:
        _training_lock.release()


def _load_model():
    global _model_cache, _model_cache_checked_at
    now = time.monotonic()
    with _model_cache_lock:
        if now - _model_cache_checked_at < MODEL_CACHE_SECONDS:
            return _model_cache
        try:
            artifact = _read_artifact()
            if not artifact or artifact["model_payload"] is None:
                _model_cache = None
            else:
                bundle = pickle.loads(bytes(artifact["model_payload"]))
                _model_cache = bundle if bundle.get("feature_version") == FEATURE_VERSION else None
        except Exception:
            _model_cache = None
        _model_cache_checked_at = now
        return _model_cache


def predict_three_minute(history):
    cleaned = _clean_history(history or [])
    if len(cleaned) < LAG_COUNT + 1:
        return None

    bundle = _load_model()
    if not bundle:
        return None

    try:
        north_m, east_m = [float(value) for value in bundle["model"].predict([_feature_vector(cleaned, len(cleaned) - 1)])[0]]
        current = cleaned[-1]
        latitude = current["latitude"]
        longitude = current["longitude"]
        speed_kmh = max(0.0, min(120.0, current["speed"]))
        max_distance_m = max(350.0, speed_kmh * 50.0 * 1.6 + 200.0)
        distance_m = math.hypot(north_m, east_m)
        if distance_m > max_distance_m and distance_m > 0:
            scale = max_distance_m / distance_m
            north_m *= scale
            east_m *= scale

        predicted_latitude = latitude + north_m / 111320.0
        longitude_scale = 111320.0 * max(0.15, math.cos(math.radians(latitude)))
        predicted_longitude = longitude + east_m / longitude_scale
        if not (27.70 <= predicted_latitude <= 29.20 and 76.70 <= predicted_longitude <= 78.10):
            return None

        return {
            "latitude": round(predicted_latitude, 6),
            "longitude": round(predicted_longitude, 6),
            "model_type": "RandomForestRegressor",
            "horizon_minutes": HORIZON_SECONDS // 60,
            "model_mae_km": bundle.get("model_mae_km"),
            "baseline_mae_km": bundle.get("baseline_mae_km"),
            "trained_at": bundle.get("trained_at"),
            "model_version": FEATURE_VERSION,
        }
    except Exception:
        return None
