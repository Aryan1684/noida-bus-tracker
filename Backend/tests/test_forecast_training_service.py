import unittest

from services.forecast_training_service import build_training_samples, _clean_history


def make_history(count=40, start=1800000000.0, interval=60):
    return [
        {
            "time": start + index * interval,
            "latitude": 28.50 + index * 0.0001,
            "longitude": 77.40 + index * 0.00008,
            "speed": 20 + (index % 3),
        }
        for index in range(count)
    ]


class ForecastTrainingTests(unittest.TestCase):
    def test_training_samples_have_feature_shape_and_three_minute_targets(self):
        samples = build_training_samples({"TEST-BUS": make_history()})
        self.assertGreater(len(samples), 10)
        self.assertEqual(len(samples[0]["features"]), 23)
        self.assertEqual(len(samples[0]["target"]), 2)

    def test_duplicate_timestamps_are_deduplicated(self):
        history = make_history(8)
        duplicate = dict(history[3])
        duplicate["latitude"] += 0.00001
        history.append(duplicate)
        cleaned = _clean_history(history)
        timestamps = [point["time"] for point in cleaned]
        self.assertEqual(len(timestamps), len(set(timestamps)))

    def test_samples_are_chronologically_sorted(self):
        histories = {
            "BUS-A": make_history(24),
            "BUS-B": make_history(24, start=1800010000.0),
        }
        samples = build_training_samples(histories)
        times = [sample["time"] for sample in samples]
        self.assertEqual(times, sorted(times))


if __name__ == "__main__":
    unittest.main()
