import json
import os
import secrets
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_PATH = os.getenv("ANALYTICS_SQLITE_PATH", "/tmp/noidabus_analytics.sqlite3")

ALLOWED_EVENTS = {
    "app_open",
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

EVENT_COLUMNS = {
    "visitor_id": "VARCHAR(100)",
    "source": "VARCHAR(30)",
    "device_type": "VARCHAR(30)",
    "browser": "VARCHAR(50)",
    "os": "VARCHAR(50)",
    "language": "VARCHAR(20)",
    "referrer": "TEXT",
    "screen_width": "INTEGER",
    "screen_height": "INTEGER",
    "app_version": "VARCHAR(40)",
}


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
                        event_name VARCHAR(80) NOT NULL,
                        event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        path TEXT,
                        session_id VARCHAR(100),
                        visitor_id VARCHAR(100),
                        source VARCHAR(30),
                        device_type VARCHAR(30),
                        browser VARCHAR(50),
                        os VARCHAR(50),
                        language VARCHAR(20),
                        referrer TEXT,
                        screen_width INTEGER,
                        screen_height INTEGER,
                        app_version VARCHAR(40),
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        coarse_lat DOUBLE PRECISION,
                        coarse_lon DOUBLE PRECISION
                    )
                    """
                )
                for name, sql_type in EVENT_COLUMNS.items():
                    cursor.execute(
                        f"ALTER TABLE analytics_events ADD COLUMN IF NOT EXISTS {name} {sql_type}"
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
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_analytics_events_visitor ON analytics_events(visitor_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_analytics_events_source ON analytics_events(source)"
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
                    source TEXT,
                    device_type TEXT,
                    browser TEXT,
                    os TEXT,
                    language TEXT,
                    referrer TEXT,
                    screen_width INTEGER,
                    screen_height INTEGER,
                    app_version TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    coarse_lat REAL,
                    coarse_lon REAL
                )
                """
            )
            existing = {
                row[1]
                for row in connection.execute("PRAGMA table_info(analytics_events)").fetchall()
            }
            sqlite_types = {
                "visitor_id": "TEXT",
                "source": "TEXT",
                "device_type": "TEXT",
                "browser": "TEXT",
                "os": "TEXT",
                "language": "TEXT",
                "referrer": "TEXT",
                "screen_width": "INTEGER",
                "screen_height": "INTEGER",
                "app_version": "TEXT",
            }
            for name, sql_type in sqlite_types.items():
                if name not in existing:
                    connection.execute(
                        f"ALTER TABLE analytics_events ADD COLUMN {name} {sql_type}"
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
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_visitor ON analytics_events(visitor_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_source ON analytics_events(source)"
            )

        connection.commit()
        _initialized = True
    finally:
        connection.close()


def _clean_text(value, limit):
    if value is None:
        return None
    return str(value)[:limit] or None


def _clean_metadata(metadata):
    if not isinstance(metadata, dict):
        return {}

    cleaned = {}

    for key, value in metadata.items():
        key = str(key)[:40]

        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[key] = value

    return cleaned


def record_event(
    event_name,
    path=None,
    session_id=None,
    visitor_id=None,
    source="web",
    device_type=None,
    browser=None,
    os_name=None,
    language=None,
    referrer=None,
    screen_width=None,
    screen_height=None,
    app_version=None,
    metadata=None,
    coarse_lat=None,
    coarse_lon=None,
):
    if event_name not in ALLOWED_EVENTS:
        return False

    _init_db()

    metadata = _clean_metadata(metadata or {})
    path = _clean_text(path, 500)
    session_id = _clean_text(session_id, 100)
    visitor_id = _clean_text(visitor_id, 100)
    source = _clean_text(source or "web", 30) or "web"
    device_type = _clean_text(device_type, 30)
    browser = _clean_text(browser, 50)
    os_name = _clean_text(os_name, 50)
    language = _clean_text(language, 20)
    referrer = _clean_text(referrer, 300)
    app_version = _clean_text(app_version, 40)

    screen_width = int(screen_width) if isinstance(screen_width, (int, float)) else None
    screen_height = int(screen_height) if isinstance(screen_height, (int, float)) else None

    values = (
        event_name,
        path,
        session_id,
        visitor_id,
        source,
        device_type,
        browser,
        os_name,
        language,
        referrer,
        screen_width,
        screen_height,
        app_version,
        json.dumps(metadata),
        coarse_lat,
        coarse_lon,
    )

    if DATABASE_URL:
        connection = _connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO analytics_events
                    (
                        event_name, path, session_id, visitor_id, source,
                        device_type, browser, os, language, referrer,
                        screen_width, screen_height, app_version, metadata,
                        coarse_lat, coarse_lon
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    values,
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
                (
                    event_name, event_time, path, session_id, visitor_id, source,
                    device_type, browser, os, language, referrer,
                    screen_width, screen_height, app_version, metadata,
                    coarse_lat, coarse_lon
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_name,
                    datetime.now(timezone.utc).isoformat(),
                    *values,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    return True


def record_consented_location(
    latitude,
    longitude,
    path=None,
    session_id=None,
    visitor_id=None,
    source="web",
):
    latitude = round(float(latitude), 2)
    longitude = round(float(longitude), 2)

    return record_event(
        "location_shared",
        path=path,
        session_id=session_id,
        visitor_id=visitor_id,
        source=source,
        metadata={
            "location_mode": "user_consented_approximate",
        },
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
                    SELECT
                        event_name, event_time, path, session_id, visitor_id, source,
                        device_type, browser, os, language, referrer,
                        screen_width, screen_height, app_version,
                        metadata, coarse_lat, coarse_lon
                    FROM analytics_events
                    WHERE event_time >= %s
                    ORDER BY event_time ASC
                    LIMIT 100000
                    """,
                    (cutoff,),
                )
                rows = cursor.fetchall()
        else:
            rows = connection.execute(
                """
                SELECT
                    event_name, event_time, path, session_id, visitor_id, source,
                    device_type, browser, os, language, referrer,
                    screen_width, screen_height, app_version,
                    metadata, coarse_lat, coarse_lon
                FROM analytics_events
                WHERE event_time >= ?
                ORDER BY event_time ASC
                LIMIT 100000
                """,
                (cutoff.isoformat(),),
            ).fetchall()
    finally:
        connection.close()

    normalized = []

    for row in rows:
        (
            event_name,
            event_time,
            path,
            session_id,
            visitor_id,
            source,
            device_type,
            browser,
            os_name,
            language,
            referrer,
            screen_width,
            screen_height,
            app_version,
            metadata,
            coarse_lat,
            coarse_lon,
        ) = row

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
                "source": source or "web",
                "device_type": device_type or "unknown",
                "browser": browser or "unknown",
                "os": os_name or "unknown",
                "language": language or "unknown",
                "referrer": referrer or "",
                "screen_width": screen_width,
                "screen_height": screen_height,
                "app_version": app_version or "",
                "metadata": metadata if isinstance(metadata, dict) else {},
                "coarse_lat": coarse_lat,
                "coarse_lon": coarse_lon,
            }
        )

    return normalized


def _parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _daily_counts(rows, days):
    today = datetime.now(timezone.utc).date()
    buckets = {}

    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        buckets[day.isoformat()] = {
            "events": 0,
            "visitors": set(),
            "sessions": set(),
            "views": 0,
            "refreshes": 0,
            "selections": 0,
        }

    for row in rows:
        parsed = _parse_time(row["event_time"])
        if not parsed:
            continue

        key = parsed.date().isoformat()
        bucket = buckets.get(key)
        if not bucket:
            continue

        bucket["events"] += 1
        visitor = row["visitor_id"] or ("legacy-" + row["session_id"] if row["session_id"] else "")
        if visitor:
            bucket["visitors"].add(visitor)
        if row["session_id"]:
            bucket["sessions"].add(row["session_id"])
        if row["event_name"] == "page_view":
            bucket["views"] += 1
        if row["event_name"] == "refresh":
            bucket["refreshes"] += 1
        if row["event_name"] == "bus_selected":
            bucket["selections"] += 1

    return [
        {
            "date": date,
            "events": values["events"],
            "visitors": len(values["visitors"]),
            "sessions": len(values["sessions"]),
            "views": values["views"],
            "refreshes": values["refreshes"],
            "selections": values["selections"],
        }
        for date, values in buckets.items()
    ]


def _hourly_counts(rows):
    buckets = {
        hour: {
            "events": 0,
            "visitors": set(),
        }
        for hour in range(24)
    }

    for row in rows:
        parsed = _parse_time(row["event_time"])
        if not parsed:
            continue

        bucket = buckets[parsed.hour]
        bucket["events"] += 1
        visitor = row["visitor_id"] or ("legacy-" + row["session_id"] if row["session_id"] else "")
        if visitor:
            bucket["visitors"].add(visitor)

    return [
        {
            "hour": hour,
            "label": f"{hour:02d}:00",
            "events": values["events"],
            "visitors": len(values["visitors"]),
        }
        for hour, values in buckets.items()
    ]


def _distribution(rows, key, limit=12):
    counts = Counter()
    visitors = defaultdict(set)

    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] += 1
        visitor = row.get("visitor_id") or ("legacy-" + row.get("session_id", "") if row.get("session_id") else "")
        if visitor:
            visitors[value].add(visitor)

    return [
        {
            "name": name,
            "count": count,
            "visitors": len(visitors[name]),
        }
        for name, count in counts.most_common(limit)
    ]


def dashboard(days=30):
    rows = _read_rows(days)

    event_counts = Counter(row["event_name"] for row in rows)
    sessions = {row["session_id"] for row in rows if row["session_id"]}

    visitor_keys = set()
    visitor_days = defaultdict(set)

    for row in rows:
        visitor = row["visitor_id"] or ("legacy-" + row["session_id"] if row["session_id"] else "")
        if not visitor:
            continue
        visitor_keys.add(visitor)
        parsed = _parse_time(row["event_time"])
        if parsed:
            visitor_days[visitor].add(parsed.date().isoformat())

    returning_visitors = sum(1 for days_seen in visitor_days.values() if len(days_seen) >= 2)

    sessions_rows = defaultdict(list)
    for row in rows:
        if row["session_id"]:
            sessions_rows[row["session_id"]].append(row)

    durations = []
    bounce_sessions = 0

    for session_rows in sessions_rows.values():
        times = [_parse_time(row["event_time"]) for row in session_rows]
        times = [value for value in times if value]
        if len(times) > 1:
            duration = (max(times) - min(times)).total_seconds() / 60
            durations.append(min(duration, 60))
        if len(session_rows) <= 1:
            bounce_sessions += 1

    average_session_minutes = round(sum(durations) / len(durations), 2) if durations else 0
    bounce_rate = round(bounce_sessions / len(sessions), 3) if sessions else 0
    engaged_sessions = sum(1 for items in sessions_rows.values() if len(items) >= 2)
    average_events_per_session = round(len(rows) / len(sessions), 2) if sessions else 0

    platform_data = {}
    for source in ["web", "android", "unknown"]:
        platform_rows = [
            row for row in rows if (row["source"] or "web") == source
        ]
        platform_visitors = set()
        platform_sessions = set()
        for row in platform_rows:
            visitor = row["visitor_id"] or ("legacy-" + row["session_id"] if row["session_id"] else "")
            if visitor:
                platform_visitors.add(visitor)
            if row["session_id"]:
                platform_sessions.add(row["session_id"])
        platform_data[source] = {
            "visitors": len(platform_visitors),
            "sessions": len(platform_sessions),
            "views": sum(1 for row in platform_rows if row["event_name"] == "page_view" or row["event_name"] == "app_open"),
            "events": len(platform_rows),
            "selections": sum(1 for row in platform_rows if row["event_name"] == "bus_selected"),
            "app_opens": sum(1 for row in platform_rows if row["event_name"] == "app_open"),
        }

    total_platform_visitors = sum(item["visitors"] for item in platform_data.values() if item["visitors"])
    platforms = []

    for name, item in platform_data.items():
        item["name"] = name
        item["visitor_share"] = round(item["visitors"] / total_platform_visitors, 3) if total_platform_visitors else 0
        platforms.append(item)

    bus_counts = Counter()
    shared_buses = Counter()
    search_counts = Counter()
    path_counts = Counter()
    referrer_counts = Counter()

    for row in rows:
        path = row["path"]
        if path:
            path_counts[path] += 1

        if row["referrer"]:
            referrer_counts[row["referrer"]] += 1

        metadata = row["metadata"]

        if row["event_name"] == "bus_selected" and metadata.get("bus_id"):
            bus_counts[str(metadata["bus_id"])] += 1

        if row["event_name"] == "bus_shared" and metadata.get("bus_id"):
            shared_buses[str(metadata["bus_id"])] += 1

        if row["event_name"] == "place_search" and metadata.get("place"):
            search_counts[str(metadata["place"])] += 1

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

    recent = []

    for row in reversed(rows[-100:]):
        metadata = row["metadata"]
        recent.append(
            {
                "event": row["event_name"],
                "time": row["event_time"],
                "source": row["source"],
                "device": row["device_type"],
                "path": row["path"],
                "bus_id": str(metadata.get("bus_id", ""))[:80],
                "place": str(metadata.get("place", ""))[:120],
            }
        )
        if len(recent) >= 40:
            break

    return {
        "storage": storage_mode(),
        "days": days,
        "total_events": len(rows),
        "unique_visitors": len(visitor_keys),
        "unique_sessions": len(sessions),
        "returning_visitors": returning_visitors,
        "page_views": event_counts["page_view"],
        "refreshes": event_counts["refresh"],
        "location_uses": event_counts["location_used"],
        "location_shares": event_counts["location_shared"],
        "bus_selections": event_counts["bus_selected"],
        "bus_shares": event_counts["bus_shared"],
        "feedback_submitted": event_counts["feedback_submitted"],
        "reports_submitted": event_counts["report_submitted"],
        "pwa_installs": event_counts["pwa_install"],
        "average_session_minutes": average_session_minutes,
        "bounce_sessions": bounce_sessions,
        "bounce_rate": bounce_rate,
        "engaged_sessions": engaged_sessions,
        "average_events_per_session": average_events_per_session,
        "visitor_id_coverage": round(
            sum(1 for row in rows if row["visitor_id"]) / len(rows),
            3,
        ) if rows else 0,
        "platforms": platforms,
        "event_breakdown": [
            {"event": name, "count": count}
            for name, count in event_counts.most_common()
        ],
        "top_buses": [
            {"bus_id": bus_id, "count": count}
            for bus_id, count in bus_counts.most_common(15)
        ],
        "top_shared_buses": [
            {"bus_id": bus_id, "count": count}
            for bus_id, count in shared_buses.most_common(15)
        ],
        "top_searches": [
            {"name": name, "count": count}
            for name, count in search_counts.most_common(15)
        ],
        "top_paths": [
            {"name": path, "count": count}
            for path, count in path_counts.most_common(15)
        ],
        "referrers": [
            {"name": name, "count": count}
            for name, count in referrer_counts.most_common(10)
        ],
        "browsers": _distribution(rows, "browser"),
        "oses": _distribution(rows, "os"),
        "devices": _distribution(rows, "device_type"),
        "languages": _distribution(rows, "language"),
        "app_versions": _distribution(rows, "app_version"),
        "daily": _daily_counts(rows, min(days, 31)),
        "hourly": _hourly_counts(rows),
        "location_cells": safe_locations[:100],
        "recent_events": recent,
    }


def verify_admin_token(token):
    configured = os.getenv("ADMIN_TOKEN", "")

    if not configured or not token:
        return False

    return secrets.compare_digest(configured, token)
