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
from screen.compute import build_report_data  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
