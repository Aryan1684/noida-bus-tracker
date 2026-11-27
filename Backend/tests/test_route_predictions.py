import unittest

from services.direction_service import (
    LANDMARKS,
    ROUTES,
    calculate_bearing,
    get_route_prediction,
    update_bus_history,
    moving_packet_heading,
)


def midpoint(first, second):
    a = LANDMARKS[first]
    b = LANDMARKS[second]
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def predict_on_segment(bus_id, route_id, segment_index):
    route = next(route for route in ROUTES if route["id"] == route_id)
    first = route["points"][segment_index]
    second = route["points"][segment_index + 1]
    latitude, longitude = midpoint(first, second)
    a = LANDMARKS[first]
    b = LANDMARKS[second]
    bearing = calculate_bearing(a[0], a[1], b[0], b[1])
    return get_route_prediction(bus_id, latitude, longitude, bearing)


class RoutePredictionTests(unittest.TestCase):
    def test_single_packet_selects_the_forward_or_reverse_segment(self):
        a, b = "Advant", "Sector 163"
        lat, lon = midpoint(a, b)
        bus = dict(bus_id="UP80KT3703", latitude=lat, longitude=lon, speed=28,
                   vehicle_status="live", gps_age_seconds=4)
        point = dict(time=100, latitude=lat, longitude=lon, speed=28)
        for start, end in [(a, b), (b, a)]:
            bus["gps_heading"] = calculate_bearing(*LANDMARKS[start], *LANDMARKS[end])
            result = update_bus_history(bus, [point])
            self.assertEqual(result["likely_next_stop"], end)
            self.assertEqual(result["heading_source"], "gps_packet")

    def test_packet_heading_handles_north_staleness_and_history_fallback(self):
        bus = dict(bus_id="TEST", speed=20, latitude=28.5, longitude=77.401,
                   gps_heading="0", gps_age_seconds=5)
        for patch in [{}, {"gps_heading": 360}]:
            self.assertEqual(moving_packet_heading(dict(bus, **patch)), 0)
        for patch in [{"gps_heading": 999}, {"gps_heading": None}, {"gps_heading": "nan"},
                      {"speed": 0}, {"vehicle_status": "no_signal"}, {"snapshot_age_seconds": 116}]:
            self.assertIsNone(moving_packet_heading(dict(bus, **patch)))
        history = [dict(latitude=28.5, longitude=lon, time=t, speed=20)
                   for lon, t in [(77.40, 100), (77.401, 120)]]
        self.assertEqual(update_bus_history(bus, history)["heading"], 0)
        fallback = update_bus_history(dict(bus, gps_heading=None), history)
        self.assertAlmostEqual(fallback["heading"], 90, delta=1)
        self.assertEqual(fallback["heading_source"], "position_history")

    def test_advant_is_at_sector_142_not_the_sector_62_area(self):
        latitude, longitude = LANDMARKS["Advant"]
        self.assertGreater(latitude, 28.49)
        self.assertLess(latitude, 28.51)
        self.assertGreater(longitude, 77.40)
        self.assertLess(longitude, 77.42)

    def test_botanical_to_pari_via_advant_predicts_advant_corridor(self):
        result = predict_on_segment("UP80KT3703", "N-R02-ADVANT-OUT", 6)
        self.assertIsNotNone(result)
        self.assertEqual(result["route_path_id"], "N-R02-ADVANT-OUT")
        self.assertEqual(result["likely_destination"], "Pari Chowk")

    def test_airport_route_predicts_airport_after_branch(self):
        result = predict_on_segment("UP14ST3546", "GR01-AIRPORT-OUT", 4)
        self.assertIsNotNone(result)
        self.assertEqual(result["route_path_id"], "GR01-AIRPORT-OUT")
        self.assertEqual(result["likely_destination"], "Noida International Airport")

    def test_shared_chaar_murti_corridor_does_not_guess_terminal(self):
        result = predict_on_segment("UP14ST3546", "GR01-AIRPORT-OUT", 1)
        self.assertIsNotNone(result)
        self.assertEqual(result["likely_next_stop"], "Surajpur")
        self.assertIsNone(result["likely_destination"])
        self.assertEqual(result["destination_confidence"], "Unknown")


if __name__ == "__main__":
    unittest.main()
