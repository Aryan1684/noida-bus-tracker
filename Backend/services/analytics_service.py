import json
import os
import queue
import secrets
import sqlite3
import threading
from urllib.parse import urlparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

INDIA_TIMEZONE = timezone(timedelta(hours=5, minutes=30))

DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_PATH = os.getenv("ANALYTICS_SQLITE_PATH", "/tmp/noidabus_analytics.sqlite3")

ALLOWED_EVENTS = {
    "app_open",
    "first_open",
    "page_view",
    "routes_opened",
    "favorite_added",
    "favorite_removed",
    "favorites_opened",
    "bus_follow_toggled",
    "movement_trail_opened",
    "playback_opened",
    "eta_requested",
    "settings_opened",
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
_event_queue = queue.Queue(maxsize=1000)
_event_worker = None
_event_worker_lock = threading.Lock()

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
    if not DATABASE_URL:
        return "sqlite-ephemeral"

    host = (urlparse(DATABASE_URL).hostname or "").lower()
    if host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com"):
        return "supabase-postgresql"

    return "postgresql"


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
                cursor.execute("ALTER TABLE public.analytics_events ENABLE ROW LEVEL SECURITY")
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


def _write_event(
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



def _run_event_worker():
    while True:
        payload = _event_queue.get()
        try:
            _write_event(**payload)
        except Exception as error:
            print(f"Analytics event write failed: {error}", flush=True)
        finally:
            _event_queue.task_done()


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
    global _event_worker

    if event_name not in ALLOWED_EVENTS:
        return False

    payload = {
        "event_name": event_name,
        "path": path,
        "session_id": session_id,
        "visitor_id": visitor_id,
        "source": source,
        "device_type": device_type,
        "browser": browser,
        "os_name": os_name,
        "language": language,
        "referrer": referrer,
        "screen_width": screen_width,
        "screen_height": screen_height,
        "app_version": app_version,
        "metadata": metadata,
        "coarse_lat": coarse_lat,
        "coarse_lon": coarse_lon,
    }

    with _event_worker_lock:
        if _event_worker is None or not _event_worker.is_alive():
            _event_worker = threading.Thread(
                target=_run_event_worker,
                name="analytics-writer",
                daemon=True,
            )
            _event_worker.start()

    try:
        _event_queue.put_nowait(payload)
        return True
    except queue.Full:
        print("Analytics event queue full; event dropped", flush=True)
        return False

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


def _read_rows(days=30, hours=None):
    _init_db()
    now = datetime.now(timezone.utc)
    cutoff = now - (timedelta(hours=hours) if hours is not None else timedelta(days=days))

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
                    ORDER BY event_time DESC
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
                ORDER BY event_time DESC
                LIMIT 100000
                """,
                (cutoff.isoformat(),),
            ).fetchall()
    finally:
        connection.close()

    rows.reverse()
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


def _traffic_series(rows, days=30, hours=None):
    now = datetime.now(timezone.utc)
    span = timedelta(hours=hours) if hours is not None else timedelta(days=days)
    cutoff = now - span

    if hours is not None:
        bucket_count = hours
        step = timedelta(hours=1)
        granularity = "hour"
        starts = [cutoff + step * index for index in range(bucket_count)]
        labels = [
            value.astimezone(INDIA_TIMEZONE).strftime("%H:%M")
            for value in starts
        ]
    elif days > 60:
        bucket_count = (days + 6) // 7
        step = timedelta(days=7)
        granularity = "week"
        starts = [cutoff + step * index for index in range(bucket_count)]
        labels = [value.astimezone(INDIA_TIMEZONE).strftime("%d %b") for value in starts]
    else:
        bucket_count = days
        step = timedelta(days=1)
        granularity = "day"
        starts = [cutoff + step * index for index in range(bucket_count)]
        labels = [value.astimezone(INDIA_TIMEZONE).strftime("%d %b") for value in starts]

    buckets = [
        {
            "events": 0,
            "visitors": set(),
            "sessions": set(),
            "views": 0,
            "refreshes": 0,
            "selections": 0,
        }
        for _ in range(bucket_count)
    ]

    for row in rows:
        parsed = _parse_time(row["event_time"])
        if not parsed or parsed < cutoff or parsed > now:
            continue
        local_time = parsed.astimezone(INDIA_TIMEZONE)
        if granularity == "hour":
            index = int((parsed - starts[0].astimezone(timezone.utc)).total_seconds() // step.total_seconds())
        else:
            index = int((parsed - cutoff).total_seconds() // step.total_seconds())
        if index < 0 or index >= bucket_count:
            continue

        bucket = buckets[index]
        bucket["events"] += 1
        visitor = row["visitor_id"] or ("legacy-" + row["session_id"] if row["session_id"] else "")
        if visitor:
            bucket["visitors"].add(visitor)
        if row["session_id"]:
            bucket["sessions"].add(row["session_id"])
        if row["event_name"] in {"page_view", "app_open"}:
            bucket["views"] += 1
        if row["event_name"] == "refresh":
            bucket["refreshes"] += 1
        if row["event_name"] == "bus_selected":
            bucket["selections"] += 1

    return [
        {
            "date": starts[index].astimezone(INDIA_TIMEZONE).date().isoformat(),
            "label": labels[index],
            "events": values["events"],
            "visitors": len(values["visitors"]),
            "sessions": len(values["sessions"]),
            "views": values["views"],
            "refreshes": values["refreshes"],
            "selections": values["selections"],
        }
        for index, values in enumerate(buckets)
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

        bucket = buckets[parsed.astimezone(INDIA_TIMEZONE).hour]
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



def _read_mobile_install_rows():
    _init_db()
    connection = _connect()

    try:
        query = """
            SELECT event_time, visitor_id, app_version, metadata, coarse_lat, coarse_lon
            FROM analytics_events
            WHERE event_name = 'first_open' AND source = 'android'
            ORDER BY event_time DESC
            LIMIT 100000
        """
        if DATABASE_URL:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
        else:
            rows = connection.execute(query).fetchall()
    finally:
        connection.close()

    normalized = []
    for event_time, visitor_id, app_version, metadata, coarse_lat, coarse_lon in rows:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (TypeError, ValueError):
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        if hasattr(event_time, "isoformat"):
            event_time = event_time.isoformat()
        normalized.append({
            "event_time": str(event_time),
            "visitor_id": visitor_id or "",
            "app_version": app_version or "",
            "metadata": metadata,
            "coarse_lat": coarse_lat,
            "coarse_lon": coarse_lon,
        })
    return normalized


def _mobile_distribution(rows, field):
    installations = defaultdict(set)
    for row in rows:
        visitor_id = row.get("visitor_id")
        if not visitor_id:
            continue
        metadata = row.get("metadata") or {}
        value = str(metadata.get(field) or "Unknown").strip()[:100] or "Unknown"
        installations[value].add(visitor_id)
    return [
        {"name": name, "count": len(visitor_ids)}
        for name, visitor_ids in sorted(
            installations.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )[:25]
    ]


def mobile_dashboard(days=30, hours=None):
    activity_rows = [
        row for row in _read_rows(days=days, hours=hours)
        if str(row.get("source") or "").strip().lower() == "android"
    ]
    first_opens = _read_mobile_install_rows()
    install_ids = {row["visitor_id"] for row in first_opens if row["visitor_id"]}
    active_install_ids = {row["visitor_id"] for row in activity_rows if row["visitor_id"]}
    active_sessions = {row["session_id"] for row in activity_rows if row["session_id"]}
    event_counts = Counter(row["event_name"] for row in activity_rows)
    period_install_ids = {
        row["visitor_id"]
        for row in activity_rows
        if row.get("event_name") == "first_open" and row.get("visitor_id")
    }

    device_rows = []
    seen_device_rows = set()
    for row in first_opens:
        visitor_id = row.get("visitor_id")
        metadata = row.get("metadata") or {}
        if not visitor_id:
            continue
        key = (
            visitor_id,
            metadata.get("device_brand"),
            metadata.get("device_manufacturer"),
            metadata.get("device_model"),
            metadata.get("android_version"),
            row.get("app_version"),
        )
        if key in seen_device_rows:
            continue
        seen_device_rows.add(key)
        device_rows.append({
            "visitor_id": visitor_id,
            "app_version": row.get("app_version") or "",
            "metadata": metadata,
        })

    install_area_visitors = defaultdict(set)
    for row in first_opens:
        if not row.get("visitor_id") or row.get("coarse_lat") is None or row.get("coarse_lon") is None:
            continue
        cell = (round(float(row["coarse_lat"]), 2), round(float(row["coarse_lon"]), 2))
        install_area_visitors[cell].add(row["visitor_id"])

    install_areas = [
        {
            "latitude": latitude,
            "longitude": longitude,
            "count": len(visitor_ids),
            "name": "Approximate first-open area",
        }
        for (latitude, longitude), visitor_ids in sorted(
            install_area_visitors.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
        if len(visitor_ids) >= 3
    ]

    installs_with_area = len({
        row["visitor_id"] for row in first_opens
        if row.get("visitor_id") and row.get("coarse_lat") is not None and row.get("coarse_lon") is not None
    })
    period_label = f"Last {hours} hours" if hours is not None else f"Last {days} days"

    return {
        "storage": storage_mode(),
        "period_label": period_label,
        "window_hours": hours,
        "window_days": days if hours is None else None,
        "tracked_first_opens_all_time": len(install_ids),
        "tracked_first_opens_in_window": len(period_install_ids),
        "active_installations": len(active_install_ids),
        "active_sessions": len(active_sessions),
        "app_opens": event_counts["app_open"],
        "first_opens_in_window": event_counts["first_open"],
        "feature_events": sum(
            count for name, count in event_counts.items()
            if name not in {"app_open", "first_open"}
        ),
        "total_events": len(activity_rows),
        "daily": _traffic_series(activity_rows, days=days, hours=hours),
        "brands": _mobile_distribution(device_rows, "device_brand"),
        "manufacturers": _mobile_distribution(device_rows, "device_manufacturer"),
        "models": _mobile_distribution(device_rows, "device_model"),
        "android_versions": _mobile_distribution(device_rows, "android_version"),
        "app_versions": [
            {"name": name, "count": len(visitors)}
            for name, visitors in sorted(
                _group_mobile_versions(activity_rows).items(),
                key=lambda item: len(item[1]),
                reverse=True,
            )[:20]
        ],
        "event_breakdown": [
            {"name": name, "count": count}
            for name, count in event_counts.most_common(20)
        ],
        "install_areas": install_areas[:100],
        "tracked_installs_with_area": installs_with_area,
        "install_events_seen": len(first_opens),
        "tracking_note": "First opens count installation instances first observed after this analytics feature is released. This is not an exact Play Store install count or a count of unique physical phones. Area is an approximate IP-derived area at first app open, not GPS install location.",
    }


def _group_mobile_versions(rows):
    grouped = defaultdict(set)
    for row in rows:
        visitor_id = row.get("visitor_id")
        if not visitor_id:
            continue
        version = str(row.get("app_version") or "Unknown").strip()[:50] or "Unknown"
        grouped[version].add(visitor_id)
    return grouped




def dashboard(days=30, hours=None):
    rows = _read_rows(days=days, hours=hours)
    period_label = f"Last {hours} hours" if hours is not None else f"Last {days} days"
    latest_event_at = rows[-1]["event_time"] if rows else None
    series_granularity = "hour" if hours is not None else "week" if days > 60 else "day"

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
            visitor_days[visitor].add(parsed.astimezone(INDIA_TIMEZONE).date().isoformat())

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
    known_sources = ["web", "installed_app", "android", "ios", "unknown"]

    def normalized_source(row):
        value = str(row.get("source") or "web").strip().lower()
        return value if value in known_sources[:-1] else "unknown"

    for source in known_sources:
        platform_rows = [
            row for row in rows if normalized_source(row) == source
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

    location_visitors = defaultdict(set)

    for row in rows:
        if row["event_name"] != "location_shared":
            continue

        if row["coarse_lat"] is None or row["coarse_lon"] is None or not row["visitor_id"]:
            continue

        cell = (
            round(float(row["coarse_lat"]), 2),
            round(float(row["coarse_lon"]), 2),
        )
        location_visitors[cell].add(row["visitor_id"])

    location_cells = Counter({
        cell: len(visitors)
        for cell, visitors in location_visitors.items()
    })

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
        "database_provider": "Supabase" if storage_mode() == "supabase-postgresql" else "PostgreSQL" if storage_mode() == "postgresql" else "Temporary SQLite",
        "period_label": period_label,
        "window_hours": hours,
        "window_days": days if hours is None else None,
        "series_granularity": series_granularity,
        "latest_event_at": latest_event_at,
        "days": days,
        "total_events": len(rows),
        "unique_visitors": len(visitor_keys),
        "unique_sessions": len(sessions),
        "returning_visitors": returning_visitors,
        "page_views": event_counts["page_view"] + event_counts["app_open"],
        "browser_page_views": event_counts["page_view"],
        "app_opens": event_counts["app_open"],
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
        "daily": _traffic_series(rows, days=days, hours=hours),
        "hourly": _hourly_counts(rows),
        "location_cells": safe_locations[:100],
        "recent_events": recent,
    }


def verify_admin_token(token):
    configured = os.getenv("ADMIN_TOKEN", "")

    if not configured or not token:
        return False

    return secrets.compare_digest(configured, token)
