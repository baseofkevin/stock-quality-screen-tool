# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import stock_report  # noqa: E402
from screen.fetch import load_bundle, normalize_code  # noqa: E402
from screen.compute import _margin_trend, _valuation_chart, build_report_data  # noqa: E402
from screen.render import _margin_chart  # noqa: E402
from screen.score import compute_scores  # noqa: E402
from providers.eastmoney import to_secucode  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "mini_bundle.json"


class CodeTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_code("600519"), "sh600519")
        self.assertEqual(normalize_code("301101"), "sz301101")
        self.assertEqual(normalize_code("920001"), "bj920001")
        self.assertEqual(normalize_code("600519.SH"), "sh600519")

    def test_secucode(self):
        self.assertEqual(to_secucode("600519"), "600519.SH")
        self.assertEqual(to_secucode("920001"), "920001.BJ")
        self.assertEqual(to_secucode("301101"), "301101.SZ")


class CliDefaultTest(unittest.TestCase):
    def test_default_out_dir_is_project_html_report(self):
        args = stock_report.build_parser().parse_args(["--stock-code", "600519"])
        self.assertEqual(Path(args.out_dir), ROOT / "html-report")


class OfflineReportTest(unittest.TestCase):
    def test_cli_outputs_only_html(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "stock_report.py"),
                 "--stock-code", "600519", "--bundle", str(FIXTURE), "--out-dir", str(out)],
                cwd=str(ROOT), capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            files = list(out.iterdir())
            self.assertEqual(len(files), 1, [p.name for p in files])
            self.assertEqual(files[0].suffix, ".html")
            self.assertFalse((out / "report.json").exists())
            html = files[0].read_text(encoding="utf-8")
            for heading in ["一、生意本身", "二、经营质量与风险", "三、企业估值与机构预期",
                            "四、综合评分", "五、后续跟踪"]:
                self.assertIn(heading, html)
            self.assertIn("机构未来盈利预期", html)
            self.assertIn("产品/业务结构", html)
            self.assertIn("茅台酒", html)
            self.assertIn("机构目标价", html)
            self.assertIn("近 15 个季度利润率趋势", html)
            self.assertIn("近 15 个季度估值走势（周频）", html)
            self.assertEqual(html.count("<svg"), 4)
            self.assertIn('class="latest"', html)
            self.assertNotIn("财务数据全景", html)
            self.assertNotIn("25 条", html)
            self.assertNotIn('type="application/json"', html)

    def test_compute_contract(self):
        raw = load_bundle(FIXTURE)
        data = compute_scores(build_report_data(raw["calls"], raw["code"]))
        self.assertIsNotNone(data["quality"]["score"])
        self.assertIsNotNone(data["valuation_score"]["score"])
        self.assertEqual(len(data["risks"]["checks"]), 10)
        self.assertIn(data["decision"]["key"],
                      {"buy", "watch_price", "expensive", "watch", "avoid", "unknown"})
        self.assertGreaterEqual(data["confidence"], 0)
        self.assertLessEqual(data["confidence"], 100)
        self.assertGreaterEqual(len(data["forecast"]["forecasts"]), 1)
        self.assertTrue(data["tracking"])
        self.assertEqual(data["financials"]["margin_trend"]["count"], 6)
        self.assertGreater(data["valuation"]["chart"]["count"], 0)
        self.assertIsNotNone(data["valuation"]["chart"]["latest"]["pe"])

    def test_margin_trend_keeps_last_15_quarters(self):
        dates = [f"{year}-{month}-{day}" for year in range(2022, 2027)
                 for month, day in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31"))]
        merged = {
            d: {"income": {
                "OperatingRevenue_Q": "100",
                "OperatingCost_Q": "40",
                "NPParentCompanyOwners_Q": "20",
            }} for d in dates
        }
        trend = _margin_trend(merged)
        self.assertEqual(trend["count"], 15)
        self.assertEqual(trend["start"], dates[-15])
        self.assertEqual(trend["end"], dates[-1])
        self.assertAlmostEqual(trend["points"][-1]["gross"], 60.0)
        self.assertAlmostEqual(trend["points"][-1]["net"], 20.0)

    def test_margin_chart_labels_all_quarters(self):
        labels = [f"{year}Q{q}" for year in (23, 24, 25) for q in range(1, 5)]
        labels += ["26Q1", "26Q2", "26Q3"]
        points = [
            {"date": f"2023-{(i % 4) * 3 + 3:02d}-30", "label": label,
             "gross": 60.0 + i, "net": 20.0 + i}
            for i, label in enumerate(labels)
        ]
        chart = _margin_chart({"points": points, "count": 15,
                               "start": points[0]["date"], "end": points[-1]["date"]})
        self.assertEqual(chart.count('text-anchor="middle"'), 15)
        self.assertIn("共 15 个季度", chart)
        self.assertIn("最新 26Q3", chart)

    def test_valuation_chart_breaks_negative_pe(self):
        rows = [
            {"TRADE_DATE": "2024-01-05", "PE_TTM": 20.0, "PB_MRQ": 5.0, "PS_TTM": 4.0},
            {"TRADE_DATE": "2024-01-12", "PE_TTM": -8.0, "PB_MRQ": 5.1, "PS_TTM": 4.1},
            {"TRADE_DATE": "2024-01-19", "PE_TTM": 22.0, "PB_MRQ": 5.2, "PS_TTM": 4.2},
        ]
        chart = _valuation_chart(rows, "")
        self.assertEqual(chart["points"][1]["pe"], None)
        self.assertTrue(chart["points"][1]["pe_negative"])
        self.assertEqual(chart["negative_ranges"], [["2024-01-12", "2024-01-12"]])
        self.assertEqual(chart["latest"]["pe"]["value"], 22.0)


if __name__ == "__main__":
    unittest.main()
