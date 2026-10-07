import unittest

from services.validation_service import validate_gps_batch


BASE = {
    "depot_name": "NOIDA ELECTRIC",
    "bus_id": "TEST001",
    "latitude": 28.514812,
    "longitude": 77.410070,
    "speed": 30,
    "timestamp": "2026-10-07T10:00:00Z",
    "vehicle_status": "live",
}


def point(**changes):
    value = dict(BASE)
    value.update(changes)
    return value


class ValidationServiceTests(unittest.TestCase):
    def test_valid_point_is_accepted(self):
        result = validate_gps_batch([point()])
        self.assertEqual(result["stats"]["accepted"], 1)
        self.assertEqual(result["stats"]["rejected"], 0)

    def test_duplicate_is_rejected(self):
        result = validate_gps_batch([point(), point()])
        self.assertEqual(result["stats"]["accepted"], 1)
        self.assertEqual(result["stats"]["reject_reasons"]["duplicate_point"], 1)

    def test_out_of_order_is_rejected(self):
        result = validate_gps_batch([
            point(),
            point(latitude=28.515000, timestamp="2026-10-07T09:59:00Z"),
        ])
        self.assertEqual(result["stats"]["reject_reasons"]["out_of_order"], 1)

    def test_bad_coordinates_are_rejected(self):
        result = validate_gps_batch([
            point(latitude=61.716667, longitude=77.409700)
        ])
        self.assertEqual(result["stats"]["reject_reasons"]["outside_noida_bounds"], 1)

    def test_impossible_speed_is_rejected(self):
        result = validate_gps_batch([point(speed=91)])
        self.assertEqual(result["stats"]["reject_reasons"]["impossible_speed"], 1)

    def test_impossible_jump_is_rejected(self):
        result = validate_gps_batch([
            point(),
            point(
                latitude=28.514900,
                longitude=77.410100,
                timestamp="2026-10-07T10:00:04Z",
            ),
        ])
        self.assertEqual(result["stats"]["reject_reasons"]["impossible_jump"], 1)

    def test_previous_point_rejects_out_of_order_across_cycles(self):
        previous = {
            "latitude": BASE["latitude"],
            "longitude": BASE["longitude"],
            "event_time": 1791367200.0,
            "timestamp": BASE["timestamp"],
        }
        result = validate_gps_batch(
            [point(timestamp="2026-10-07T09:59:59Z")],
            previous_points={"TEST001": previous},
        )
        self.assertEqual(result["stats"]["reject_reasons"]["out_of_order"], 1)

    def test_previous_point_is_used_for_jump_validation(self):
        previous = {
            "latitude": BASE["latitude"],
            "longitude": BASE["longitude"],
            "event_time": 1791367200.0,
            "timestamp": BASE["timestamp"],
        }
        result = validate_gps_batch(
            [point(
                latitude=28.514900,
                longitude=77.410100,
                timestamp="2026-10-07T10:00:04Z",
            )],
            previous_points={"TEST001": previous},
        )
        self.assertEqual(result["stats"]["accepted"], 1)


if __name__ == "__main__":
    unittest.main()
