# -*- coding: utf-8 -*-
"""数值清洗与统计工具、打分原语（screen/util.py）。"""
import math
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


import support  # noqa: F401  (把项目根目录加入 sys.path)
from screen.util import (cagr, clamp, div, inverse, linear, mean, median, num,
                         pct, ratio, stdev, text, year_of, yi)


class NumTest(unittest.TestCase):
    def test_passes_through_finite_numbers(self):
        self.assertEqual(num(3), 3.0)
        self.assertEqual(num(3.5), 3.5)
        self.assertEqual(num("12.5"), 12.5)

    def test_cleans_thousand_separator_and_percent(self):
        self.assertEqual(num("1,234.5"), 1234.5)
        self.assertEqual(num("12%"), 12.0)
        self.assertEqual(num(" -8.2% "), -8.2)

    def test_placeholders_become_none(self):
        for value in (None, "", "  ", "--", "-", "None", "null", "nan", "abc"):
            self.assertIsNone(num(value), value)

    def test_rejects_bool_and_non_finite(self):
        self.assertIsNone(num(True))
        self.assertIsNone(num(False))
        self.assertIsNone(num("inf"))
        self.assertIsNone(num(float("nan")))


class DivTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(div(1, 2), 0.5)

    def test_none_or_zero_returns_none(self):
        self.assertIsNone(div(None, 2))
        self.assertIsNone(div(2, None))
        self.assertIsNone(div(2, 0))
        self.assertIsNone(div(0, 0))


class MedianMeanStdevTest(unittest.TestCase):
    def test_median_ignores_none(self):
        self.assertIsNone(median([]))
        self.assertIsNone(median([None, None]))
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([4, 1, 3, 2]), 2.5)
        self.assertEqual(median([1, None, 3]), 2)

    def test_mean(self):
        self.assertIsNone(mean([]))
        self.assertAlmostEqual(mean([1, 2, None]), 1.5)

    def test_stdev_is_sample_stdev(self):
        self.assertIsNone(stdev([1]))
        self.assertEqual(stdev([2, 2, 2]), 0.0)
        self.assertAlmostEqual(stdev([1, 3]), math.sqrt(2), places=6)


class CagrTest(unittest.TestCase):
    def test_compound_growth_in_percent(self):
        self.assertAlmostEqual(cagr(100, 121, 2), 10.0, places=6)
        self.assertAlmostEqual(cagr(100, 100, 3), 0.0, places=6)

    def test_requires_positive_base(self):
        self.assertIsNone(cagr(0, 100, 2))
        self.assertIsNone(cagr(-100, 100, 2))
        self.assertIsNone(cagr(100, -1, 2))
        self.assertIsNone(cagr(100, 100, 0))
        self.assertIsNone(cagr(None, 100, 2))


class ClampTest(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(clamp(-5), 0.0)
        self.assertEqual(clamp(150), 100.0)
        self.assertEqual(clamp(42), 42)


class LinearTest(unittest.TestCase):
    def test_maps_and_truncates(self):
        self.assertEqual(linear(5, 0, 10, 20), 10.0)
        self.assertEqual(linear(-5, 0, 10, 20), 0.0)
        self.assertEqual(linear(50, 0, 10, 20), 20.0)
        self.assertAlmostEqual(linear(7.5, 0, 15, 20), 10.0)

    def test_none_and_degenerate_range(self):
        self.assertIsNone(linear(None, 0, 10, 20))
        self.assertIsNone(linear(5, 5, 5, 20))


class InverseTest(unittest.TestCase):
    def test_lower_is_better(self):
        self.assertEqual(inverse(0, 0, 10, 20), 20.0)
        self.assertEqual(inverse(10, 0, 10, 20), 0.0)
        self.assertEqual(inverse(5, 0, 10, 20), 10.0)
        self.assertEqual(inverse(-1, 0, 10, 20), 20.0)
        self.assertEqual(inverse(99, 0, 10, 20), 0.0)

    def test_none(self):
        self.assertIsNone(inverse(None, 0, 10, 20))


class YearOfTest(unittest.TestCase):
    def test_extracts_four_digit_year(self):
        self.assertEqual(year_of("2025-12-31"), 2025)
        self.assertEqual(year_of("2026-09-30 00:00:00"), 2026)
        self.assertIsNone(year_of(""))
        self.assertIsNone(year_of(None))
        self.assertIsNone(year_of("abc"))


class FormatTest(unittest.TestCase):
    def test_pct(self):
        self.assertEqual(pct(None), "—")
        self.assertEqual(pct(12.34), "12.3%")
        self.assertEqual(pct(12.34, 2), "12.34%")

    def test_yi(self):
        self.assertEqual(yi(None), "—")
        self.assertEqual(yi(1e8), "1.00 亿")
        self.assertEqual(yi(2.5e8, 1), "2.5 亿")

    def test_ratio_and_text(self):
        self.assertEqual(ratio(None), "—")
        self.assertEqual(ratio(1.234), "1.23")
        self.assertEqual(text("  "), "暂无披露")
        self.assertEqual(text("白酒", "无"), "白酒")


class ScorePrimitiveContractTest(unittest.TestCase):
    """Q/V 全部子项都靠这两个原语，把契约固定下来。"""

    def test_linear_endpoints(self):
        cases = [(0, 0), (15, 20), (-1, 0), (30, 20)]
        for x, expected in cases:
            self.assertEqual(linear(x, 0, 15, 20), expected)

    def test_inverse_endpoints(self):
        cases = [(0, 8), (3, 0), (-2, 8), (9, 0)]
        for x, expected in cases:
            self.assertEqual(inverse(x, 0, 3, 8), expected)


if __name__ == "__main__":
    unittest.main()
