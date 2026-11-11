# -*- coding: utf-8 -*-
"""14 项风险检查（真伪/趋势/质量/安全）、致命项、数据完整度与决策矩阵。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import support
from screen.score import (_data_quality, _decision, _fatal, _forecast_metrics,
                          _pattern_summary, _risk_checks)

CHECK_KEYS = [
    "cash_flow", "nonrecurring",
    "margin_improve", "contract_liability",
    "ar_gap", "inventory_gap", "cashflow_pattern", "construction", "per_share",
    "cash_debt", "leverage", "interest", "goodwill", "other_receivable",
]


def checks_by_key(rows):
    return {c["key"]: c for c in _risk_checks(support.with_annual(rows))}


# ---------------------------------------------------------------- 真伪
class CashFlowCheckTest(unittest.TestCase):
    """1 净现比 TTM 四档 + FCF 负年数（原「利润含金量」与「FCF 持续性」合并）。"""

    def test_clear_when_cash_conversion_is_healthy(self):
        c = checks_by_key(support.annual_rows(5, ocf=14e8, net_profit=12e8))["cash_flow"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("优秀", c["detail"])
        self.assertIn("FCF 5 年中 0 年为负", c["detail"])
        self.assertEqual(c["severity"], "高")

    def test_watch_in_the_middle_band(self):
        c = checks_by_key(support.annual_rows(5, ocf=7e8, net_profit=12e8))["cash_flow"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("警惕", c["detail"])

    def test_hit_when_dangerous(self):
        c = checks_by_key(support.annual_rows(5, ocf=2e8, net_profit=12e8))["cash_flow"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("危险", c["detail"])

    def test_hit_when_two_consecutive_years_below_half(self):
        rows = support.annual_rows(5, ocf=[14e8, 14e8, 14e8, 5e8, 5.5e8], net_profit=12e8)
        c = checks_by_key(rows)["cash_flow"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("连续 2 年 < 0.5", c["detail"])

    def test_hit_when_fcf_negative_three_years(self):
        rows = support.annual_rows(5, fcf=[12e8, -1e8, -1e8, -1e8, 12e8])
        c = checks_by_key(rows)["cash_flow"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("3 年为负", c["detail"])

    def test_unknown_when_loss(self):
        c = checks_by_key(support.annual_rows(3, net_profit=-1e8))["cash_flow"]
        self.assertEqual(c["status"], "unknown")

    def test_ttm_fields_take_precedence(self):
        rows = support.annual_rows(5, ocf=14e8, net_profit=12e8,
                                   ocf_ttm=3e8, np_ttm=12e8)
        c = checks_by_key(rows)["cash_flow"]
        self.assertEqual(c["status"], "hit")   # 0.25，用 TTM 而不是年报值 1.17
        self.assertIn("(TTM)", c["detail"])

    def test_fcf_text_says_not_applicable_when_no_year_available(self):
        rows = support.annual_rows(5, ocf=14e8, net_profit=12e8, fcf=[None] * 5)
        c = checks_by_key(rows)["cash_flow"]
        self.assertEqual(c["status"], "clear")          # 净现比好，不因缺 FCF 就改判
        self.assertIn("FCF 无可用年度（口径不适用）", c["detail"])
        self.assertNotIn("0 年中 0 年为负", c["detail"])


class NonRecurringCheckTest(unittest.TestCase):
    """2 扣非/归母缺口 + 扣非增速缺口 + 期间费用率增速差。"""

    def test_clear_by_default(self):
        c = checks_by_key(support.annual_rows(3))["nonrecurring"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("扣非/归母 95.8%", c["detail"])

    def test_hit_below_seventy_percent(self):
        c = checks_by_key(support.annual_rows(3, net_profit=12e8, deducted=7e8))["nonrecurring"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("58.3%", c["detail"])

    def test_unknown_when_parent_profit_negative(self):
        c = checks_by_key(support.annual_rows(3, net_profit=-1e8))["nonrecurring"]
        self.assertEqual(c["status"], "unknown")

    def test_detail_has_deducted_growth_gap(self):
        rows = support.annual_rows(3, deducted=[8e8, 9e8, 11.5e8], net_profit=12e8)
        c = checks_by_key(rows)["nonrecurring"]
        self.assertIn("扣非增速", c["detail"])
        self.assertIn("归母", c["detail"])

    def test_watch_when_expenses_outgrow_revenue(self):
        rows = support.annual_rows(3, revenue=100e8, sell_expense=[3e8, 3e8, 7e8])
        c = checks_by_key(rows)["nonrecurring"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("增速差", c["detail"])


# ---------------------------------------------------------------- 趋势
class MarginImproveTest(unittest.TestCase):
    """3 ① 毛利率环比改善三条件 + 毛利率/净利率/营收的同比、环比对照。"""

    # 五期季报：营收 100/101/102/103/104 亿，毛利率 40/41/42/43/45，净利率 18/19/20/21/23
    BASE = [
        ("2025-03-31", 100e8, 40.0, 18.0), ("2025-06-30", 101e8, 41.0, 19.0),
        ("2025-09-30", 102e8, 42.0, 20.0), ("2025-12-31", 103e8, 43.0, 21.0),
        ("2026-03-31", 104e8, 45.0, 23.0),
    ]

    def _check(self, points):
        return {c["key"]: c for c in _risk_checks(support.margin_data(points))}["margin_improve"]

    def test_clear_when_all_three_hold(self):
        c = self._check(self.BASE)
        self.assertEqual(c["status"], "clear")
        self.assertIn("C1/C2/C3 成立", c["detail"])
        self.assertIn("毛利率 +5.00pct", c["detail"])      # 同比
        self.assertIn("毛利率 +2.00pct", c["detail"])      # 环比
        self.assertIn("营收 +4.0%", c["detail"])
        self.assertIn("营收 +1.0%", c["detail"])

    def test_watch_when_yoy_condition_fails(self):
        points = [("2025-03-31", 100e8, 50.0, 20.0), ("2025-06-30", 101e8, 41.0, 19.0),
                  ("2025-09-30", 102e8, 42.0, 20.0), ("2025-12-31", 103e8, 43.0, 21.0),
                  ("2026-03-31", 104e8, 45.0, 21.0)]
        c = self._check(points)
        self.assertEqual(c["status"], "watch")
        self.assertIn("C3 不成立", c["detail"])
        # 点名的是「毛利率同比」，不是笼统的「未改善」
        self.assertEqual(c["compare"]["badge"], "毛利率同比走弱")
        self.assertIn("「毛利率同比」（-5.00pct）", c["compare"]["verdict"])
        self.assertIn("其余 5 项改善或持平", c["compare"]["verdict"])

    def test_watch_when_revenue_falls(self):
        points = [("2025-03-31", 100e8, 40.0, 18.0), ("2025-06-30", 101e8, 41.0, 19.0),
                  ("2025-09-30", 102e8, 42.0, 20.0), ("2025-12-31", 103e8, 43.0, 21.0),
                  ("2026-03-31", 99e8, 45.0, 23.0)]
        c = self._check(points)
        self.assertEqual(c["status"], "watch")
        self.assertIn("C2 不成立", c["detail"])
        # 同比、环比都下滑 → badge 合成一句
        self.assertEqual(c["compare"]["badge"], "营业收入同比、环比下滑")

    def test_hit_when_margins_turn_down(self):
        points = [("2025-03-31", 100e8, 50.0, 20.0), ("2025-06-30", 101e8, 48.0, 19.0),
                  ("2025-09-30", 102e8, 44.0, 18.0), ("2025-12-31", 103e8, 42.0, 17.0),
                  ("2026-03-31", 104e8, 40.0, 16.0)]
        c = self._check(points)
        self.assertEqual(c["status"], "hit")
        self.assertIn("走弱", c["detail"])
        self.assertEqual(c["compare"]["badge"], "毛利率同比、环比走弱；净利率同比、环比走弱")

    def test_compare_lines_carry_six_numbers(self):
        c = self._check(self.BASE)["compare"]
        self.assertIn("同比（2026-03-31 vs 2025-03-31）", c["yoy_line"])
        self.assertIn("营业收入 104.00 亿（+4.0%，上年同季 100.00 亿）", c["yoy_line"])
        self.assertIn("毛利率 45.00%（+5.00pct，上年同季 40.00%）", c["yoy_line"])
        self.assertIn("净利率（归母） 23.00%（+5.00pct，上年同季 18.00%）", c["yoy_line"])
        self.assertIn("环比（2026-03-31 vs 2025-12-31）", c["qoq_line"])
        self.assertIn("毛利率 45.00%（+2.00pct，上一季 43.00%）", c["qoq_line"])
        self.assertIn("净利率（归母） 23.00%（+2.00pct，上一季 21.00%）", c["qoq_line"])

    def test_clear_badge_says_both_bases_improved(self):
        c = self._check(self.BASE)
        self.assertEqual(c["compare"]["badge"], "毛利率同比、环比均改善")
        self.assertIn("三项条件全部成立", c["compare"]["verdict"])

    def test_net_margin_weakness_is_reported_when_margins_pass(self):
        """三条件只判毛利率和营收；净利率走弱仍要在正文点出来，不能装作没看见。"""
        points = [("2025-03-31", 100e8, 40.0, 30.0), ("2025-06-30", 101e8, 41.0, 28.0),
                  ("2025-09-30", 102e8, 42.0, 26.0), ("2025-12-31", 103e8, 43.0, 24.0),
                  ("2026-03-31", 104e8, 45.0, 22.0)]
        c = self._check(points)
        self.assertEqual(c["status"], "clear")
        self.assertIn("净利率同比", c["compare"]["verdict"])
        self.assertIn("不在三条件之内", c["compare"]["verdict"])

    def test_unknown_when_report_periods_are_not_consecutive(self):
        """接口缺季时不能按位置取“上一季”，否则拿年报和三季报比环比。

        这里只有 2025Q1、Q2、Q4：最新一期的上一季（Q3）和上年同季（2024Q4）都缺。
        """
        c = self._check([
            ("2025-03-31", 100e8, 40.0), ("2025-06-30", 102e8, 42.0),
            ("2025-12-31", 103e8, 43.0),
        ])
        self.assertEqual(c["status"], "unknown")
        self.assertIn("季报不连续", c["detail"])
        self.assertEqual(c["compare"], {})

    def test_unknown_without_quarter_data(self):
        c = {x["key"]: x for x in _risk_checks(support.with_annual(
            support.annual_rows(3)))}["margin_improve"]
        self.assertEqual(c["status"], "unknown")

    def test_missing_net_margin_is_marked_not_counted(self):
        """净利率缺失不能算“改善”，要写“缺数据未判定”。"""
        points = [("2025-03-31", 100e8, 40.0), ("2025-06-30", 101e8, 41.0),
                  ("2025-09-30", 102e8, 42.0), ("2025-12-31", 103e8, 43.0),
                  ("2026-03-31", 105e8, 45.0)]
        c = self._check(points)
        self.assertIn("净利率同比、净利率环比缺数据未判定", c["compare"]["verdict"])


class ContractLiabilityTest(unittest.TestCase):
    """4 ② 合同负债/营收：同比 + 占比。"""

    def test_clear_when_expanding(self):
        rows = support.annual_rows(3, contract_liability=[6e8, 6e8, 8e8])
        c = checks_by_key(rows)["contract_liability"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("需求扩张", c["detail"])
        self.assertIn("占营收 8.0%", c["detail"])

    def test_watch_when_weakening(self):
        rows = support.annual_rows(3, contract_liability=[12e8, 12e8, 8e8])
        c = checks_by_key(rows)["contract_liability"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("预收转弱", c["detail"])

    def test_hit_when_two_periods_of_decline(self):
        rows = support.annual_rows(3, contract_liability=[8e8, 6e8, 4.5e8])
        c = checks_by_key(rows)["contract_liability"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("连续两期下滑", c["detail"])

    def test_unknown_without_field(self):
        rows = support.annual_rows(3, contract_liability=None, advance_payment=None)
        self.assertEqual(checks_by_key(rows)["contract_liability"]["status"], "unknown")

    def test_advance_payment_is_added(self):
        rows = support.annual_rows(3, contract_liability=6e8, advance_payment=2e8,
                                   revenue=100e8)
        c = checks_by_key(rows)["contract_liability"]
        self.assertIn("8.00 亿", c["detail"])


# ---------------------------------------------------------------- 质量
class ArGapTest(unittest.TestCase):
    """5 应收增速差：应收增速 − 营收增速。"""

    def test_clear_by_default(self):
        c = checks_by_key(support.annual_rows(3))["ar_gap"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("应收占营收 5.0%", c["detail"])

    def test_hit_when_two_years_over_fifteen_points(self):
        rows = support.annual_rows(3, revenue=100e8, ar=[5e8, 7e8, 10e8])
        c = checks_by_key(rows)["ar_gap"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("连续两年 > 15pct", c["detail"])

    def test_watch_when_only_latest_year(self):
        rows = support.annual_rows(3, revenue=100e8, ar=[5e8, 5e8, 7e8])
        c = checks_by_key(rows)["ar_gap"]
        self.assertEqual(c["status"], "watch")

    def test_unknown_when_receivable_base_too_small(self):
        rows = support.annual_rows(3, revenue=100e8, ar=[2e6, 2e6, 4e6])
        c = checks_by_key(rows)["ar_gap"]
        self.assertEqual(c["status"], "unknown")
        self.assertIn("基数过小", c["detail"])

    def test_material_but_small_base_only_warns(self):
        rows = support.annual_rows(3, revenue=100e8, ar=[1.2e8, 1.2e8, 1.9e8])
        c = checks_by_key(rows)["ar_gap"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("仅提示", c["detail"])

    def test_two_years_over_fifteen_but_small_base_only_warns(self):
        """连续两年 >15pct 也不能绕过小基数保护（应收占营收 1.6%）。"""
        rows = support.annual_rows(3, revenue=100e8, ar=[1.0e8, 1.2e8, 1.6e8])
        c = checks_by_key(rows)["ar_gap"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("仅提示", c["detail"])
        self.assertIn("连续两年 > 15pct", c["detail"])
        self.assertNotEqual(c["status"], "hit")

    def test_material_ratio_boundary_still_hits(self):
        """刚好 2%（AR_MATERIAL_RATIO）算够大，连续两年 >15pct 仍判命中。"""
        rows = support.annual_rows(3, revenue=100e8, ar=[1.25e8, 1.5e8, 2.0e8])
        c = checks_by_key(rows)["ar_gap"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("连续两年 > 15pct", c["detail"])

    def test_receivable_fin_is_not_counted_as_receivable(self):
        """应收款项融资是票据结算，不是赊销：只有它增长时不报。"""
        rows = support.annual_rows(3, revenue=100e8, ar=0.0,
                                   receivable_fin=[1e8, 1e8, 40e8])
        self.assertEqual(checks_by_key(rows)["ar_gap"]["status"], "unknown")


class InventoryGapTest(unittest.TestCase):
    """6 存货增速差。"""

    def test_clear_by_default(self):
        self.assertEqual(checks_by_key(support.annual_rows(3))["inventory_gap"]["status"], "clear")

    def test_watch_between_fifteen_and_thirty(self):
        rows = support.annual_rows(3, revenue=100e8, inventory=[6e8, 6e8, 7.2e8])
        c = checks_by_key(rows)["inventory_gap"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("+20.0pct", c["detail"])

    def test_hit_above_thirty_points(self):
        rows = support.annual_rows(3, revenue=100e8, inventory=[6e8, 6e8, 8.4e8])
        self.assertEqual(checks_by_key(rows)["inventory_gap"]["status"], "hit")

    def test_hit_when_two_years_over_fifteen(self):
        rows = support.annual_rows(3, revenue=100e8, inventory=[5e8, 6e8, 7.2e8])
        c = checks_by_key(rows)["inventory_gap"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("连续两年", c["detail"])

    def test_unknown_when_inventory_too_small(self):
        rows = support.annual_rows(3, revenue=100e8, inventory=[0.5e8, 0.5e8, 0.8e8])
        c = checks_by_key(rows)["inventory_gap"]
        self.assertEqual(c["status"], "unknown")
        self.assertIn("占比过小", c["detail"])


class CashflowPatternTest(unittest.TestCase):
    """7 三流组合。"""

    def test_clear_for_healthy_pattern(self):
        c = checks_by_key(support.annual_rows(3))["cashflow_pattern"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("+--", c["detail"])

    def test_hit_when_living_on_financing(self):
        rows = support.annual_rows(3, ocf=-1e8, icf=1e8, fcf_fin=2e8)
        c = checks_by_key(rows)["cashflow_pattern"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("靠输血续命", c["detail"])
        self.assertTrue(c["detail"].count("-++"))

    def test_watch_when_investing_cashflow_positive(self):
        rows = support.annual_rows(3, ocf=5e8, icf=1e8, fcf_fin=-2e8)
        c = checks_by_key(rows)["cashflow_pattern"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("理财", c["detail"])

    def test_unknown_when_field_missing(self):
        rows = support.annual_rows(3, icf=None)
        self.assertEqual(checks_by_key(rows)["cashflow_pattern"]["status"], "unknown")


class ConstructionTest(unittest.TestCase):
    """8 在建工程/固定资产。"""

    def test_clear_when_flat(self):
        self.assertEqual(checks_by_key(support.annual_rows(3))["construction"]["status"], "clear")

    def test_watch_and_tag_when_rising_without_new_debt(self):
        rows = support.annual_rows(3, construction=[1e8, 2e8, 4e8], debt=10e8)
        c = checks_by_key(rows)["construction"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("自有资金扩产", c["detail"])
        self.assertIn("有息负债未增", c["detail"])
        self.assertEqual(c["tag"], "自有资金扩产")

    def test_watch_and_tag_when_funded_by_debt(self):
        rows = support.annual_rows(3, construction=[1e8, 2e8, 4e8], debt=[10e8, 12e8, 16e8])
        c = checks_by_key(rows)["construction"]
        self.assertEqual(c["tag"], "借钱扩产")
        self.assertIn("借钱扩产", c["detail"])
        self.assertIn("同期有息负债增加", c["detail"])

    def test_unknown_without_construction_field(self):
        rows = support.annual_rows(3, construction=None)
        self.assertEqual(checks_by_key(rows)["construction"]["status"], "unknown")


class PerShareTest(unittest.TestCase):
    """9 每股口径：股本扩张 且 每股营收/每股 OCF 未增。"""

    def test_clear_when_shares_flat(self):
        c = checks_by_key(support.annual_rows(4))["per_share"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("股本未扩张", c["detail"])

    def test_hit_when_shares_up_but_per_share_falls(self):
        rows = support.annual_rows(4, shares=[10e8, 10e8, 10e8, 14.4e8], revenue=100e8)
        c = checks_by_key(rows)["per_share"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("+44.0%", c["detail"])

    def test_clear_when_shares_and_per_share_both_grow(self):
        rows = support.annual_rows(4, shares=[10e8, 10e8, 10e8, 14.4e8],
                                   revenue=[100e8, 110e8, 120e8, 150e8],
                                   ocf=[14e8, 15.4e8, 16.8e8, 21e8])
        c = checks_by_key(rows)["per_share"]
        self.assertEqual(c["status"], "clear")

    def test_unknown_without_shares(self):
        self.assertEqual(checks_by_key(support.annual_rows(3, shares=None))["per_share"]["status"],
                         "unknown")


# ---------------------------------------------------------------- 安全
class CashDebtTest(unittest.TestCase):
    """10 现金短债比（+ 速动比率，记分不否决）。"""

    def test_clear_without_short_debt(self):
        c = checks_by_key(support.annual_rows(3))["cash_debt"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("无短期有息负债", c["detail"])

    def test_hit_below_half(self):
        rows = support.annual_rows(3, cash=4.46e8, short_loan=41e8)
        c = checks_by_key(rows)["cash_debt"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("0.11", c["detail"])

    def test_watch_between_half_and_one(self):
        rows = support.annual_rows(3, cash=5e8, short_loan=6e8)
        self.assertEqual(checks_by_key(rows)["cash_debt"]["status"], "watch")

    def test_calm_wording_above_five(self):
        rows = support.annual_rows(3, cash=100e8, short_loan=1e8)
        c = checks_by_key(rows)["cash_debt"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("无短债压力", c["detail"])
        self.assertNotIn("= 100.00", c["detail"])

    def test_one_year_due_debt_counts_in_denominator(self):
        rows = support.annual_rows(3, cash=10e8, short_loan=None, ncl_1y=12e8)
        self.assertEqual(checks_by_key(rows)["cash_debt"]["status"], "watch")

    def test_quick_ratio_never_vetoes(self):
        rows = support.annual_rows(3, cash=100e8, short_loan=1e8, quick_ratio=0.5)
        c = checks_by_key(rows)["cash_debt"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("记 1 分", c["detail"])

    def test_unknown_without_balance_sheet(self):
        self.assertEqual(checks_by_key([])["cash_debt"]["status"], "unknown")


class LeverageCheckTest(unittest.TestCase):
    def test_clear_for_net_cash_company(self):
        c = checks_by_key(support.annual_rows(3, debt=10e8, cash=20e8, ebit=16e8))["leverage"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("-0.62", c["detail"])

    def test_hit_above_three_times_ebit(self):
        c = checks_by_key(support.annual_rows(3, debt=60e8, cash=10e8, ebit=16e8))["leverage"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("3.12", c["detail"])

    def test_detail_shows_debt_trend(self):
        rows = support.annual_rows(3, debt=[10e8, 12e8, 15e8])
        c = checks_by_key(rows)["leverage"]
        self.assertIn("有息负债", c["detail"])
        self.assertIn("+50.0%", c["detail"])

    def test_unknown_when_debt_missing(self):
        c = checks_by_key(support.annual_rows(3, debt=None))["leverage"]
        self.assertEqual(c["status"], "unknown")
        self.assertIn("字段不足", c["detail"])


class InterestCheckTest(unittest.TestCase):
    def test_net_interest_income_is_clear(self):
        c = checks_by_key(support.annual_rows(3, finance_expense=-1e8))["interest"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("净利息收入", c["detail"])

    def test_hit_below_three_times(self):
        c = checks_by_key(support.annual_rows(3, ebit=10e8, finance_expense=5e8))["interest"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("2.0x", c["detail"])

    def test_gross_profit_cover_can_trigger_hit(self):
        """EBIT 覆盖够、但毛利额/利息 <3 → 仍然命中（手册口径：为银行打工）。"""
        rows = support.annual_rows(3, ebit=30e8, finance_expense=8e8, gross_margin=10.0)
        c = checks_by_key(rows)["interest"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("毛利额/利息", c["detail"])
        self.assertIn("为银行打工", c["detail"])

    def test_unknown_when_expense_missing(self):
        self.assertEqual(
            checks_by_key(support.annual_rows(3, finance_expense=None))["interest"]["status"],
            "unknown")


class GoodwillCheckTest(unittest.TestCase):
    def test_hit_above_thirty_percent(self):
        c = checks_by_key(support.annual_rows(3, equity=100e8, goodwill=35e8))["goodwill"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("35.0%", c["detail"])

    def test_watch_between_twenty_and_thirty(self):
        c = checks_by_key(support.annual_rows(3, equity=100e8, goodwill=25e8))["goodwill"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("25.0%", c["detail"])

    def test_imputed_zero_is_clear_with_reminder(self):
        rows = support.annual_rows(3, goodwill=0.0, goodwill_imputed=True)
        c = checks_by_key(rows)["goodwill"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("建议核对年报", c["detail"])

    def test_null_goodwill_field_stays_unknown(self):
        rows = support.annual_rows(3, goodwill=None, goodwill_imputed=False)
        self.assertEqual(checks_by_key(rows)["goodwill"]["status"], "unknown")

    def test_unknown_when_equity_zero(self):
        self.assertEqual(
            checks_by_key(support.annual_rows(3, equity=0))["goodwill"]["status"], "unknown")


class OtherReceivableTest(unittest.TestCase):
    """11 其他应收款/总资产（资金占用）。"""

    def test_clear_by_default(self):
        c = checks_by_key(support.annual_rows(3))["other_receivable"]
        self.assertEqual(c["status"], "clear")
        self.assertIn("0.25%", c["detail"])

    def test_watch_above_two_percent(self):
        rows = support.annual_rows(3, other_ar=6e8, total_assets=200e8)
        c = checks_by_key(rows)["other_receivable"]
        self.assertEqual(c["status"], "watch")
        self.assertIn("3.00%", c["detail"])

    def test_hit_when_other_payable_also_grows(self):
        rows = support.annual_rows(3, other_ar=6e8, total_assets=200e8,
                                   other_ap=[1e8, 1e8, 1.6e8])
        c = checks_by_key(rows)["other_receivable"]
        self.assertEqual(c["status"], "hit")
        self.assertIn("体外循环", c["detail"])

    def test_unknown_without_field(self):
        self.assertEqual(checks_by_key(support.annual_rows(3, other_ar=None))["other_receivable"]["status"],
                         "unknown")


# ---------------------------------------------------------------- 结构与组合
class RiskChecksContractTest(unittest.TestCase):
    def test_fourteen_checks_in_fixed_order(self):
        checks = _risk_checks(support.with_annual(support.annual_rows(5)))
        self.assertEqual([c["key"] for c in checks], CHECK_KEYS)
        for c in checks:
            self.assertIn(c["status"], {"hit", "watch", "clear", "unknown", "na"})
            self.assertIn(c["severity"], {"高", "中"})
            self.assertIn(c["group"], config.RISK_GROUPS)
            self.assertTrue(c["name"])
            self.assertTrue(c["detail"])

    def test_group_counts_match_config(self):
        checks = _risk_checks(support.with_annual(support.annual_rows(5)))
        self.assertEqual(len(checks), config.RISK_CHECK_COUNT)
        for group in config.RISK_GROUPS:
            self.assertTrue([c for c in checks if c["group"] == group])

    def test_empty_data_all_unknown(self):
        checks = _risk_checks(support.with_annual([]))
        self.assertEqual(len(checks), config.RISK_CHECK_COUNT)
        self.assertTrue(all(c["status"] == "unknown" for c in checks),
                        [c["key"] for c in checks if c["status"] != "unknown"])

    def test_financial_stock_marks_inapplicable(self):
        data = support.with_annual(support.annual_rows(5))
        data["meta"] = {"industry": "银行"}
        checks = {c["key"]: c for c in _risk_checks(data)}
        for key in config.FINANCIAL_INAPPLICABLE_CHECKS:
            self.assertEqual(checks[key]["status"], "na", key)
        self.assertEqual(checks["cash_flow"]["status"], "clear")   # 非口径类仍然照常判定

    def test_financial_leverage_detail_hides_unusable_debt_size(self):
        data = support.with_annual(support.annual_rows(5, ebit=None))
        data["meta"] = {"industry": "银行"}
        checks = {c["key"]: c for c in _risk_checks(data)}
        self.assertEqual(checks["leverage"]["status"], "unknown")
        self.assertIn("金融股不适用本口径", checks["leverage"]["detail"])
        self.assertNotIn("亿 →", checks["leverage"]["detail"])


class PatternSummaryTest(unittest.TestCase):
    """组合定性：单一指标不足以定性。"""

    def _summary(self, **overrides):
        rows = support.annual_rows(5, **overrides)
        return _pattern_summary(_risk_checks(support.with_annual(rows)))

    def test_no_flags_returns_empty(self):
        self.assertEqual(self._summary(), "")

    def test_pledging_pattern(self):
        rows = support.annual_rows(5, revenue=100e8, ar=[5e8, 6e8, 8e8, 10e8, 13e8],
                                   ocf=2e8, net_profit=12e8)
        s = _pattern_summary(_risk_checks(support.with_annual(rows)))
        self.assertIn("赊销冲量", s)

    def test_short_debt_plus_leverage(self):
        rows = support.annual_rows(5, cash=4e8, short_loan=20e8, debt=60e8, ebit=10e8)
        s = _pattern_summary(_risk_checks(support.with_annual(rows)))
        self.assertIn("借钱垫资", s)

    def test_dilution_pattern(self):
        rows = support.annual_rows(5, shares=[10e8, 10e8, 10e8, 10e8, 16e8])
        s = _pattern_summary(_risk_checks(support.with_annual(rows)))
        self.assertIn("摊薄", s)


class FatalTest(unittest.TestCase):
    def _fatal(self, rows):
        return _fatal(support.with_annual(rows), _risk_checks(support.with_annual(rows)))

    def test_negative_equity(self):
        self.assertIn("净资产为负", self._fatal(support.annual_rows(3, equity=-1e8)))

    def test_interest_cover_below_one(self):
        rows = support.annual_rows(3, ebit=4e8, finance_expense=5e8)
        self.assertIn("利息保障 < 1", self._fatal(rows))

    def test_goodwill_over_half_of_equity(self):
        rows = support.annual_rows(3, equity=100e8, goodwill=60e8)
        self.assertIn("商誉/净资产超过 50%", self._fatal(rows))

    def test_negative_cashflow_with_high_leverage(self):
        rows = support.annual_rows(5, ocf=[-1e8, -1e8, -1e8, -1e8, -1e8],
                                   debt=100e8, cash=10e8, ebit=16e8)
        self.assertIn("连续 3 年经营现金流为负且净负债/EBIT > 4", self._fatal(rows))

    def test_two_year_history_cannot_claim_three_negative_years(self):
        """只有 2 个年报时不能说「连续 3 年」（P2-3）。"""
        rows = support.annual_rows(2, ocf=[-1e8, -1e8], debt=100e8, cash=10e8, ebit=16e8)
        self.assertEqual(self._fatal(rows), [])

    def test_missing_year_breaks_the_three_year_chain(self):
        """最近三年里有一年 OCF 缺失 → 不能声称连续 3 年。"""
        rows = support.annual_rows(5, ocf=[-1e8, -1e8, -1e8, None, -1e8],
                                   debt=100e8, cash=10e8, ebit=16e8)
        self.assertEqual(self._fatal(rows), [])

    def test_healthy_company_has_no_fatal(self):
        self.assertEqual(self._fatal(support.annual_rows(5)), [])

    def test_missing_cashflow_does_not_trigger_fatal(self):
        # ocf 缺失被当作 0，0 < 0 不成立，因此不误杀
        rows = support.annual_rows(5, ocf=None, debt=100e8, cash=10e8, ebit=16e8)
        self.assertEqual(self._fatal(rows), [])

    def test_new_checks_never_add_fatal(self):
        """现金短债比/净现比命中只点名，不升级为致命。"""
        rows = support.annual_rows(5, cash=1e8, short_loan=50e8, ocf=1e8, net_profit=12e8)
        checks = _risk_checks(support.with_annual(rows))
        self.assertEqual({c["key"]: c["status"] for c in checks}["cash_debt"], "hit")
        self.assertEqual(self._fatal(rows), [])


class DataQualityTest(unittest.TestCase):
    def _dq(self, *, coverage=4, q_coverage=100.0, checks=None):
        data = {"forecast": {"coverage": coverage}}
        q = {"coverage": q_coverage}
        if checks is None:
            checks = [{"key": "leverage", "name": "杠杆", "status": "clear"}] * 14
        return _data_quality(data, q, checks)

    def test_all_good_no_blockers(self):
        dq = self._dq()
        self.assertEqual(dq["buy_blockers"], [])
        self.assertEqual(dq["risk_total"], 14)
        self.assertEqual(dq["risk_known"], 14)
        self.assertEqual(dq["institution_coverage"], 4)

    def test_few_institutions_block(self):
        dq = self._dq(coverage=2)
        self.assertTrue(any("机构覆盖 2 家" in b for b in dq["buy_blockers"]))

    def test_low_quality_coverage_blocks(self):
        dq = self._dq(q_coverage=79.9)
        self.assertTrue(any("Q 数据覆盖" in b for b in dq["buy_blockers"]))

    def test_critical_unknown_blocks_with_chinese_names(self):
        checks = [{"key": "cash_flow", "name": "现金流质量", "status": "unknown"},
                  {"key": "goodwill", "name": "商誉", "status": "unknown"},
                  {"key": "construction", "name": "在建工程", "status": "unknown"}]
        dq = self._dq(checks=checks)
        self.assertEqual(dq["critical_unknown"], ["现金流质量", "商誉"])
        blockers = " ".join(dq["buy_blockers"])
        self.assertIn("现金流质量", blockers)
        self.assertNotIn("在建工程", blockers)   # 非关键检查不阻断

    def test_counts_unknown(self):
        checks = [{"key": "construction", "name": "在建工程", "status": "unknown"}] * 3 + \
                 [{"key": "leverage", "name": "杠杆", "status": "clear"}] * 7
        dq = self._dq(checks=checks)
        self.assertEqual(dq["risk_unknown"], 3)
        self.assertEqual(dq["risk_known"], 7)

    def test_na_is_neither_known_nor_unknown(self):
        checks = [{"key": "cash_debt", "name": "现金短债比", "status": "na"}] * 5 + \
                 [{"key": "leverage", "name": "杠杆", "status": "clear"}] * 9
        dq = self._dq(checks=checks)
        self.assertEqual(dq["risk_na"], 5)
        self.assertEqual(dq["risk_known"], 9)
        self.assertEqual(dq["risk_unknown"], 0)


class DecisionTest(unittest.TestCase):
    def _decide(self, q, v, *, fatal=(), blockers=()):
        return _decision({"score": q}, {"score": v}, list(fatal),
                         {"buy_blockers": list(blockers)})

    def test_fatal_beats_everything(self):
        d = self._decide(100, 100, fatal=["净资产为负"])
        self.assertEqual(d["key"], "avoid")
        self.assertIn("致命风险", d["reason"])

    def test_missing_scores_are_unknown(self):
        self.assertEqual(self._decide(None, 80)["key"], "unknown")
        self.assertEqual(self._decide(80, None)["key"], "unknown")

    def test_hard_floor_blocks_any_valuation(self):
        d = self._decide(44.9, 100)
        self.assertEqual(d["key"], "avoid")
        self.assertIn("禁止买入", d["reason"])

    def test_top_quality_bands(self):
        self.assertEqual(self._decide(75, 65)["key"], "buy")
        self.assertEqual(self._decide(75, 64.9), {"key": "watch_price",
                                                  "label": "好公司，等价格",
                                                  "reason": "质量通过，估值尚未到舒服区间"})
        self.assertEqual(self._decide(85, 50)["key"], "watch_price")
        self.assertEqual(self._decide(75, 49.9)["key"], "expensive")
        self.assertIn("偏贵", self._decide(75, 35)["label"])
        self.assertIn("太贵", self._decide(75, 34.9)["label"])

    def test_medium_high_bands(self):
        self.assertEqual(self._decide(70, 80)["key"], "buy")
        self.assertEqual(self._decide(70, 79.9)["key"], "buy_ok")
        self.assertEqual(self._decide(70, 70)["key"], "buy_ok")
        self.assertEqual(self._decide(70, 69.9)["key"], "watch")
        self.assertEqual(self._decide(70, 49.9)["key"], "avoid")

    def test_medium_bands(self):
        self.assertEqual(self._decide(60, 75)["key"], "buy_small")
        self.assertEqual(self._decide(60, 74.9)["key"], "watch")
        self.assertEqual(self._decide(60, 49.9)["key"], "avoid")

    def test_weak_bands(self):
        self.assertEqual(self._decide(50, 80)["key"], "buy_trial")
        self.assertEqual(self._decide(50, 79.9)["key"], "watch")
        self.assertEqual(self._decide(50, 64.9)["key"], "avoid")

    def test_blockers_downgrade_buy_to_watch(self):
        d = self._decide(80, 70, blockers=["机构覆盖 1 家（少于 3 家）"])
        self.assertEqual(d["key"], "watch")
        self.assertEqual(d["label"], "观察，等待数据完整")
        self.assertIn("机构覆盖", d["reason"])

    def test_blockers_do_not_change_avoid_or_expensive(self):
        self.assertEqual(self._decide(44, 90, blockers=["Q 数据覆盖 50%"])["key"], "avoid")
        self.assertEqual(self._decide(75, 40, blockers=["Q 数据覆盖 50%"])["key"], "expensive")
        self.assertEqual(self._decide(80, 55, blockers=["Q 数据覆盖 50%"])["key"], "watch_price")


class ForecastGrowthBaseTest(unittest.TestCase):
    """预期增速的兜底 CAGR 必须从最近年报起算（annual 是降序，取 annual[0]）。"""

    def _data(self, latest_np: float = 80e8):
        return {
            "meta": {"price": 10.0, "pe": 20.0},
            "forecast": {
                "target_price": 12.0,
                "forecasts": [
                    {"year": 2026, "pe": 18.0, "net_profit_yoy": None, "net_profit_yi": None},
                    {"year": 2027, "pe": 16.0, "net_profit_yoy": None, "net_profit_yi": None},
                    {"year": 2028, "pe": 15.0, "net_profit_yoy": None, "net_profit_yi": 100.0},
                ],
            },
            "financials": {"annual": [
                {"year": 2025, "net_profit": latest_np},   # 最新在前
                {"year": 2024, "net_profit": 70e8},
                {"year": 2023, "net_profit": 60e8},
            ]},
        }

    def test_cagr_starts_from_latest_annual(self):
        m = _forecast_metrics(self._data())
        # (100 / 80) ** (1/3) - 1 = 7.72%，不是从 2023 的 60 亿起算的 10.76%
        self.assertAlmostEqual(m["growth"], 7.72, places=2)
        self.assertEqual(m["growth_count"], 3)

    def test_loss_in_latest_year_blocks_growth_even_if_earlier_profitable(self):
        m = _forecast_metrics(self._data(latest_np=-5e8))
        self.assertIsNone(m["growth"])
        self.assertIn("最近年报亏损", m["growth_reason"])


class RiskGateTest(unittest.TestCase):
    """一致性闸门（0.9.0）：第二节的命中/提示必须能压掉买入类结论。"""

    NAMES = {"cash_flow": "现金流质量", "cash_debt": "现金短债比",
             "per_share": "每股口径", "goodwill": "商誉"}

    def _decide(self, q, v, *, hits=(), watches=(), blockers=()):
        def make(keys, status):
            return [{"key": k, "name": self.NAMES.get(k, k), "status": status} for k in keys]

        checks = make(list(hits), "hit") + make(list(watches), "watch")
        return _decision({"score": q}, {"score": v}, [],
                         {"buy_blockers": list(blockers)}, {"checks": checks})

    # ---- 不触发
    def test_clean_second_section_keeps_buy(self):
        d = self._decide(80, 70, watches=["per_share"])
        self.assertEqual(d["key"], "buy")
        self.assertNotIn("note", d)

    def test_single_non_headline_hit_degrades_to_watch(self):
        d = self._decide(80, 70, hits=["per_share"])
        self.assertEqual(d["key"], "watch")
        self.assertEqual(d["label"], "观察，第二节有信号")
        self.assertIn("第二节命中 1 项", d["reason"])
        self.assertIn("降级为观察", d["note"])

    def test_two_watches_degrade_to_watch(self):
        d = self._decide(80, 70, watches=["per_share", "goodwill"])
        self.assertEqual(d["key"], "watch")
        self.assertIn("提示 2 项", d["reason"])

    def test_single_watch_keeps_buy(self):
        self.assertEqual(self._decide(80, 70, watches=["per_share"])["key"], "buy")

    # ---- 降为回避
    def test_two_hits_degrade_to_avoid(self):
        d = self._decide(80, 70, hits=["per_share", "goodwill"])
        self.assertEqual(d["key"], "avoid")
        self.assertIn("命中 2 项", d["reason"])
        self.assertIn("降级为回避", d["note"])

    def test_headline_hit_alone_vetoes_buy(self):
        d = self._decide(80, 70, hits=["cash_flow"])
        self.assertEqual(d["key"], "avoid")
        self.assertIn("一票否决位", d["reason"])
        self.assertIn("现金流质量", d["reason"])

    def test_cash_debt_headline_also_vetoes(self):
        self.assertEqual(self._decide(80, 70, hits=["cash_debt"])["key"], "avoid")

    # ---- 只动买入方向
    def test_expensive_is_not_softened(self):
        d = self._decide(80, 30, hits=["cash_flow", "per_share"], watches=["goodwill"])
        self.assertEqual(d["key"], "expensive")

    def test_matrix_avoid_is_untouched(self):
        d = self._decide(70, 40, hits=["cash_flow"])
        self.assertEqual(d["key"], "avoid")
        self.assertIn("估值不便宜", d["reason"])

    def test_watch_price_is_untouched(self):
        d = self._decide(80, 50, hits=["cash_flow"])
        self.assertEqual(d["key"], "watch_price")

    def test_hard_floor_still_wins(self):
        d = self._decide(44, 90, hits=["cash_flow"])
        self.assertEqual(d["key"], "avoid")
        self.assertIn("禁止买入", d["reason"])

    # ---- 与数据完整性规则共存
    def test_blockers_still_handle_missing_data(self):
        d = self._decide(80, 70, blockers=["机构覆盖 1 家（少于 3 家）"])
        self.assertEqual(d["label"], "观察，等待数据完整")
        self.assertIn("机构覆盖", d["reason"])

    def test_gate_reason_wins_over_blockers(self):
        """命中两项要降为回避；不能被“数据不全”的观察盖掉（那是更轻的结论）。"""
        d = self._decide(80, 70, hits=["per_share", "goodwill"], blockers=["机构覆盖 1 家（少于 3 家）"])
        self.assertEqual(d["key"], "avoid")

    def test_watch_degradation_still_reports_blockers_as_watch(self):
        d = self._decide(80, 70, hits=["per_share"], blockers=["机构覆盖 1 家（少于 3 家）"])
        self.assertEqual(d["key"], "watch")
        self.assertIn("第二节", d["reason"])

    def test_unknown_checks_do_not_enter_gate(self):
        checks = [{"key": "goodwill", "name": "商誉", "status": "unknown"}] * 3
        d = _decision({"score": 80}, {"score": 70}, [], {"buy_blockers": []}, {"checks": checks})
        self.assertEqual(d["key"], "buy")

    def test_risks_argument_is_optional(self):
        """老调用方（4 参数）不受影响：拿不到第二节就不加闸门。"""
        self.assertEqual(_decision({"score": 80}, {"score": 70}, [], {"buy_blockers": []})["key"], "buy")


if __name__ == "__main__":
    unittest.main()
