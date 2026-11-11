# -*- coding: utf-8 -*-
"""代码号段规则：三处入口必须给出一致答案（screen/codes.py）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screen import codes  # noqa: E402
from screen.batch import eastmoney_url  # noqa: E402
from screen.fetch import normalize_code  # noqa: E402
from providers.eastmoney import to_secucode  # noqa: E402


class SplitTest(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(codes.split("600519"), (None, "600519"))
        self.assertEqual(codes.split("sh600519"), ("sh", "600519"))
        self.assertEqual(codes.split("600519.SH"), ("sh", "600519"))
        self.assertEqual(codes.split("600519.sh"), ("sh", "600519"))
        self.assertEqual(codes.split(" 600519 "), (None, "600519"))

    def test_unrecognized(self):
        for raw in ("", None, "60051", "6005190", "abcdef", "600519.XX", "sh600519.SH"):
            self.assertIsNone(codes.split(raw), msg=raw)

    def test_bare_dot_removal(self):
        # 点号后不是市场后缀（如港股 00700.HK）→ 去掉点号后既非 6 位也非 8 位，判为无效
        self.assertIsNone(codes.split("00700.HK"))


class MarketOfTest(unittest.TestCase):
    def test_segments(self):
        cases = {
            "600519": "sh", "688111": "sh", "900901": "sh",     # 主板 / 科创板 / B 股
            "000001": "sz", "002594": "sz", "300059": "sz",     # 主板 / 中小板 / 创业板
            "430047": "bj", "830799": "bj", "920001": "bj",     # 北交所三套号段
        }
        for digits, market in cases.items():
            self.assertEqual(codes.market_of(digits), market, msg=digits)


class EntryPointsAgreeTest(unittest.TestCase):
    """三个入口对同一只股票必须给出互相解释得通的答案。"""

    def test_same_market_everywhere(self):
        for raw in ("600519", "sh600519", "600519.SH", "000001", "300059",
                    "688111", "920001", "430047", "830799", "900901"):
            market = codes.normalize(raw)[:2]
            self.assertTrue(to_secucode(raw).endswith("." + market.upper()), msg=raw)
            self.assertEqual(normalize_code(raw), codes.normalize(raw), msg=raw)
            url = eastmoney_url(raw)
            if market == "bj":
                self.assertIn(f"/bj/{codes.six(raw)}.html", url, msg=raw)
            else:
                self.assertIn(f"/{market}{codes.six(raw)}.html", url, msg=raw)

    def test_secucode_accepts_suffixed_form(self):
        # 0.9.7 之前 to_secucode("600519.SH") 会 replace('.','') 后变成 8 位而抛错
        self.assertEqual(to_secucode("600519.SH"), "600519.SH")
        self.assertEqual(to_secucode("600519.sh"), "600519.SH")
        self.assertEqual(to_secucode("sz300059"), "300059.SZ")

    def test_invalid_inputs(self):
        for raw in ("", None, "bad", "12345", "1234567", "60051X"):
            with self.assertRaises(ValueError, msg=raw):
                codes.normalize(raw)
            with self.assertRaises(ValueError, msg=raw):
                codes.secucode(raw)
            self.assertEqual(codes.eastmoney_url(raw), "", msg=raw)


if __name__ == "__main__":
    unittest.main()
