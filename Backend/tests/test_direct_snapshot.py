import unittest
from datetime import datetime, timezone

from services import gps_service
from services.gps_service import get_direct_live_buses, get_direct_snapshot_status


class DirectSnapshotTests(unittest.TestCase):
    def test_malformed_records_do_not_abort_feed(self):
        good_bus = {
            "depot_name": "NOIDA ELECTRIC",
            "bus_id": "TEST-SNAPSHOT-001",
            "latitude": 28.514812,
            "longitude": 77.410070,
            "speed": 0,
            "timestamp": "2026-10-11T10:00:00Z",
            "vehicle_status": "stationary",
        }
        buses = get_direct_live_buses(
            [None, "x", 17, good_bus],
            include_persisted_history=False,
        )
        self.assertEqual(len(buses), 1)
        self.assertEqual(buses[0]["bus_id"], "TEST-SNAPSHOT-001")

    def test_repeated_source_fix_is_not_added_twice_to_history(self):
        timestamp = datetime.now(timezone.utc).isoformat()
        bus = {
            "depot_name": "NOIDA ELECTRIC",
            "bus_id": "TEST-HISTORY-001",
            "latitude": 28.514812,
            "longitude": 77.410070,
            "speed": 0,
            "timestamp": timestamp,
            "vehicle_status": "stationary",
        }
        with gps_service._cache_lock:
            gps_service._direct_history.pop("TEST-HISTORY-001", None)

        get_direct_live_buses([bus])
        get_direct_live_buses([bus])

        history = gps_service.get_direct_bus_histories(["TEST-HISTORY-001"])
        self.assertEqual(len(history["TEST-HISTORY-001"]), 1)

    def test_empty_feed_is_recorded_as_empty_not_outage(self):
        buses = get_direct_live_buses([], include_persisted_history=False)
        status = get_direct_snapshot_status()
        self.assertEqual(buses, [])
        self.assertEqual(status["state"], "empty")
        self.assertEqual(status["bus_count"], 0)


if __name__ == "__main__":
    unittest.main()
