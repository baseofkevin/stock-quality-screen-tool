# -*- coding: utf-8 -*-
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import stock_report  # noqa: E402
import config  # noqa: E402
from screen.batch import (EASTMONEY_COLUMN, LINK_COLUMN, SCORE_COLUMN,
                          eastmoney_link_cell, eastmoney_url,
                          ensure_result_columns, link_target, read_csv_table,
                          report_link_cell, write_csv_table)  # noqa: E402
from screen.fetch import DataError, load_bundle, normalize_code  # noqa: E402
from screen.index_html import write_index_html  # noqa: E402
from screen.compute import (_cash_valuation, _margin_trend, _valuation_chart,
                            build_report_data)  # noqa: E402
from screen.render import _margin_chart, _section_valuation, render_html  # noqa: E402
from screen.score import _data_quality, _decision, _valuation_score, compute_scores  # noqa: E402
from screen.summary import SummaryError, extract_score_summary  # noqa: E402
from screen.xlsx import write_report_xlsx  # noqa: E402
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
    @staticmethod
    def _fixture_data():
        raw = load_bundle(FIXTURE)
        return compute_scores(build_report_data(raw["calls"], raw["code"]))

    @classmethod
    def _fixture_risk_known(cls):
        return cls._fixture_data()["data_quality"]["risk_known"]

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
            self.assertRegex(files[0].name, r"^贵州茅台-企业质量初筛-\d{8}-\d{6}\.html$")
            self.assertFalse((out / "report.json").exists())
            html = files[0].read_text(encoding="utf-8")
            self.assertIn("<title>贵州茅台（sh600519）企业质量初筛</title>", html)
            self.assertNotIn("· 生成", html)
            for heading in ["一、生意本身", "二、经营质量与风险", "三、企业估值与机构预期",
                            "四、综合评分", "五、后续跟踪"]:
                self.assertIn(heading, html)
            self.assertIn("PE/PB/PS 历史分位及走势图", html)
            self.assertIn("机构对企业未来盈利的预期", html)
            self.assertIn("产品/业务结构", html)
            self.assertIn("茅台酒", html)
            self.assertIn("机构目标价", html)
            self.assertIn(f"近 {config.TREND_YEARS} 年季度毛利率/净利率趋势", html)
            self.assertNotIn("近 15 个季度利润率趋势", html)
            self.assertIn(f"下图为近 {config.VALUATION_YEARS} 年周频走势", html)
            self.assertNotIn("近 15 个季度估值走势（周频）", html)
            self.assertNotIn("近 15 个季度周频走势", html)
            self.assertNotIn("本报告的估值", html)
            self.assertNotIn("对企业进行 DCF 估值", html)
            self.assertNotIn("DCF", html)
            self.assertNotIn("FCF 收益率", html)
            self.assertIn("用现金扣除与底线估值方式对企业进行估值", html)
            self.assertIn("货币资金/市值", html)
            self.assertIn("最近年报净利润总额", html)
            self.assertIn("估值分构成（机构口径）", html)
            self.assertIn("机构目标价空间", html)
            self.assertIn("预期未来净利增速", html)
            self.assertIn("数据完整度", html)
            self.assertIn("第二节不参与打分", html)
            self.assertIn("一致性闸门", html)
            known = self._fixture_risk_known()
            self.assertIn(f"风险检查 {known}/{config.RISK_CHECK_COUNT}", html)
            self.assertNotIn("置信度", html)
            self.assertEqual(html.count("<svg"), 4)
            self.assertIn('class="latest"', html)
            self.assertNotIn("财务数据全景", html)
            self.assertNotIn("25 条", html)
            self.assertNotIn('type="application/json"', html)

    def test_compute_contract(self):
        data = self._fixture_data()
        self.assertIsNotNone(data["quality"]["score"])
        self.assertIsNotNone(data["valuation_score"]["score"])
        self.assertEqual(len(data["risks"]["checks"]), config.RISK_CHECK_COUNT)
        self.assertIn(data["risks"]["gate_level"], (None, "watch", "avoid"))
        self.assertIn(data["decision"]["key"],
                      {"buy", "buy_ok", "buy_small", "buy_trial",
                       "watch_price", "expensive", "watch", "avoid", "unknown"})
        self.assertNotIn("confidence", data)
        self.assertEqual(data["data_quality"]["risk_total"], config.RISK_CHECK_COUNT)
        self.assertEqual(data["data_quality"]["risk_known"] + data["data_quality"]["risk_unknown"],
                         config.RISK_CHECK_COUNT)
        self.assertEqual(data["data_quality"]["institution_coverage"], 4)
        self.assertEqual(data["data_quality"]["buy_blockers"], [])
        self.assertGreaterEqual(len(data["forecast"]["forecasts"]), 1)
        self.assertTrue(data["tracking"])
        self.assertEqual(data["financials"]["margin_trend"]["count"], 6)
        self.assertGreater(data["valuation"]["chart"]["count"], 0)
        self.assertIsNotNone(data["valuation"]["chart"]["latest"]["pe"])
        self.assertEqual([a["years"] for a in data["cash_valuation"]["anchors"]],
                         [3, 5, 10, 15, 20])
        self.assertEqual([p["key"] for p in data["valuation_score"]["parts"]],
                         ["target_upside", "forecast_pe", "profit_growth"])

    def test_expectation_flags_are_inside_forecast_section(self):
        raw = load_bundle(FIXTURE)
        data = build_report_data(raw["calls"], raw["code"])
        data["flags"] = ["测试预期差提示"]
        html = _section_valuation(data)
        i_forecast = html.index("机构对企业未来盈利的预期")
        i_flag = html.index("测试预期差提示")
        i_cash = html.index("用现金扣除与底线估值方式对企业进行估值")
        self.assertLess(i_forecast, i_flag)
        self.assertLess(i_flag, i_cash)

    def test_margin_trend_keeps_last_five_years(self):
        dates = [f"{year}-{month}-{day}" for year in range(2019, 2027)
                 for month, day in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31"))]
        merged = {
            d: {"income": {
                "OperatingRevenue_Q": "100",
                "OperatingCost_Q": "40",
                "NPParentCompanyOwners_Q": "20",
            }} for d in dates
        }
        trend = _margin_trend(merged)
        self.assertEqual(trend["count"], 20)          # 5 年 × 4 个季度
        self.assertEqual(trend["start"], dates[-20])
        self.assertEqual(trend["end"], dates[-1])
        self.assertAlmostEqual(trend["points"][-1]["gross"], 60.0)
        self.assertAlmostEqual(trend["points"][-1]["net"], 20.0)

    def test_margin_chart_labels_all_quarters_in_five_years(self):
        labels = [f"{year % 100:02d}Q{q}" for year in range(2022, 2027) for q in range(1, 5)]
        points = [
            {"date": f"{2022 + i // 4}-{(i % 4) * 3 + 3:02d}-30", "label": label,
             "gross": 60.0 + i, "net": 20.0 + i}
            for i, label in enumerate(labels)
        ]
        chart = _margin_chart({"points": points, "count": 20,
                               "start": points[0]["date"], "end": points[-1]["date"]})
        self.assertEqual(chart.count('text-anchor="middle"'), 20)   # 20 个季度全部标刻度
        self.assertIn("共 20 个季度", chart)
        self.assertIn("最新 26Q4", chart)
        self.assertIn(f"近 {config.TREND_YEARS} 年季度毛利率/净利率趋势", chart)
        self.assertNotIn("不足", chart)                              # 满 5 年不写"不足"

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


class CashValuationTest(unittest.TestCase):
    """现金扣除与底线估值：只展示，不进入 V 分。"""

    def test_uses_latest_cash_and_total_profit(self):
        annual = [{"date": "2025-12-31", "cash": 2.3e9, "debt": 5e8,
                   "net_profit": 4.8e8, "net_profit_total": 5.1e8}]
        latest = {"date": "2026-09-30", "cash": 2.5e9, "debt": 1e9}
        quote = {"total_shares": 1e8, "price": 5.0}
        cv = _cash_valuation(annual, latest, quote, 5e9)
        self.assertTrue(cv["applicable"])
        self.assertAlmostEqual(cv["cash_yi"], 25.0)       # 用最新期，不是年报 23 亿
        self.assertAlmostEqual(cv["debt_yi"], 10.0)
        self.assertAlmostEqual(cv["cash_ratio_pct"], 50.0)
        self.assertAlmostEqual(cv["ex_cash_cap_yi"], 25.0)
        self.assertAlmostEqual(cv["net_profit_yi"], 5.1)
        self.assertAlmostEqual(cv["ex_cash_pe"], 25.0 / 5.1)
        self.assertAlmostEqual(cv["earnings_yield_pct"], 5.1 / 50.0 * 100.0)
        self.assertEqual([a["years"] for a in cv["anchors"]], [3, 5, 10, 15, 20])
        self.assertAlmostEqual(cv["anchors"][0]["value_yi"], 25.0 + 3 * 5.1)
        self.assertAlmostEqual(cv["anchors"][0]["per_share"], 40.3)
        self.assertAlmostEqual(cv["anchors"][0]["margin_pct"], (40.3 - 50) / 40.3 * 100)

    def test_negative_ex_cash_marks_pe_not_applicable(self):
        annual = [{"date": "2025-12-31", "net_profit_total": 5.1e8}]
        latest = {"date": "2026-09-30", "cash": 6e9}
        cv = _cash_valuation(annual, latest, {"total_shares": 1e8}, 5e9)
        self.assertTrue(cv["negative_ex_cash"])
        self.assertAlmostEqual(cv["ex_cash_cap_yi"], -10.0)
        self.assertIsNone(cv["ex_cash_pe"])
        self.assertEqual(len(cv["anchors"]), 5)            # 现金底仓仍可计算

    def test_missing_or_negative_profit_disables_anchor(self):
        latest = {"date": "2026-09-30", "cash": 2.5e9}
        cv = _cash_valuation([{"date": "2025-12-31"}], latest,
                             {"total_shares": 1e8}, 5e9)
        self.assertEqual(cv["anchors"], [])
        self.assertIn("净利润总额", cv["reason"])
        cv = _cash_valuation([{"date": "2025-12-31", "net_profit_total": -1e8}],
                             latest, {"total_shares": 1e8}, 5e9)
        self.assertEqual(cv["anchors"], [])
        self.assertIn("非正", cv["reason"])

    def test_financial_industry_not_applicable(self):
        cv = _cash_valuation([{"date": "2025-12-31", "net_profit_total": 5e8}],
                             {"date": "2026-09-30", "cash": 1e9},
                             {"total_shares": 1e8}, 5e9, "银行")
        self.assertFalse(cv["applicable"])
        self.assertEqual(cv["reason"], "金融股不适用")


class ValuationScoreTest(unittest.TestCase):
    """V 分机构口径：目标价空间 40 + 预测 PE 20 + 净利增速 40。"""

    def _data(self):
        return {
            "meta": {"price": 100.0, "pe": 20.0},
            "forecast": {
                "available": True,
                "target_price": 130.0,
                "coverage": 5,
                "forecasts": [
                    {"year": 2026, "pe": 18.0, "net_profit_yoy": 20.0},
                    {"year": 2027, "pe": 16.0, "net_profit_yoy": 15.0},
                ],
            },
            "financials": {"annual": [{"year": 2025, "net_profit": 10e8}]},
        }

    def test_three_parts_weighted(self):
        v = _valuation_score(self._data())
        self.assertAlmostEqual(v["parts"][0]["score"], 100.0)       # 目标价 +30%
        self.assertAlmostEqual(v["parts"][1]["score"], 77.7778, places=3)
        self.assertAlmostEqual(v["parts"][2]["score"], 81.25, places=2)
        self.assertAlmostEqual(v["score"], 88.1, places=1)

    def test_missing_target_price_renormalizes(self):
        data = self._data()
        data["forecast"].pop("target_price")
        v = _valuation_score(data)
        self.assertIsNone(v["parts"][0]["score"])
        self.assertAlmostEqual(v["score"], 80.1, places=1)

    def test_target_price_without_price_does_not_break(self):
        data = self._data()
        data["meta"]["price"] = None
        v = _valuation_score(data)
        self.assertIsNone(v["parts"][0]["score"])
        self.assertIsNotNone(v["score"])       # 预测 PE + 增速仍可计算

    def test_no_coverage_returns_none(self):
        data = self._data()
        data["forecast"] = {"available": False, "forecasts": [], "target_price": None, "coverage": 0}
        v = _valuation_score(data)
        self.assertIsNone(v["score"])
        self.assertEqual(v["grade"], "数据不足")

    def test_negative_base_disables_growth(self):
        data = self._data()
        data["financials"]["annual"][0]["net_profit"] = -1e8
        v = _valuation_score(data)
        self.assertIsNone(v["parts"][2]["score"])
        self.assertIsNone(v["score"])

    def test_no_coverage_keeps_quality_score(self):
        raw = load_bundle(FIXTURE)
        data = build_report_data(raw["calls"], raw["code"])
        data["forecast"] = {"available": False, "forecasts": [], "target_price": None,
                            "coverage": 0, "rating": {}}
        data = compute_scores(data)
        self.assertIsNotNone(data["quality"]["score"])
        self.assertIsNone(data["valuation_score"]["score"])
        self.assertEqual(data["decision"]["key"], "unknown")


class DecisionRulesTest(unittest.TestCase):
    def test_critical_unknown_blocks_buy(self):
        raw = load_bundle(FIXTURE)
        data = build_report_data(raw["calls"], raw["code"])
        q = {"score": 80, "coverage": 100.0}
        checks = [{"key": "cash_flow", "name": "现金流质量", "status": "unknown"}]
        dq = _data_quality(data, q, checks)
        self.assertTrue(any("现金流质量" in x for x in dq["buy_blockers"]))

    def _dq(self, blockers=None):
        return {"buy_blockers": blockers or []}

    def test_buy_requires_complete_data(self):
        d = _decision({"score": 80}, {"score": 70}, [], self._dq())
        self.assertEqual(d["key"], "buy")
        d = _decision({"score": 80}, {"score": 70}, [], self._dq(["机构覆盖 1 家（少于 3 家）"]))
        self.assertEqual(d["key"], "watch")
        self.assertIn("机构覆盖", d["reason"])

    def test_high_quality_bands(self):
        self.assertEqual(_decision({"score": 75}, {"score": 65}, [], self._dq())["key"], "buy")
        self.assertEqual(_decision({"score": 75}, {"score": 50}, [], self._dq())["key"], "watch_price")
        self.assertEqual(_decision({"score": 75}, {"score": 35}, [], self._dq())["key"], "expensive")

    def test_medium_high_quality_needs_higher_v(self):
        self.assertEqual(_decision({"score": 70}, {"score": 80}, [], self._dq())["key"], "buy")
        self.assertEqual(_decision({"score": 70}, {"score": 70}, [], self._dq())["key"], "buy_ok")
        self.assertEqual(_decision({"score": 70}, {"score": 50}, [], self._dq())["key"], "watch")
        self.assertEqual(_decision({"score": 70}, {"score": 49}, [], self._dq())["key"], "avoid")

    def test_medium_quality_small_position_only(self):
        self.assertEqual(_decision({"score": 60}, {"score": 75}, [], self._dq())["key"], "buy_small")
        self.assertEqual(_decision({"score": 60}, {"score": 74}, [], self._dq())["key"], "watch")
        self.assertEqual(_decision({"score": 60}, {"score": 49}, [], self._dq())["key"], "avoid")

    def test_weak_quality_trial_only(self):
        self.assertEqual(_decision({"score": 50}, {"score": 80}, [], self._dq())["key"], "buy_trial")
        self.assertEqual(_decision({"score": 50}, {"score": 79}, [], self._dq())["key"], "watch")
        self.assertEqual(_decision({"score": 50}, {"score": 64}, [], self._dq())["key"], "avoid")

    def test_very_low_quality_never_buys(self):
        d = _decision({"score": 44}, {"score": 95}, [], self._dq())
        self.assertEqual(d["key"], "avoid")
        self.assertIn("禁止买入", d["reason"])

    def test_missing_or_fatal(self):
        self.assertEqual(_decision({"score": None}, {"score": 80}, [], self._dq())["key"], "unknown")
        self.assertEqual(_decision({"score": 80}, {"score": 80}, ["净资产为负"], self._dq())["key"], "avoid")


class ScoreSummaryTest(unittest.TestCase):
    def test_extract_from_rendered_html(self):
        raw = load_bundle(FIXTURE)
        data = compute_scores(build_report_data(raw["calls"], raw["code"]))
        summary = extract_score_summary(render_html(data))
        self.assertEqual(summary.conclusion, data["decision"]["label"])
        self.assertEqual(summary.quality, f"{data['quality']['score']:.1f}")
        vs = data["valuation_score"]["score"]
        self.assertEqual(summary.valuation, f"{vs:.1f}" if vs is not None else "—")

    def test_missing_section_raises(self):
        with self.assertRaises(SummaryError):
            extract_score_summary("<html><body>没有评分区</body></html>")


class CsvBatchTest(unittest.TestCase):
    def setUp(self):
        # 批量模式把结果 Excel 写到 config.XLSX_OUT_DIR；测试改到临时目录，别污染项目
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.xlsx_dir = Path(tmp.name) / "xlsx-output"
        patcher = patch.object(config, "XLSX_OUT_DIR", str(self.xlsx_dir))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write_csv(self, path: Path, codes: list[tuple[str, str]]) -> None:
        lines = ["\ufeff代码,名称,备注"]
        lines.extend(f"{code},{name},保留" for code, name in codes)
        path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        text = path.read_bytes().decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text, newline="")))

    def test_roundtrip_preserves_columns_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.csv"
            self._write_csv(path, [("600519", "贵州茅台")])
            table = read_csv_table(path)
            ensure_result_columns(table)
            table.rows[0][SCORE_COLUMN] = "可买"
            table.rows[0][LINK_COLUMN] = report_link_cell(Path(td) / "报告.html")
            write_csv_table(table)

            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", path.read_bytes())
            rows = self._read_csv(path)
            self.assertEqual(rows[0]["名称"], "贵州茅台")
            self.assertEqual(rows[0]["备注"], "保留")
            self.assertEqual(rows[0][SCORE_COLUMN], "可买")
            self.assertTrue(rows[0][LINK_COLUMN].startswith('=HYPERLINK("file:///'))
            self.assertTrue(link_target(rows[0][LINK_COLUMN]).startswith("file:///"))

    def test_batch_cli_fills_score_and_link(self):
        raw = load_bundle(FIXTURE)
        expected = compute_scores(build_report_data(raw["calls"], raw["code"]))["decision"]["label"]

        def fake_fetch(code, timeout=90.0, **kwargs):
            return load_bundle(FIXTURE)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            csv_path = td_path / "batch.csv"
            out_dir = td_path / "reports"
            self._write_csv(csv_path, [("600519", "贵州茅台")])
            with patch("stock_report.fetch_all", side_effect=fake_fetch):
                rc = stock_report.main([
                    "--csv-input", str(csv_path), "--out-dir", str(out_dir),
                    "--workers", "2", "--quiet",
                ])
            self.assertEqual(rc, 0)
            rows = self._read_csv(csv_path)
            self.assertEqual(rows[0][SCORE_COLUMN], expected)
            link = rows[0][LINK_COLUMN]
            self.assertTrue(link.startswith('=HYPERLINK("file:///'))
            report_path = Path(unquote(urlparse(link_target(link)).path))
            self.assertTrue(report_path.exists())
            self.assertRegex(report_path.name,
                             r"^贵州茅台-sh600519-企业质量初筛-\d{8}-\d{6}\.html$")
            eastmoney = rows[0][EASTMONEY_COLUMN]
            self.assertIn("东方财富网股票详情", eastmoney)
            self.assertEqual(link_target(eastmoney),
                             "https://quote.eastmoney.com/sh600519.html#fullScreenChart")

    def test_second_run_reuses_existing_html_without_fetching(self):
        raw = load_bundle(FIXTURE)
        data = compute_scores(build_report_data(raw["calls"], raw["code"]))
        expected = data["decision"]["label"]

        def must_not_fetch(code, timeout=90.0, **kwargs):
            raise AssertionError("已有报告时不应重新取数")

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            csv_path = td_path / "batch.csv"
            out_dir = td_path / "reports"
            out_dir.mkdir()
            existing = out_dir / "贵州茅台-sh600519-企业质量初筛-20260101-000000.html"
            existing.write_text(render_html(data), encoding="utf-8")
            self._write_csv(csv_path, [("600519", "贵州茅台")])
            with patch("stock_report.fetch_all", side_effect=must_not_fetch):
                rc = stock_report.main([
                    "--csv-input", str(csv_path), "--out-dir", str(out_dir),
                    "--workers", "2", "--quiet",
                ])
            self.assertEqual(rc, 0)
            rows = self._read_csv(csv_path)
            self.assertEqual(rows[0][SCORE_COLUMN], expected)
            report_path = Path(unquote(urlparse(link_target(rows[0][LINK_COLUMN])).path))
            self.assertEqual(report_path, existing)
            self.assertEqual(len(list(out_dir.glob("*-企业质量初筛-*.html"))), 1)

    def test_force_regenerates_existing_report(self):
        raw = load_bundle(FIXTURE)
        data = compute_scores(build_report_data(raw["calls"], raw["code"]))
        calls = {"n": 0}

        def fake_fetch(code, timeout=90.0, **kwargs):
            calls["n"] += 1
            return load_bundle(FIXTURE)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            csv_path = td_path / "batch.csv"
            out_dir = td_path / "reports"
            out_dir.mkdir()
            existing = out_dir / "贵州茅台-sh600519-企业质量初筛-20260101-000000.html"
            existing.write_text(render_html(data), encoding="utf-8")
            self._write_csv(csv_path, [("600519", "贵州茅台")])
            with patch("stock_report.fetch_all", side_effect=fake_fetch):
                rc = stock_report.main([
                    "--csv-input", str(csv_path), "--out-dir", str(out_dir),
                    "--workers", "1", "--force", "--quiet",
                ])
            self.assertEqual(rc, 0)
            self.assertEqual(calls["n"], 1)
            rows = self._read_csv(csv_path)
            report_path = Path(unquote(urlparse(link_target(rows[0][LINK_COLUMN])).path))
            self.assertNotEqual(report_path, existing)
            self.assertEqual(len(list(out_dir.glob("*-企业质量初筛-*.html"))), 2)

    def test_batch_continues_after_one_failure(self):
        def fake_fetch(code, timeout=90.0, **kwargs):
            if code == "sz000001":
                raise DataError("模拟取数失败")
            return load_bundle(FIXTURE)

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            csv_path = td_path / "batch.csv"
            self._write_csv(csv_path, [("600519", "贵州茅台"), ("000001", "平安银行")])
            with patch("stock_report.fetch_all", side_effect=fake_fetch):
                rc = stock_report.main([
                    "--csv-input", str(csv_path), "--out-dir", str(td_path / "reports"),
                    "--workers", "2", "--quiet",
                ])
            self.assertEqual(rc, 1)
            raw = load_bundle(FIXTURE)
            expected = compute_scores(build_report_data(raw["calls"], raw["code"]))["decision"]["label"]
            rows = self._read_csv(csv_path)
            self.assertEqual(rows[0][SCORE_COLUMN], expected)
            self.assertTrue(rows[0][LINK_COLUMN].startswith('=HYPERLINK("file:///'))
            self.assertEqual(rows[1][SCORE_COLUMN], "生成失败")
            self.assertEqual(rows[1][LINK_COLUMN], "")


class EastmoneyUrlTest(unittest.TestCase):
    def test_market_prefix_and_plain_codes(self):
        expected = "https://quote.eastmoney.com/sz300059.html#fullScreenChart"
        self.assertEqual(eastmoney_url("sz300059"), expected)
        self.assertEqual(eastmoney_url("300059"), expected)
        self.assertEqual(eastmoney_url("600519"),
                         "https://quote.eastmoney.com/sh600519.html#fullScreenChart")
        self.assertEqual(eastmoney_url("920001"),
                         "https://quote.eastmoney.com/bj/920001.html#fullScreenChart")
        self.assertEqual(eastmoney_url("bad"), "")


class NavigationOutputTest(unittest.TestCase):
    def test_xlsx_and_index_contain_clickable_report_links(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            csv_path = td_path / "rows.csv"
            out_dir = td_path / "reports"
            out_dir.mkdir()
            report = out_dir / "贵州茅台-sh600519-企业质量初筛-20260101-000000.html"
            report.write_text("<html>ok</html>", encoding="utf-8")
            csv_path.write_bytes("\ufeff代码,名称\r\n600519,贵州茅台\r\n".encode())
            table = read_csv_table(csv_path)
            ensure_result_columns(table)
            table.rows[0][SCORE_COLUMN] = "可买"
            table.rows[0][LINK_COLUMN] = report_link_cell(report)
            table.rows[0][EASTMONEY_COLUMN] = eastmoney_link_cell("600519")
            write_csv_table(table)

            xlsx = write_report_xlsx(table)
            with zipfile.ZipFile(xlsx) as zf:
                sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
                rels = zf.read("xl/worksheets/_rels/sheet1.xml.rels").decode("utf-8")
            self.assertIn("报告链接", sheet)
            self.assertIn("东方财富网股票详情", sheet)
            self.assertIn("hyperlink", sheet)
            self.assertIn("file:///", rels)
            self.assertIn("https://quote.eastmoney.com/sh600519.html#fullScreenChart", rels)

            index = write_index_html(table, out_dir)
            text = index.read_text(encoding="utf-8")
            self.assertIn("报告链接", text)
            self.assertIn("东方财富网股票详情", text)
            self.assertIn("https://quote.eastmoney.com/sh600519.html#fullScreenChart", text)
            self.assertIn('class="btn"', text)
            self.assertIn("贵州茅台", text)


if __name__ == "__main__":
    unittest.main()
