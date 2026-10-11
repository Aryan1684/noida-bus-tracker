import os
import threading
import time

from services.gps_service import refresh_direct_snapshot

INTERVAL_SECONDS = max(30, int(os.getenv("PREDICTION_COLLECT_INTERVAL_SECONDS", "60")))

_stop_event = threading.Event()
_thread = None


def _run():
    print("Prediction collector thread started", flush=True)

    while not _stop_event.is_set():
        started = time.time()

        try:
            print("GPS snapshot collector fetching live feed", flush=True)
            buses = refresh_direct_snapshot()
            print(f"GPS snapshot collector refreshed {len(buses)} buses", flush=True)
        except Exception as error:
            print(f"Prediction collector error: {error}", flush=True)

        elapsed = time.time() - started
        _stop_event.wait(max(1, INTERVAL_SECONDS - elapsed))

    print("Prediction collector thread stopped", flush=True)


def start_collector():
    global _thread

    if _thread and _thread.is_alive():
        return

    _stop_event.clear()
    _thread = threading.Thread(
        target=_run,
        name="prediction-collector",
        daemon=True,
    )
    _thread.start()


def stop_collector():
    _stop_event.set()


def collector_running():
    return bool(_thread and _thread.is_alive())
