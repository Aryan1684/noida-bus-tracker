import unittest

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

    def test_empty_feed_is_recorded_as_empty_not_outage(self):
        buses = get_direct_live_buses([], include_persisted_history=False)
        status = get_direct_snapshot_status()
        self.assertEqual(buses, [])
        self.assertEqual(status["state"], "empty")
        self.assertEqual(status["bus_count"], 0)


if __name__ == "__main__":
    unittest.main()
