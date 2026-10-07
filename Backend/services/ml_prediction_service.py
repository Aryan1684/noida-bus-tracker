import math
import os
import sqlite3
import time
from datetime import datetime, timezone

from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge

from utils.distance import calculate_distance

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_PATH = os.getenv("PREDICTION_DB_PATH", "/tmp/noidabus_prediction_history.sqlite3")
MAX_HISTORY = 10
MODEL_HISTORY = 10
MIN_MODEL_POINTS = 3
_initialized = False


def _connect():
    global _initialized

    if DATABASE_URL:
        import psycopg

        connection = psycopg.connect(DATABASE_URL, connect_timeout=8)

        if not _initialized:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bus_positions (
                        id BIGSERIAL PRIMARY KEY,
                        bus_id VARCHAR(80) NOT NULL,
                        source_timestamp TEXT NOT NULL DEFAULT '',
                        event_time DOUBLE PRECISION NOT NULL,
                        latitude DOUBLE PRECISION NOT NULL,
                        longitude DOUBLE PRECISION NOT NULL,
                        speed DOUBLE PRECISION,
                        UNIQUE (bus_id, source_timestamp, latitude, longitude)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bus_positions_bus_time ON bus_positions(bus_id, event_time DESC)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ingestion_log (
                        id BIGSERIAL PRIMARY KEY,
                        recorded_at TEXT NOT NULL,
                        buses_received INTEGER NOT NULL,
                        buses_accepted INTEGER NOT NULL,
                        buses_rejected INTEGER NOT NULL,
                        avg_gps_age_seconds DOUBLE PRECISION,
                        upstream_latency_ms DOUBLE PRECISION,
                        anomalies_detected INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            connection.commit()
            _initialized = True

        return connection

    connection = sqlite3.connect(SQLITE_PATH, timeout=10)

    if not _initialized:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bus_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_id TEXT NOT NULL,
                source_timestamp TEXT NOT NULL DEFAULT '',
                event_time REAL NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed REAL,
                UNIQUE (bus_id, source_timestamp, latitude, longitude)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_bus_positions_bus_time ON bus_positions(bus_id, event_time DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                buses_received INTEGER NOT NULL,
                buses_accepted INTEGER NOT NULL,
                buses_rejected INTEGER NOT NULL,
                avg_gps_age_seconds REAL,
                upstream_latency_ms REAL,
                anomalies_detected INTEGER NOT NULL DEFAULT 0
            )
            """
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


def _insert_positions(connection, rows):
    if DATABASE_URL:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO bus_positions
                (bus_id, source_timestamp, event_time, latitude, longitude, speed)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (bus_id, source_timestamp, latitude, longitude) DO NOTHING
                """,
                rows,
            )
    else:
        connection.executemany(
            """
            INSERT OR IGNORE INTO bus_positions
            (bus_id, source_timestamp, event_time, latitude, longitude, speed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def record_validation_audit(validation):
    connection = _connect()
    recorded_at = datetime.now(timezone.utc).isoformat()
    rows = []

    for item in validation.get("accepted", []):
        rows.append((
            recorded_at, item.get("bus_id"), item.get("upstream_id"),
            "accepted", "accepted", item.get("timestamp"),
            item.get("latitude"), item.get("longitude"),
            str(item.get("validation_trace") or {}),
        ))

    for item in validation.get("rejected", []):
        details = item.get("details") or {}
        rows.append((
            recorded_at, item.get("bus_id"), item.get("upstream_id"),
            "rejected", item.get("reason") or "unknown",
            item.get("timestamp"), details.get("latitude"),
            details.get("longitude"), str(details),
        ))

    try:
        if not rows:
            return
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO gps_validation_log
                    (recorded_at, bus_id, upstream_id, status, reason,
                     event_timestamp, latitude, longitude, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
        else:
            connection.executemany(
                """
                INSERT INTO gps_validation_log
                (recorded_at, bus_id, upstream_id, status, reason,
                 event_timestamp, latitude, longitude, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        connection.commit()
    finally:
        connection.close()


def record_ingestion_log(
    recorded_at,
    buses_received,
    buses_accepted,
    buses_rejected,
    avg_gps_age_seconds,
    upstream_latency_ms,
    anomalies_detected,
):
    connection = _connect()
    try:
        values = (
            recorded_at,
            int(buses_received),
            int(buses_accepted),
            int(buses_rejected),
            avg_gps_age_seconds,
            upstream_latency_ms,
            int(anomalies_detected),
        )

        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ingestion_log
                    (recorded_at, buses_received, buses_accepted, buses_rejected,
                     avg_gps_age_seconds, upstream_latency_ms, anomalies_detected)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    values,
                )
        else:
            connection.execute(
                """
                INSERT INTO ingestion_log
                (recorded_at, buses_received, buses_accepted, buses_rejected,
                 avg_gps_age_seconds, upstream_latency_ms, anomalies_detected)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

        connection.commit()
    finally:
        connection.close()


def _prune_positions(connection, bus_ids):
    for bus_id in bus_ids:
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM bus_positions
                    WHERE bus_id = %s
                      AND id NOT IN (
                          SELECT id
                          FROM bus_positions
                          WHERE bus_id = %s
                          ORDER BY event_time DESC, id DESC
                          LIMIT %s
                      )
                    """,
                    (bus_id, bus_id, MAX_HISTORY),
                )
        else:
            connection.execute(
                """
                DELETE FROM bus_positions
                WHERE bus_id = ?
                  AND id NOT IN (
                      SELECT id
                      FROM bus_positions
                      WHERE bus_id = ?
                      ORDER BY event_time DESC, id DESC
                      LIMIT ?
                  )
                """,
                (bus_id, bus_id, MAX_HISTORY),
            )


def _latest_event_time(connection, bus_id):
    if DATABASE_URL:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT event_time FROM bus_positions WHERE bus_id = %s ORDER BY event_time DESC, id DESC LIMIT 1",
                (bus_id,),
            )
            row = cursor.fetchone()
    else:
        row = connection.execute(
            "SELECT event_time FROM bus_positions WHERE bus_id = ? ORDER BY event_time DESC, id DESC LIMIT 1",
            (bus_id,),
        ).fetchone()

    return float(row[0]) if row else None


def _is_plausible_transition(connection, bus_id, event_time, latitude, longitude, speed):
    latest_time = _latest_event_time(connection, bus_id)

    if latest_time is not None and event_time <= latest_time:
        return False

    if latest_time is None:
        return True

    if DATABASE_URL:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT latitude, longitude, speed
                FROM bus_positions
                WHERE bus_id = %s
                ORDER BY event_time DESC, id DESC
                LIMIT 1
                """,
                (bus_id,),
            )
            row = cursor.fetchone()
    else:
        row = connection.execute(
            """
            SELECT latitude, longitude, speed
            FROM bus_positions
            WHERE bus_id = ?
            ORDER BY event_time DESC, id DESC
            LIMIT 1
            """,
            (bus_id,),
        ).fetchone()

    if not row:
        return True

    delta_seconds = event_time - latest_time
    if delta_seconds <= 0:
        return False

    distance_km = calculate_distance(float(row[0]), float(row[1]), latitude, longitude)
    implied_speed = distance_km / (delta_seconds / 3600.0)
    reference_speed = max(float(row[2] or 0.0), float(speed or 0.0))

    return not (
        distance_km > 0.8
        and implied_speed > max(130.0, reference_speed + 90.0)
    )


def load_latest_points(bus_ids):
    connection = _connect()
    points = {}

    try:
        for bus_id in bus_ids:
            normalized_id = str(bus_id).strip().upper()

            if DATABASE_URL:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT source_timestamp, event_time, latitude, longitude, speed
                        FROM bus_positions
                        WHERE bus_id = %s
                        ORDER BY event_time DESC, id DESC
                        LIMIT 1
                        """,
                        (normalized_id,),
                    )
                    row = cursor.fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT source_timestamp, event_time, latitude, longitude, speed
                    FROM bus_positions
                    WHERE bus_id = ?
                    ORDER BY event_time DESC, id DESC
                    LIMIT 1
                    """,
                    (normalized_id,),
                ).fetchone()

            if row:
                points[normalized_id] = {
                    "timestamp": row[0],
                    "event_time": float(row[1]),
                    "latitude": float(row[2]),
                    "longitude": float(row[3]),
                    "speed": float(row[4] or 0.0),
                }
    finally:
        connection.close()

    return points


def record_positions(buses):
    connection = _connect()
    rows = []
    seen = set()

    try:
        for bus in buses:
            bus_id = str(bus.get("bus_id") or "").strip().upper()
            latitude = _safe_float(bus.get("latitude"), math.nan)
            longitude = _safe_float(bus.get("longitude"), math.nan)
            source_timestamp = str(bus.get("timestamp") or "").strip()
            event_time = _parse_timestamp(source_timestamp)

            if (
                not bus_id
                or not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or event_time is None
            ):
                continue

            key = (bus_id, source_timestamp, latitude, longitude)
            if key in seen:
                continue

            seen.add(key)
            speed = _safe_float(bus.get("speed"), 0.0)
            rows.append((bus_id, source_timestamp, event_time, latitude, longitude, speed))

        if not rows:
            return

        _insert_positions(connection, rows)
        _prune_positions(connection, sorted({row[0] for row in rows}))
        connection.commit()
    finally:
        connection.close()



