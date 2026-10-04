import json
import os
import secrets
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_PATH = os.getenv("ANALYTICS_SQLITE_PATH", "/tmp/noidabus_analytics.sqlite3")

ALLOWED_EVENTS = {
    "page_view",
    "refresh",
    "location_used",
    "place_search",
    "bus_selected",
    "bus_shared",
    "location_shared",
    "feedback_opened",
    "feedback_submitted",
    "report_opened",
    "report_submitted",
    "pwa_install",
}

_initialized = False


def storage_mode():
    return "postgresql" if DATABASE_URL else "sqlite-ephemeral"


def _connect():
    if DATABASE_URL:
        import psycopg
        return psycopg.connect(DATABASE_URL, connect_timeout=8)

    return sqlite3.connect(SQLITE_PATH, timeout=10)


def _init_db():
    global _initialized

    if _initialized:
        return

    connection = _connect()

    try:
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analytics_events (
                        id BIGSERIAL PRIMARY KEY,
                        visitor_id VARCHAR(80),
                        event_name VARCHAR(80) NOT NULL,
                        event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        path TEXT,
                        session_id VARCHAR(80),
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        coarse_lat DOUBLE PRECISION,
                        coarse_lon DOUBLE PRECISION
                    )
                    """
                )
                cursor.execute(
                    "ALTER TABLE analytics_events ADD COLUMN IF NOT EXISTS visitor_id VARCHAR(80)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_analytics_events_visitor ON analytics_events(visitor_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_analytics_events_time ON analytics_events(event_time)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_analytics_events_name ON analytics_events(event_name)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_analytics_events_session ON analytics_events(session_id)"
                )
        else:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    path TEXT,
                    session_id TEXT,
                    visitor_id TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    coarse_lat REAL,
                    coarse_lon REAL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_time ON analytics_events(event_time)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_name ON analytics_events(event_name)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_session ON analytics_events(session_id)"
            )

        connection.commit()
        _initialized = True
    finally:
        connection.close()


def _event_time_iso():
    return datetime.now(timezone.utc).isoformat()


def _clean_metadata(metadata):
    if not isinstance(metadata, dict):
        return {}

    cleaned = {}

    for key, value in metadata.items():
        key = str(key)[:40]

        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[key] = value

    return cleaned


def record_event(event_name, path=None, session_id=None, metadata=None, coarse_lat=None, coarse_lon=None):
    if event_name not in ALLOWED_EVENTS:
        return False

    _init_db()

    metadata = _clean_metadata(metadata or {})
    path = str(path or "")[:500]
    session_id = str(session_id or "")[:80] or None
    visitor_id = str(visitor_id or "")[:80] or None

    if DATABASE_URL:
        connection = _connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO analytics_events
                    (event_name, path, session_id, visitor_id, metadata, coarse_lat, coarse_lon)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event_name,
                        path,
                        session_id,
                        visitor_id,
                        json.dumps(metadata),
                        coarse_lat,
                        coarse_lon,
                    ),
                )
            connection.commit()
        finally:
            connection.close()
    else:
        connection = _connect()

        try:
            connection.execute(
                """
                INSERT INTO analytics_events
                (event_name, event_time, path, session_id, visitor_id, metadata, coarse_lat, coarse_lon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_name,
                    _event_time_iso(),
                    path,
                    session_id,
                    visitor_id,
                    json.dumps(metadata),
                    coarse_lat,
                    coarse_lon,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    return True


def record_consented_location(latitude, longitude, path=None, session_id=None, visitor_id=None):
    latitude = round(float(latitude), 2)
    longitude = round(float(longitude), 2)

    return record_event(
        "location_shared",
        path=path,
        session_id=session_id,
        visitor_id=visitor_id,
        metadata={"source": "web", "location_mode": "user_consented_approximate"},
        coarse_lat=latitude,
        coarse_lon=longitude,
    )


def _read_rows(days):
    _init_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    connection = _connect()

    try:
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_name, event_time, path, session_id, visitor_id, metadata, coarse_lat, coarse_lon
                    FROM analytics_events
                    WHERE event_time >= %s
                    ORDER BY event_time ASC
                    LIMIT 50000
                    """,
                    (cutoff,),
                )
                rows = cursor.fetchall()
        else:
            rows = connection.execute(
                """
                SELECT event_name, event_time, path, session_id, visitor_id, metadata, coarse_lat, coarse_lon
                FROM analytics_events
                WHERE event_time >= ?
                ORDER BY event_time ASC
                LIMIT 50000
                """,
                (cutoff.isoformat(),),
            ).fetchall()
    finally:
        connection.close()

    normalized = []

    for event_name, event_time, path, session_id, visitor_id, metadata, coarse_lat, coarse_lon in rows:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (TypeError, ValueError):
                metadata = {}
        elif metadata is None:
            metadata = {}

        if hasattr(event_time, "isoformat"):
            event_time = event_time.isoformat()

        normalized.append(
            {
                "event_name": event_name,
                "event_time": str(event_time),
                "path": path or "",
                "session_id": session_id or "",
                "visitor_id": visitor_id or "",
                "metadata": metadata if isinstance(metadata, dict) else {},
                "coarse_lat": coarse_lat,
                "coarse_lon": coarse_lon,
            }
        )

    return normalized


def _daily_counts(rows, days):
    today = datetime.now(timezone.utc).date()
    counts = {}

    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        counts[day.isoformat()] = 0

    for row in rows:
        try:
            day = datetime.fromisoformat(
                row["event_time"].replace("Z", "+00:00")
            ).astimezone(timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            continue

        if day in counts:
            counts[day] += 1

    return [{"date": date, "events": count} for date, count in counts.items()]


def dashboard(days=30):
    rows = _read_rows(days)

    event_counts = Counter(row["event_name"] for row in rows)
    sessions = {row["session_id"] for row in rows if row["session_id"]}
    visitors = {row["visitor_id"] for row in rows if row["visitor_id"]}
    visitor_sessions = defaultdict(set)
    for row in rows:
        if row["visitor_id"] and row["session_id"]:
            visitor_sessions[row["visitor_id"]].add(row["session_id"])
    returning_visitors = sum(1 for session_set in visitor_sessions.values() if len(session_set) > 1)

    bus_counts = Counter()
    path_counts = Counter()

    for row in rows:
        if row["path"]:
            path_counts[row["path"]] += 1

        metadata = row["metadata"]

        if row["event_name"] == "bus_selected" and metadata.get("bus_id"):
            bus_counts[str(metadata["bus_id"])] += 1

    location_cells = Counter()

    for row in rows:
        if row["event_name"] != "location_shared":
            continue

        if row["coarse_lat"] is None or row["coarse_lon"] is None:
            continue

        cell = (
            round(float(row["coarse_lat"]), 2),
            round(float(row["coarse_lon"]), 2),
        )
        location_cells[cell] += 1

    safe_locations = [
        {
            "latitude": latitude,
            "longitude": longitude,
            "shares": count,
        }
        for (latitude, longitude), count in sorted(
            location_cells.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if count >= 3
    ]

    return {
        "storage": storage_mode(),
        "days": days,
        "total_events": len(rows),
        "unique_visitors": len(visitors),
        "unique_sessions": len(sessions),
        "returning_visitors": returning_visitors,
        "page_views": event_counts["page_view"],
        "refreshes": event_counts["refresh"],
        "location_uses": event_counts["location_used"],
        "location_shares": event_counts["location_shared"],
        "bus_selections": event_counts["bus_selected"],
        "feedback_submitted": event_counts["feedback_submitted"],
        "reports_submitted": event_counts["report_submitted"],
        "event_breakdown": [
            {"event": name, "count": count}
            for name, count in event_counts.most_common()
        ],
        "top_buses": [
            {"bus_id": bus_id, "count": count}
            for bus_id, count in bus_counts.most_common(10)
        ],
        "top_paths": [
            {"path": path, "count": count}
            for path, count in path_counts.most_common(10)
        ],
        "daily": _daily_counts(rows, min(days, 30)),
        "location_cells": safe_locations[:100],
    }


def verify_admin_token(token):
    configured = os.getenv("ADMIN_TOKEN", "")

    if not configured or not token:
        return False

    return secrets.compare_digest(configured, token)
