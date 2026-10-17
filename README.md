# Noida Bus Tracker

An independent web app for exploring Noida electric-bus GPS locations, nearby vehicles, movement history, estimated direction/ETA, and user-submitted service feedback.

## Architecture

- `frontend/`: static website hosted on Netlify.
- `Backend/`: FastAPI service hosted separately; serves GPS data, nearby-bus queries, route context, maintenance controls, analytics, feedback, and reports.
- `Backend/services/gps_service.py`: upstream feed snapshots and GPS freshness.
- `Backend/services/direction_service.py` and `Backend/services/eta_service.py`: route context and movement/ETA enrichment.
- `Backend/services/analytics_service.py`: analytics storage and admin reporting.
- PostgreSQL is used when `DATABASE_URL` is configured. The SQLite fallback is ephemeral on many hosting platforms and is intended for local/development use.

## Local development

Requirements: Python version specified in `.python-version`.

```bash
cd Backend
python -m venv .venv
```

Activate the virtual environment, then install dependencies and start the API:

```bash
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

The API root is `http://127.0.0.1:8000/`. Interactive API documentation is available at `/docs` while the development server is running.

Serve `frontend/` through a local static server. The deployed frontend is configured to call the production API, so local frontend testing may require updating the API base URL in the relevant frontend scripts.

## Configuration

Set secrets in the hosting provider's environment-variable settings, not in source control.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string for persistent analytics and maintenance settings |
| `ADMIN_TOKEN` | Secret used to authenticate admin API requests |
| `MAPTILER_API_KEY` | Map/location search provider key |
| `WEB3FORMS_FEEDBACK_KEY` | Backend feedback submission key |
| `WEB3FORMS_REPORT_KEY` | Backend bus-report submission key |
| `GPS_REFRESH_INTERVAL_SECONDS` | GPS refresh cadence, where supported by the collector |
| `ANALYTICS_SQLITE_PATH` | Optional local SQLite path when PostgreSQL is not configured |

See `.env.example` for the currently documented environment variables. Do not commit real tokens, database credentials, or provider keys.

## Key endpoints

- `GET /`: API/service information.
- `GET /api/health`: GPS snapshot and collector health.
- `GET /api/livez`: process liveness.
- `GET /api/maintenance`: public maintenance status.
- `GET /api/buses`: available bus snapshot.
- `GET /api/buses/nearby?lat=28.6&lon=77.3&radius=5`: nearby buses; replace coordinates with a supported location.
- `GET /api/routes`: route/landmark context.
- `POST /api/analytics/event`: product analytics event.
- `POST /api/analytics/location`: optional, visitor-confirmed approximate location sharing.
- `GET/POST /api/admin/maintenance`: authenticated maintenance controls.
- `GET /api/admin/analytics`: authenticated analytics dashboard data.

Admin endpoints require the `X-Admin-Token` header. Never expose the admin token in frontend code.

## Maintenance mode

The admin API stores maintenance state and an optional expiry. While maintenance is enabled, tracker API operations return HTTP 503 with a maintenance response. The public maintenance-status endpoint remains available so the static site can redirect users, and authenticated admin routes remain available so maintenance can be disabled.

## Privacy

Basic product analytics does not require browser GPS. The admin heat map uses only approximate locations visitors deliberately share through the separate location-sharing control. The map suppresses cells with fewer than three distinct visitor identifiers. Hosting and network providers may process request metadata under their own policies; see `frontend/privacy.html`.

## Tests

Run backend unit tests:

```bash
cd Backend
python -m unittest discover -s tests -v
```

GitHub Actions also runs JavaScript syntax checks for files in `frontend/*.js`. These checks catch syntax errors but do not replace browser-based end-to-end, accessibility, performance, or live-provider tests.

## Deployment checklist

1. Configure persistent PostgreSQL and all required environment variables.
2. Confirm `/api/health` reports a healthy collector and fresh GPS snapshot.
3. Confirm the frontend API base URL points to the intended backend.
4. Test maintenance enable, expiry, manual disable, and tracker API blocking.
5. Verify optional location sharing and ensure declined sharing does not add a heat-map location.
6. Test feedback/report submission, admin authentication, and database retention.
7. Review the privacy notice whenever analytics collection or third-party providers change.

This is an independent project and is not affiliated with UPSRTC or any government department. GPS availability, estimated directions, and ETA may be delayed or inaccurate; do not treat estimates as official dispatch information.
