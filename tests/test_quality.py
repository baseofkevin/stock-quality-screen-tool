# -*- coding: utf-8 -*-
"""质量分 Q：5 组 16 个子项、组内防作弊汇总、口径修正（A1~A4）、覆盖率、分档。"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unittest.mock import patch

import support
import config
from screen.score import _group, _is_financial, _quality, compute_scores


def quality(rows):
    return _quality(support.with_annual(rows))


class GroupAggregationTest(unittest.TestCase):
    """组内汇总：缺失子项按 0 分计入，不按“剩余项归一”。"""

    def test_full_coverage_scores_full_weight(self):
        parts = [{"label": "A", "score": 20.0, "max": 20, "raw": ""},
                 {"label": "B", "score": 10.0, "max": 10, "raw": ""}]
        group = _group(parts, "returns")
        self.assertEqual(group["score"], 30.0)
        self.assertEqual(group["coverage"], 100.0)
        self.assertEqual(group["max"], 30)

    def test_partial_score_is_scaled_by_weight(self):
        parts = [{"label": "A", "score": 12.0, "max": 20, "raw": ""},
                 {"label": "B", "score": 10.0, "max": 10, "raw": ""}]
        group = _group(parts, "returns")
        self.assertEqual(group["score"], 22.0)      # 22/30 × 30
        self.assertEqual(group["coverage"], 100.0)

    def test_missing_item_loses_its_points(self):
        parts = [{"label": "A", "score": None, "max": 20, "raw": "—"},
                 {"label": "B", "score": 10.0, "max": 10, "raw": ""}]
        group = _group(parts, "returns")
        self.assertEqual(group["score"], 10.0)     # 10/30 × 30，而不是满分 30
        self.assertAlmostEqual(group["coverage"], 33.3, places=1)

    def test_all_missing_returns_none(self):
        parts = [{"label": "A", "score": None, "max": 20, "raw": ""},
                 {"label": "B", "score": None, "max": 10, "raw": ""}]
        self.assertIsNone(_group(parts, "returns")["score"])


class QualityPerfectCompanyTest(unittest.TestCase):
    def setUp(self):
        self.rows = support.annual_rows(
            5,
            revenue=[100e8, 115e8, 132.25e8, 152.09e8, 174.9e8],   # 15% CAGR
            roic=30.0,                                             # spread 21 ≥ 15
            roe=25.0,
            net_profit=12e8,
            ocf=14.4e8,                                            # CFO/净利 = 1.2
            fcf=12e8,                                              # FCF/净利 = 1.0
            fcf_margin=0.15,                                       # FCF/营收 = 15%（A3 新增项）
            debt=0.0, cash=20e8,
            finance_expense=-1e8,                                  # 净利息收入
            goodwill=0.0,
            gross_margin=40.0,                                     # 水平修正 ×1.0
            shares=10e8,
            deducted=12e8,
        )

    def test_full_marks(self):
        q = quality(self.rows)
        self.assertEqual(q["score"], 100.0)
        self.assertEqual(q["grade"], "优秀")
        self.assertEqual(q["coverage"], 100.0)
        self.assertEqual([g["label"] for g in q["groups"]],
                         ["资本回报", "现金创造力", "资产负债表", "成长与稳定", "会计质量"])

    def test_each_sub_item_raw_is_recorded(self):
        items = {i["label"]: i for g in quality(self.rows)["groups"] for i in g["items"]}
        self.assertEqual(items["ROIC−WACC"]["raw"], "21.0%")
        self.assertEqual(items["ROIC>WACC 年数"]["raw"], "5/5")
        self.assertEqual(items["利息保障"]["raw"], "净利息收入")
        self.assertEqual(items["FCF 为正年数"]["raw"], "5/5")
        self.assertEqual(items["FCF/营收"]["raw"], "15.0%")
        self.assertIn("水平 ×1.00", items["毛利率稳定性"]["raw"])
        self.assertEqual(len(items), 16)


class QualityItemMaxTest(unittest.TestCase):
    """子项满分集中放在 config，每组合计必须等于组权重（否则该组系统性偏高/偏低）。"""

    def test_each_group_sums_to_its_weight(self):
        for key, weight in config.QUALITY_WEIGHTS.items():
            self.assertEqual(sum(config.QUALITY_ITEM_MAX[key].values()), weight, key)

    def test_weights_total_one_hundred(self):
        self.assertEqual(sum(config.QUALITY_WEIGHTS.values()), 100)

    def test_quality_uses_every_declared_item(self):
        """config 里声明了但 _quality 没用到的子项，会让该组白丢分。"""
        items = {i["label"]: i for g in quality(support.annual_rows(5))["groups"] for i in g["items"]}
        declared = sum(len(v) for v in config.QUALITY_ITEM_MAX.values())
        self.assertEqual(len(items), declared)


class GrossMarginLevelTest(unittest.TestCase):
    """A1：毛利率稳定性要乘一道水平门槛，低毛利的“稳”不值满分。"""

    def _item(self, gm):
        rows = support.annual_rows(5, gross_margin=gm)          # σ = 0 → 稳定性原始分 4
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        return items["毛利率稳定性"]

    def test_low_margin_is_zeroed(self):
        item = self._item(12.0)                                  # (12−15)/10 → 负数 → 0
        self.assertEqual(item["score"], 0.0)
        self.assertIn("中位 12.0%", item["raw"])

    def test_half_way_level(self):
        item = self._item(20.0)                                  # (20−15)/10 = 0.5 → 4×0.5
        self.assertAlmostEqual(item["score"], 2.0)
        self.assertIn("水平 ×0.50", item["raw"])

    def test_full_margin_keeps_full_marks(self):
        item = self._item(25.0)                                  # 到达 25% 门槛
        self.assertAlmostEqual(item["score"], 4.0)

    def test_high_margin_is_capped_at_full(self):
        item = self._item(60.0)                                  # 修正系数不许 >1
        self.assertAlmostEqual(item["score"], 4.0)

    def test_missing_margin_is_not_scored(self):
        item = self._item(None)
        self.assertIsNone(item["score"])
        self.assertEqual(item["raw"], "σ —")

    def test_single_year_margin_is_not_scored(self):
        """只有 1 年毛利率 → σ 为空：这一格要留空，不能拿 None 去乘水平修正。"""
        rows = support.annual_rows(5, gross_margin=[40.0, None, None, None, None])
        item = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}["毛利率稳定性"]
        self.assertIsNone(item["score"])
        self.assertIn("中位 40.0%", item["raw"])


class AccrualMedianTest(unittest.TestCase):
    """A2：应计利润取近 3 年中位数，单年一次性项目不再决定这一格。"""

    def test_single_year_spike_is_ignored(self):
        # 应计 = (归母净利 − OCF) / 总资产：0/0/0/0/70 (%)，近 3 年中位 = 0
        # 若只看单年（70%）这一格是 0 分；取中位数后给满分 5，一次性项目不再主导判定
        rows = support.annual_rows(
            5, net_profit=10e8, total_assets=100e8,
            ocf=[10e8, 10e8, 10e8, 10e8, -60e8],
        )
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertAlmostEqual(items["应计利润"]["score"], 5.0)
        self.assertIn("3 年中位 0.0%", items["应计利润"]["raw"])
        self.assertIn("单年 70.0%", items["应计利润"]["raw"])

    def test_median_uses_last_three_years_only(self):
        # 最早两年是 0%，最近三年 4% → 中位 4%（若用全部 5 年也是 4%，这里验分母只取 3 年）
        rows = support.annual_rows(
            5, net_profit=10e8, total_assets=100e8,
            ocf=[10e8, 10e8, 6e8, 6e8, 6e8],
        )
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertAlmostEqual(items["应计利润"]["score"], 3.0)   # inverse(4, 0, 10, 5)
        self.assertIn("3 年中位 4.0%", items["应计利润"]["raw"])

    def test_missing_total_assets_is_not_scored(self):
        rows = support.annual_rows(3, total_assets=None)
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertIsNone(items["应计利润"]["score"])


class CashGroupTest(unittest.TestCase):
    """A3：现金组加 FCF/营收（0~15% → 0~4）。"""

    def _items(self, **fields):
        rows = support.annual_rows(5, **fields)
        return {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}

    def test_fcf_positive_ratio_uses_six_points(self):
        items = self._items(fcf=[12e8, 12e8, 12e8, -1e8, -2e8])
        self.assertAlmostEqual(items["FCF 为正年数"]["score"], 3.6)   # 3/5 × 6
        self.assertEqual(items["FCF 为正年数"]["raw"], "3/5")

    def test_fcf_margin_full_marks(self):
        self.assertAlmostEqual(self._items(fcf_margin=0.15)["FCF/营收"]["score"], 4.0)

    def test_fcf_margin_half(self):
        self.assertAlmostEqual(self._items(fcf_margin=0.075)["FCF/营收"]["score"], 2.0)

    def test_fcf_margin_negative_is_zero(self):
        item = self._items(fcf_margin=-0.05)["FCF/营收"]
        self.assertEqual(item["score"], 0.0)
        self.assertEqual(item["raw"], "-5.0%")

    def test_missing_fcf_margin_costs_points_and_coverage(self):
        rows = support.annual_rows(5, fcf_margin=None)
        cash = next(g for g in quality(rows)["groups"] if g["label"] == "现金创造力")
        self.assertIsNone({i["label"]: i for i in cash["items"]}["FCF/营收"]["score"])
        # 其余三项：6（5/5）+ 8（FCF/净利 1.0）+ 7×(1.167−0.7)/0.5 = 20.53
        self.assertAlmostEqual(cash["score"], 20.53, places=2)
        self.assertAlmostEqual(cash["coverage"], 84.0)                # 21/25


class ReturnsGroupTest(unittest.TestCase):
    """A4：ROIC>WACC 年数 10 分，ROE 从 10 降到 6。"""

    def _items(self, **fields):
        rows = support.annual_rows(5, **fields)
        return {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}

    def test_all_years_above_wacc(self):
        item = self._items(roic=12.0)["ROIC>WACC 年数"]              # WACC 9
        self.assertAlmostEqual(item["score"], 10.0)
        self.assertEqual(item["raw"], "5/5")

    def test_one_year_above_wacc(self):
        item = self._items(roic=[8.0, 8.0, 8.0, 8.0, 20.0])["ROIC>WACC 年数"]
        self.assertAlmostEqual(item["score"], 2.0)
        self.assertEqual(item["raw"], "1/5")

    def test_roe_only_gets_six_points(self):
        returns = next(g for g in quality(support.annual_rows(3, roe=20.0, roic=None))["groups"]
                       if g["label"] == "资本回报")
        self.assertAlmostEqual(returns["score"], 6.0)                 # 6/30 × 30
        self.assertAlmostEqual(returns["coverage"], 20.0)             # 6/30

    def test_missing_roic_is_not_counted_as_below_wacc(self):
        rows = support.annual_rows(5, roic=[12.0, 12.0, None, None, None])
        item = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}["ROIC>WACC 年数"]
        # 分母用「有 ROIC 的年份」，缺数据的年份不算“低于 WACC”
        self.assertAlmostEqual(item["score"], 10.0)
        self.assertEqual(item["raw"], "2/2")


class QualitySubItemTest(unittest.TestCase):
    """单项缺失/劣化只影响它自己那一份分。"""

    def test_interest_cover_net_income_is_full_marks(self):
        rows = support.annual_rows(3, finance_expense=-5e8)
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertEqual(items["利息保障"]["score"], 6.0)
        self.assertEqual(items["利息保障"]["raw"], "净利息收入")

    def test_interest_cover_below_three_scores_zero(self):
        rows = support.annual_rows(3, ebit=10e8, finance_expense=5e8)   # 2x
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertEqual(items["利息保障"]["score"], 0.0)

    def test_goodwill_missing_reduces_balance_coverage(self):
        rows = support.annual_rows(3, goodwill=None)
        q = quality(rows)
        balance = next(g for g in q["groups"] if g["label"] == "资产负债表")
        items = {i["label"]: i for i in balance["items"]}
        self.assertIsNone(items["商誉/净资产"]["score"])
        self.assertAlmostEqual(balance["coverage"], 70.0)              # 14/20
        self.assertAlmostEqual(balance["score"], 14.0)                 # 8 + 6

    def test_accrual_ten_percent_scores_zero(self):
        rows = support.annual_rows(3, net_profit=20e8, ocf=0.0, total_assets=200e8)
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertAlmostEqual(items["应计利润"]["score"], 0.0)
        self.assertEqual(items["应计利润"]["raw"], "3 年中位 10.0%（单年 10.0%）")

    def test_deducted_ratio_below_seventy_scores_zero(self):
        rows = support.annual_rows(3, net_profit=12e8, deducted=7e8)
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertAlmostEqual(items["扣非占比"]["score"], 0.0)

    def test_share_dilution_uses_last_three_years(self):
        rows = support.annual_rows(5, shares=[10e8, 10e8, 10.3e8, 10.61e8, 10.93e8])
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertAlmostEqual(items["股本稀释"]["score"], 0.0)        # 3%/年 → 0

    def test_revenue_cagr_uses_first_and_last_year(self):
        rows = support.annual_rows(3, revenue=[100e8, 100e8, 132.25e8])
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertAlmostEqual(items["营收 CAGR"]["score"], 5.0)       # 15%

    def test_net_debt_negative_scores_full(self):
        rows = support.annual_rows(3, debt=5e8, cash=30e8, ebit=16e8)
        items = {i["label"]: i for g in quality(rows)["groups"] for i in g["items"]}
        self.assertAlmostEqual(items["净负债/EBIT"]["score"], 8.0)


class QualityMissingDataTest(unittest.TestCase):
    def test_single_annual_is_not_enough(self):
        q = quality(support.annual_rows(1))
        self.assertIsNone(q["score"])
        self.assertEqual(q["grade"], "数据不足")
        self.assertEqual(q["groups"], [])
        self.assertEqual(q["coverage"], 0.0)

    def test_two_annuals_are_not_enough_either(self):
        """0.9.4：门槛从 2 年提到 3 年。2 个点的 σ / CAGR 不该拿来定性。"""
        q = quality(support.annual_rows(2))
        self.assertIsNone(q["score"])
        self.assertEqual(q["grade"], "数据不足")

    def test_three_annuals_is_enough(self):
        q = quality(support.annual_rows(3))
        self.assertIsNotNone(q["score"])

    def test_all_fields_missing_returns_none(self):
        rows = support.annual_rows(2, revenue=None, net_profit=None, net_profit_total=None,
                                   deducted=None, gross_margin=None, roe=None, roic=None,
                                   ocf=None, fcf=None, fcf_margin=None, debt=None, cash=None,
                                   ebit=None, finance_expense=None, goodwill=None,
                                   shares=None, total_assets=None)
        q = quality(rows)
        self.assertIsNone(q["score"])
        self.assertEqual(q["grade"], "数据不足")

    def test_partial_group_still_produces_total(self):
        # 0.9.4 起年报 <3 个整只跳过，所以这里用 3 年（各年同值，中位数/σ 与 2 年时一致）
        rows = support.annual_rows(3, roe=20.0, roic=None, net_profit=None, ocf=None,
                                   fcf=None, fcf_margin=None, debt=None, cash=None, ebit=None,
                                   finance_expense=None, goodwill=None, revenue=None,
                                   gross_margin=None, shares=None, total_assets=None,
                                   deducted=None)
        q = quality(rows)
        returns = next(g for g in q["groups"] if g["label"] == "资本回报")
        # 只有 ROE 满分 6，组内满分 30 → 6/30×30 = 6（缺的 24 分直接丢掉）
        self.assertAlmostEqual(returns["score"], 6.0, places=1)
        self.assertAlmostEqual(returns["coverage"], 20.0, places=1)
        # ROE 稳定性还能算出来（roe 有值），所以成长组拿到 3 分
        self.assertAlmostEqual(q["score"], 20.0, places=1)
        self.assertEqual(q["grade"], "差")
        self.assertAlmostEqual(q["coverage"], 9.0, places=1)


class QualityGradeTest(unittest.TestCase):
    """分档边界：用 patch 控制总分，只验等级映射。"""

    def _grade_for(self, total):
        # 0.9.8 起 _group 只收 key，组名和权重都从 config 取
        def fake_group(parts, key):
            weight = config.QUALITY_WEIGHTS[key]
            return {"key": key, "label": config.QUALITY_GROUP_LABELS[key], "weight": weight,
                    "score": weight * total / 100.0, "max": weight,
                    "coverage": 100.0, "items": parts}

        with patch("screen.score._group", side_effect=fake_group):
            return _quality(support.with_annual(support.annual_rows(3)))["grade"]

    def test_boundaries(self):
        cases = [(100, "优秀"), (85, "优秀"), (84.9, "良好"), (75, "良好"),
                 (74.9, "中等偏上"), (65, "中等偏上"), (64.9, "中等"),
                 (55, "中等"), (54.9, "偏弱"), (45, "偏弱"), (44.9, "差"), (0, "差")]
        for total, expected in cases:
            self.assertEqual(self._grade_for(total), expected, total)


class FinancialStockTest(unittest.TestCase):
    """银行/保险/证券：口径不可比，不出 Q/V 结论。"""

    def _data(self, industry: str) -> dict:
        data = support.report_data()
        data["meta"]["industry"] = industry
        return compute_scores(data)

    def test_industry_keywords(self):
        for name in ("银行", "保险", "证券"):
            self.assertTrue(_is_financial({"meta": {"industry": f"{name}业"}}), name)
        self.assertFalse(_is_financial({"meta": {"industry": "食品饮料"}}))
        self.assertFalse(_is_financial({}))

    def test_financial_stock_gets_no_score_but_keeps_risks(self):
        data = self._data("银行")
        self.assertIsNone(data["quality"]["score"])
        self.assertIsNone(data["valuation_score"]["score"])
        self.assertEqual(data["quality"]["grade"], "金融股不适用")
        self.assertTrue(data["quality"]["not_applicable"])
        self.assertEqual(data["decision"]["key"], "unknown")
        self.assertIn("金融股不适用", data["decision"]["label"])
        self.assertEqual(len(data["risks"]["checks"]), config.RISK_CHECK_COUNT)   # 风险原文仍展示
        self.assertEqual(data["moat"]["level"], "不适用")
        self.assertIn("金融股不适用", data["data_quality"]["buy_blockers"][0])

    def test_normal_stock_is_unaffected(self):
        data = self._data("食品饮料")
        self.assertIsNotNone(data["quality"]["score"])
        self.assertFalse(data["quality"].get("not_applicable", False))
        self.assertNotIn("金融股", data["decision"]["label"])

    def test_financial_stock_passes_validate(self):
        from screen.validate import validate
        validate(self._data("证券"))                                 # 不应抛错


class AnnualYearsGateTest(unittest.TestCase):
    """上市不足 3 年（年报 <3 个）整只跳过：不是失败，也不出「数据不足」报告。"""

    def _data(self, years):
        return {"meta": {"code": "sh600519"},
                "financials": {"annual": support.annual_rows(years)}}

    def test_zero_annuals_is_an_error(self):
        from screen.validate import ScreenError, validate
        with self.assertRaises(ScreenError) as ctx:
            validate(self._data(0))
        self.assertIn("没有可用年报", str(ctx.exception))

    def test_one_and_two_annuals_are_skipped(self):
        from screen.validate import SkipStock, validate
        for years in (1, 2):
            with self.assertRaises(SkipStock) as ctx:
                validate(self._data(years))
            self.assertIn("上市不足 3 年", str(ctx.exception))
            self.assertIn(f"仅 {years} 个年报", str(ctx.exception))

    def test_skip_stock_is_a_screen_error(self):
        """继承 ScreenError：忘了接住的地方仍按失败处理，不会静默吞掉。"""
        from screen.validate import ScreenError, SkipStock
        self.assertTrue(issubclass(SkipStock, ScreenError))

    def test_skip_text_matches_config(self):
        from screen.batch import SKIP_SCORE_TEXT
        self.assertEqual(SKIP_SCORE_TEXT, f"跳过：上市不足 {config.MIN_ANNUAL_YEARS} 年")
        self.assertEqual(config.MIN_ANNUAL_YEARS, 3)


class ComputeScoresRobustnessTest(unittest.TestCase):
    """只有 financials 的 data 也要能算完（P2-7：不假设 valuation/meta 键存在）。"""

    def test_missing_valuation_block_does_not_crash(self):
        data = compute_scores(support.with_annual(support.annual_rows(5)))
        self.assertIn("decision", data)
        pe_row = next(t for t in data["tracking"] if t["metric"] == "PE 分位")
        self.assertEqual(pe_row["current"], "—")

    def test_missing_meta_and_forecast_do_not_crash(self):
        data = compute_scores({"financials": {"annual": support.annual_rows(5)},
                               "valuation": {"metrics": {}}})
        self.assertIsNone(data["valuation_score"]["score"])


if __name__ == "__main__":
    unittest.main()
