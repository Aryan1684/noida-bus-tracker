import unittest

from services.position_trust_service import match_position


class PositionTrustTests(unittest.TestCase):
    def test_known_route_position_matches(self):
        result = match_position("UP80KT3703", 28.5641, 77.3358, 0)
        self.assertIn(result["route_match_confidence"], {"high", "medium"})

    def test_far_position_is_off_route(self):
        result = match_position("UP80KT3703", 28.17556, 77.60500, 180)
        self.assertEqual(result["route_match_status"], "off_route")

    def test_result_contains_progress(self):
        result = match_position("UP80KT3703", 28.5641, 77.3358)
        self.assertIsNotNone(result["route_progress"])


if __name__ == "__main__":
    unittest.main()
