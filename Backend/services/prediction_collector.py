import os
import threading
import time

from services.gps_service import refresh_direct_snapshot

INTERVAL_SECONDS = max(30, int(os.getenv("GPS_REFRESH_INTERVAL_SECONDS", "60")))
FORECAST_TRAIN_CHECK_SECONDS = max(300, int(os.getenv("FORECAST_TRAIN_CHECK_SECONDS", "300")))

_stop_event = threading.Event()
_training_stop_event = threading.Event()
_thread = None
_training_thread = None


def _run():
    print("Live GPS collector thread started", flush=True)

    while not _stop_event.is_set():
        started = time.time()

        try:
            print("GPS snapshot collector fetching live feed", flush=True)
            buses = refresh_direct_snapshot()
            print(f"GPS snapshot collector refreshed {len(buses)} buses", flush=True)
        except Exception as error:
            print(f"Live GPS collector error: {error}", flush=True)

        elapsed = time.time() - started
        _stop_event.wait(max(1, INTERVAL_SECONDS - elapsed))

    print("Prediction collector thread stopped", flush=True)


def _run_forecast_training():
    print("Forecast model trainer thread started", flush=True)
    while not _training_stop_event.is_set():
        try:
            from services.forecast_training_service import train_forecast_model, forecast_model_status
            status = forecast_model_status()
            age = time.time() - float(status.get("trained_at") or 0)
            if not status.get("active") or age >= int(os.getenv("FORECAST_RETRAIN_INTERVAL_SECONDS", "21600")):
                result = train_forecast_model()
                print(f"Forecast training attempt: {result.get('status')}", flush=True)
        except Exception as error:
            print(f"Forecast training check failed: {type(error).__name__}", flush=True)
        _training_stop_event.wait(FORECAST_TRAIN_CHECK_SECONDS)


def start_collector():
    global _thread, _training_thread

    _stop_event.clear()
    _training_stop_event.clear()

    if not (_thread and _thread.is_alive()):
        _thread = threading.Thread(
            target=_run,
            name="live-gps-collector",
            daemon=True,
        )
        _thread.start()

    if not (_training_thread and _training_thread.is_alive()):
        _training_thread = threading.Thread(
            target=_run_forecast_training,
            name="forecast-model-trainer",
            daemon=True,
        )
        _training_thread.start()


def stop_collector():
    _stop_event.set()
    _training_stop_event.set()


def collector_running():
    return bool(_thread and _thread.is_alive())
