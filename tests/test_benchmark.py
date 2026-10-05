from __future__ import annotations

import unittest

from edge_ai_director.benchmark import percentile, summarize


class PercentileTests(unittest.TestCase):
    def test_percentile_interpolates_sorted_samples(self) -> None:
        values = [40.0, 10.0, 30.0, 20.0]

        self.assertEqual(percentile(values, 0.0), 10.0)
        self.assertEqual(percentile(values, 0.5), 25.0)
        self.assertEqual(percentile(values, 1.0), 40.0)

    def test_percentile_rejects_empty_or_invalid_input(self) -> None:
        with self.assertRaises(ValueError):
            percentile([], 0.5)
        with self.assertRaises(ValueError):
            percentile([1.0], 1.1)

    def test_summary_keeps_tail_latency_visible(self) -> None:
        summary = summarize([10.0, 10.0, 10.0, 50.0])

        self.assertEqual(summary["count"], 4)
        self.assertEqual(summary["mean"], 20.0)
        self.assertGreater(summary["p95"], summary["p50"])


if __name__ == "__main__":
    unittest.main()
