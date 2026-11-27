import unittest
from datetime import datetime, timedelta, timezone

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

    def test_only_local_electric_depots_enter_snapshot(self):
        base = {"latitude": 28.4652, "longitude": 77.508, "speed": 0}
        rows = [
            ("N1", "NOIDA ELECTRIC", None),
            ("G1", "Greater Noida Electric", "Electric"),
            ("D1", "GREATER NOIDA ELECTRIC", "Diesel"),
            ("D2", "NOIDA", "Diesel"),
            ("A1", "AGRA ELECTRIC", "Electric"),
        ]
        buses = get_direct_live_buses([
            dict(base, bus_id=bus_id, depot_name=depot, fuel_type=fuel)
            for bus_id, depot, fuel in rows
        ])
        self.assertEqual({bus["bus_id"] for bus in buses}, {"N1", "G1"})

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

    def test_heading_uses_recent_motion_and_clears_when_stopped(self):
        now = datetime.now(timezone.utc)
        bus = dict(bus_id="EAST-01", latitude=28.51, longitude=77.41,
                   speed=20, depot_name="NOIDA ELECTRIC", vehicle_status="moving")
        with gps_service._cache_lock:
            gps_service._direct_history.pop(bus["bus_id"], None)
        def sample(seconds, longitude, speed):
            return get_direct_live_buses([dict(bus, timestamp=(now + timedelta(seconds=seconds)).isoformat(),
                                               longitude=longitude, speed=speed)])[0]
        self.assertIsNone(sample(-40, 77.41, 20)["heading"])
        self.assertAlmostEqual(sample(-20, 77.411, 20)["heading"], 90, delta=1)
        self.assertIsNone(sample(0, 77.411, 0)["heading"])

    def test_first_moving_fix_preserves_valid_device_heading(self):
        base = dict(depot_name="NOIDA ELECTRIC", latitude=28.51, longitude=77.41,
                    speed=18, timestamp=datetime.now(timezone.utc).isoformat())
        for index, (device, expected) in enumerate([(0, 0), ("273.5", 273.5), (360, 0),
                                                    (-1, None), ("nan", None), ("", None)]):
            row = dict(base, bus_id=f"DEVICE-{index}", heading=device)
            bus = get_direct_live_buses([row])[0]
            self.assertEqual(bus["heading"], expected)
            self.assertEqual(bus["gps_heading"], expected)
        stopped = get_direct_live_buses([dict(base, bus_id="DEVICE-STOP", speed=0, heading=94)])[0]
        self.assertIsNone(stopped["heading"])

    def test_empty_feed_is_recorded_as_empty_not_outage(self):
        buses = get_direct_live_buses([], include_persisted_history=False)
        status = get_direct_snapshot_status()
        self.assertEqual(buses, [])
        self.assertEqual(status["state"], "empty")
        self.assertEqual(status["bus_count"], 0)


if __name__ == "__main__":
    unittest.main()
