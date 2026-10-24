import unittest

from services.direction_service import (
    LANDMARKS,
    ROUTES,
    calculate_bearing,
    get_route_prediction,
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
