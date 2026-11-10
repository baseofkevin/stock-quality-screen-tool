# -*- coding: utf-8 -*-
"""接口 JSON → 计算用数据：字段映射、FCF、市值、分位、机构预期、主营、现金底线。

DCF 已在 0.7.7 移除，本文件末尾保留回归守卫，防止它被重新引入。
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


import config
import support
from screen import compute
from screen.compute import (_cash_valuation, _close_price, _forecast, _mainop,
                            _margin_trend, _period_record, _valuation,
                            _valuation_chart, _years_before, build_financials,
                            market_cap_yi)

CODE = "sh600519"


# ---- 构造 interface 片段 --------------------------------------------------

def income_row(date, *, revenue=100e8, net_profit=12e8, net_margin=12.0,
               deducted=11.5e8, gross=40.0, roe=15.0, roic=12.0,
               ebit=16e8, finance_expense=1e8):
    return {
        "EndDate": date,
        "OperatingRevenue": revenue,
        "NPParentCompanyOwners": net_profit,
        "NetProfitRatio": net_margin,
        "NPDeductNonRecurringPL": deducted,
        "GrossIncomeRatio": gross,
        "ROEWeighted": roe,
        "ROIC": roic,
        "EBIT": ebit,
        "FinancialExpense": finance_expense,
    }


def balance_row(date, *, equity=80e8, debt=10e8, cash=20e8, total_assets=200e8,
                shares=10e8, goodwill=None, current_ratio=2.0, quick_ratio=1.5,
                ar=5e8, inventory=6e8, ebit=None):
    row = {
        "EndDate": date,
        "SEWithoutMI": equity,
        "TotalShareholderEquity": equity + 5e8,
        "InterestBearDebt": debt,
        "CashEquivalents": cash,
        "TotalAssets": total_assets,
        "CurrentRatio": current_ratio,
        "QuickRatio": quick_ratio,
        "PaidInCapital": shares,
        "BillAccReceivable": ar,
        "Inventories": inventory,
    }
    if goodwill is not None:
        row["GoodWill"] = goodwill
    if ebit is not None:
        row["EBIT"] = ebit
    return row


def cashflow_row(date, *, ocf=14e8):
    return {"EndDate": date, "NetOperateCashFlow": ocf}


def finance_call(income=(), balance=(), cashflow=()):
    return {"tool": "data_finance", "response": {"data": {CODE: {
        "income": list(income), "balance": list(balance), "cashflow": list(cashflow)}}}}


def capex_call(rows):
    return {"tool": "RPT_F10_FINANCE_GCASHFLOW",
            "response": {"result": {"data": list(rows)}}}


def value_call(rows, tool="RPT_VALUEANALYSIS_DET"):
    return {"tool": tool, "response": {"result": {"data": list(rows)}}}


def payload_call(tool, payload):
    return {"tool": tool, "response": {"data": {CODE: payload}}}


class PeriodRecordTest(unittest.TestCase):
    """单期记录：每个计算键取哪个接口字段。"""

    def test_maps_core_fields(self):
        parts = {
            "income": income_row("2025-12-31"),
            "balance": balance_row("2025-12-31", goodwill=5e8),
            "cashflow": cashflow_row("2025-12-31"),
        }
        rec = _period_record("2025-12-31", parts, {2025: 2e8})
        self.assertEqual(rec["year"], 2025)
        self.assertAlmostEqual(rec["revenue"], 100e8)
        self.assertAlmostEqual(rec["net_profit"], 12e8)
        self.assertAlmostEqual(rec["net_profit_total"], 12e8)  # 100e8 × 12%
        self.assertAlmostEqual(rec["fcf"], 12e8)               # 14e8 − 2e8
        self.assertAlmostEqual(rec["fcf_margin"], 0.12)
        self.assertAlmostEqual(rec["equity"], 80e8)
        self.assertAlmostEqual(rec["goodwill"], 5e8)
        self.assertFalse(rec["goodwill_imputed"])

    def test_falls_back_to_alternate_field_names(self):
        parts = {
            "income": {"EndDate": "2025-12-31",
                       "TotalOperatingRevenue": 90e8,
                       "NPParentCompanyOwnersTTM": 9e8},
            "balance": balance_row("2025-12-31"),
            "cashflow": {"EndDate": "2025-12-31", "NetOperateCashFlowTTM": 11e8},
        }
        rec = _period_record("2025-12-31", parts, {})
        self.assertAlmostEqual(rec["revenue"], 90e8)
        self.assertAlmostEqual(rec["net_profit"], 9e8)
        self.assertAlmostEqual(rec["ocf"], 11e8)

    def test_ebit_can_come_from_income(self):
        parts = {"income": income_row("2025-12-31", ebit=18e8), "balance": {}, "cashflow": {}}
        self.assertAlmostEqual(_period_record("2025-12-31", parts, {})["ebit"], 18e8)

    def test_missing_capex_makes_fcf_none(self):
        parts = {"income": income_row("2025-12-31"), "balance": {}, "cashflow": cashflow_row("2025-12-31")}
        rec = _period_record("2025-12-31", parts, {2024: 2e8})
        self.assertIsNone(rec["fcf"])
        self.assertIsNone(rec["fcf_margin"])

    def test_goodwill_missing_field_is_imputed_zero(self):
        parts = {"income": {}, "balance": balance_row("2025-12-31"), "cashflow": {}}
        rec = _period_record("2025-12-31", parts, {})
        self.assertEqual(rec["goodwill"], 0.0)   # 唯一“缺失当 0”的字段
        self.assertTrue(rec["goodwill_imputed"])

    def test_goodwill_present_but_null_stays_none(self):
        parts = {"income": {}, "balance": balance_row("2025-12-31", goodwill=None), "cashflow": {}}
        parts["balance"]["GoodWill"] = None
        rec = _period_record("2025-12-31", parts, {})
        self.assertIsNone(rec["goodwill"])
        self.assertFalse(rec["goodwill_imputed"])


class BuildFinancialsTest(unittest.TestCase):
    def _calls(self):
        income = [income_row("2023-12-31"), income_row("2024-12-31"), income_row("2025-12-31"),
                  income_row("2026-09-30", revenue=80e8, net_profit=10e8)]
        balance = [balance_row("2023-12-31"), balance_row("2024-12-31"), balance_row("2025-12-31"),
                   balance_row("2026-09-30")]
        cashflow = [cashflow_row("2023-12-31"), cashflow_row("2024-12-31"),
                    cashflow_row("2025-12-31"), cashflow_row("2026-09-30", ocf=9e8)]
        return [
            finance_call(income, balance, cashflow),
            capex_call([{"REPORT_DATE": "2025-12-31", "CONSTRUCT_LONG_ASSET": 2e8},
                        {"REPORT_DATE": "2024-12-31", "CONSTRUCT_LONG_ASSET": 3e8}]),
        ]

    def test_annual_window_and_order(self):
        fin = build_financials(self._calls(), CODE)
        self.assertEqual([y["date"] for y in fin["annual"]],
                         ["2025-12-31", "2024-12-31", "2023-12-31"])
        self.assertEqual(fin["capex_years"], [2024, 2025])

    def test_latest_quarter_uses_annual_fcf(self):
        fin = build_financials(self._calls(), CODE)
        self.assertEqual(fin["latest"]["date"], "2026-09-30")
        # 季报 OCF 9e8 − 全年 capex 会失真，统一改成最近年报 FCF
        self.assertAlmostEqual(fin["latest"]["fcf"], 12e8)
        self.assertEqual(fin["latest"]["fcf_basis"], "最近年报")

    def test_annual_fcf_uses_matching_capex_year(self):
        fin = build_financials(self._calls(), CODE)
        by_year = {y["year"]: y for y in fin["annual"]}
        self.assertAlmostEqual(by_year[2025]["fcf"], 12e8)   # 14e8 − 2e8
        self.assertAlmostEqual(by_year[2024]["fcf"], 11e8)   # 14e8 − 3e8
        self.assertIsNone(by_year[2023]["fcf"])              # 没有 capex

    def test_capex_takes_annual_row_not_q1_of_same_year(self):
        """东财 capex 是年初至今累计：同年 Q1/Q3 行不能覆盖年报行。"""
        calls = self._calls()
        calls[1] = capex_call([
            # 接口按日期降序返回：先 Q3、再 Q1，最后 12-31
            {"REPORT_DATE": "2025-09-30", "CONSTRUCT_LONG_ASSET": 1.5e8},
            {"REPORT_DATE": "2025-03-31", "CONSTRUCT_LONG_ASSET": 0.5e8},
            {"REPORT_DATE": "2025-12-31", "CONSTRUCT_LONG_ASSET": 2e8},
            {"REPORT_DATE": "2024-06-30", "CONSTRUCT_LONG_ASSET": 1e8},
            {"REPORT_DATE": "2024-12-31", "CONSTRUCT_LONG_ASSET": 3e8},
        ])
        by_year = {y["year"]: y for y in build_financials(calls, CODE)["annual"]}
        self.assertAlmostEqual(by_year[2025]["capex"], 2e8)
        self.assertAlmostEqual(by_year[2024]["capex"], 3e8)
        self.assertAlmostEqual(by_year[2025]["fcf"], 12e8)   # 14e8 − 2e8，不是 14e8 − 0.5e8
        self.assertAlmostEqual(by_year[2024]["fcf"], 11e8)

    def test_year_without_annual_capex_row_stays_none(self):
        """只有季报行、没有 12-31 行时，宁可 FCF 未知，也不要用 Q1 累计值。"""
        calls = self._calls()
        calls[1] = capex_call([{"REPORT_DATE": "2025-09-30", "CONSTRUCT_LONG_ASSET": 1.5e8}])
        by_year = {y["year"]: y for y in build_financials(calls, CODE)["annual"]}
        self.assertIsNone(by_year[2025]["capex"])
        self.assertIsNone(by_year[2025]["fcf"])

    def test_ttm_fields_are_attached_to_latest(self):
        calls = self._calls()
        calls[0]["response"]["data"][CODE]["income"][-1].update({
            "OperatingRevenueTTM": 130e8, "NPParentCompanyOwnersTTM": 64e8, "EPSTTM": 51.5})
        calls[0]["response"]["data"][CODE]["cashflow"][-1]["NetOperateCashFlowTTM"] = 84e8
        latest = build_financials(calls, CODE)["latest"]
        self.assertAlmostEqual(latest["revenue_ttm"], 130e8)
        self.assertAlmostEqual(latest["net_profit_ttm"], 64e8)
        self.assertAlmostEqual(latest["ocf_ttm"], 84e8)
        self.assertAlmostEqual(latest["eps_ttm"], 51.5)

    def test_empty_finance_call_returns_empty_structures(self):
        fin = build_financials([], CODE)
        self.assertEqual(fin["annual"], [])
        self.assertEqual(fin["latest"], {})
        self.assertEqual(fin["margin_trend"]["count"], 0)


class MarginTrendTest(unittest.TestCase):
    def test_keeps_last_twenty_quarters_and_skips_missing(self):
        # 8 年 × 4 = 32 个季度，默认窗口只留最近 5 年（20 个）
        dates = [f"{y}-{m}-{d}" for y in range(2019, 2027)
                 for m, d in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31"))]
        merged = {d: {"income": {"OperatingRevenue_Q": 100, "OperatingCost_Q": 40,
                                 "NPParentCompanyOwners_Q": 20}} for d in dates}
        trend = _margin_trend(merged)
        self.assertEqual(trend["count"], config.TREND_QUARTERS)
        self.assertEqual(trend["count"], 20)                  # 5 年 = 20 个季度
        self.assertEqual(trend["start"], dates[-20])
        self.assertEqual(trend["points"][-1]["label"], "26Q4")
        self.assertAlmostEqual(trend["points"][-1]["gross"], 60.0)
        self.assertAlmostEqual(trend["points"][-1]["net"], 20.0)

        merged[dates[-1]]["income"].pop("OperatingCost_Q")
        self.assertIsNone(_margin_trend(merged)["points"][-1]["gross"])

    def test_short_history_keeps_whatever_is_available(self):
        dates = ["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"]
        merged = {d: {"income": {"OperatingRevenue_Q": 100, "OperatingCost_Q": 40,
                                 "NPParentCompanyOwners_Q": 20}} for d in dates}
        trend = _margin_trend(merged)
        self.assertEqual(trend["count"], 4)
        self.assertEqual(trend["start"], "2025-12-31")

    def test_quarter_label(self):
        merged = {"2025-09-30": {"income": {"OperatingRevenue_Q": 100, "OperatingCost_Q": 50}}}
        self.assertEqual(_margin_trend(merged)["points"][0]["label"], "25Q3")


class MarketCapTest(unittest.TestCase):
    def test_calibrates_yuan(self):
        yi, yuan = market_cap_yi({"total_market_cap": 1.8279e12, "price": 1462.29,
                                  "total_shares": 1.25e9})
        self.assertAlmostEqual(yuan, 1.8279e12, delta=1)
        self.assertAlmostEqual(yi, 18279.0, delta=1)

    def test_calibrates_wan_yuan(self):
        # 接口按“万元”给：1.8279e7 万元 = 1.8279e11 元
        yi, _ = market_cap_yi({"total_market_cap": 1.8279e7, "price": 100.0,
                               "total_shares": 1.8279e9})
        self.assertAlmostEqual(yi, 1827.9, delta=0.1)

    def test_calibrates_yi_yuan(self):
        # 接口按“亿元”给：1827.9 亿元
        yi, _ = market_cap_yi({"total_market_cap": 1827.9, "price": 100.0,
                               "total_shares": 1.8279e9})
        self.assertAlmostEqual(yi, 1827.9, delta=0.1)

    def test_without_price_falls_back_to_yi_factor(self):
        yi, yuan = market_cap_yi({"total_market_cap": 100.0})
        self.assertAlmostEqual(yi, 100.0)
        self.assertAlmostEqual(yuan, 100e8)

    def test_missing_cap_uses_price_times_shares(self):
        yi, yuan = market_cap_yi({"price": 10.0, "total_shares": 1e9})
        self.assertIsNone(yi)
        self.assertAlmostEqual(yuan, 1e10)


class ClosingBasisTest(unittest.TestCase):
    """全篇估值口径：分位表用序列最后一点，价格用口径日收盘。"""

    def _val(self, pe_last=25.0):
        rows = [
            {"TRADE_DATE": "2024-01-05", "PE_TTM": 20.0, "PB_MRQ": 5.0, "PS_TTM": 4.0},
            {"TRADE_DATE": "2024-01-12", "PE_TTM": pe_last, "PB_MRQ": 5.2, "PS_TTM": 4.2},
        ]
        return _valuation([value_call(rows)])

    def test_current_ignores_realtime_quote(self):
        """行情实时 PE 与序列尾值不同时，以序列（收盘）为准。"""
        val = self._val(pe_last=25.0)
        self.assertAlmostEqual(val["metrics"]["pe"]["current"], 25.0)
        self.assertAlmostEqual(val["metrics"]["pb"]["current"], 5.2)

    def test_percentile_uses_close_basis(self):
        val = self._val(pe_last=25.0)
        # 样本 [20, 25]，当前取 25 → 小于 25 的 1 个、等于 1 个 → (1+0.5)/2
        self.assertAlmostEqual(val["metrics"]["pe"]["percentile"], 75.0, places=1)

    def test_close_price_same_day_uses_quote(self):
        val = self._val()
        price, basis = _close_price(
            val, {"time": "2024-01-12", "price": 100.0, "prev_close": 99.0},
            {"latest": {"eps_ttm": 4.0}})
        self.assertAlmostEqual(price, 100.0)
        self.assertEqual(basis, "2024-01-12 收盘")

    def test_close_price_uses_prev_close_when_quote_is_next_day(self):
        """盘中运行：行情日在口径日之后，prev_close 就是口径日收盘。"""
        val = self._val()
        price, basis = _close_price(
            val, {"time": "2024-01-15", "price": 103.0, "prev_close": 100.5},
            {"latest": {"eps_ttm": 4.1}})          # PE 25 × 4.1 = 102.5，与 100.5 差 2%，信任 prev_close
        self.assertAlmostEqual(price, 100.5)
        self.assertTrue(basis.endswith("收盘"))

    def test_close_price_derives_when_prev_close_far_off(self):
        """prev_close 与 PE×EPS 差 5% 以上，通常是除权/错位，改用与图同源的反推值。"""
        val = self._val()
        price, basis = _close_price(
            val, {"time": "2024-01-15", "price": 103.0, "prev_close": 90.0},
            {"latest": {"eps_ttm": 4.0}})          # 25 × 4 = 100 → 与 90 差 11%
        self.assertAlmostEqual(price, 100.0)
        self.assertIn("反推", basis)

    def test_close_price_falls_back_to_derived_without_prev_close(self):
        val = self._val()
        price, basis = _close_price(val, {"time": "2024-01-15", "price": 103.0},
                                    {"latest": {"eps_ttm": 4.0}})
        self.assertAlmostEqual(price, 100.0)
        self.assertIn("反推", basis)

    def test_close_price_falls_back_to_live_price_last(self):
        price, basis = _close_price({"sample": {}, "metrics": {}},
                                    {"time": "2024-01-15", "price": 88.0}, {"latest": {}})
        self.assertAlmostEqual(price, 88.0)
        self.assertEqual(basis, "实时价")

    def test_market_cap_recomputed_from_close(self):
        yi, yuan = market_cap_yi({"total_market_cap": 1.0e11, "price": 90.0,
                                  "total_shares": 1e9}, price=100.0)
        self.assertAlmostEqual(yuan, 1.0e11)
        self.assertAlmostEqual(yi, 1000.0)

    def test_market_cap_without_override_keeps_quote_path(self):
        yi, _ = market_cap_yi({"total_market_cap": 1827.9, "price": 100.0,
                               "total_shares": 1.8279e9})
        self.assertAlmostEqual(yi, 1827.9, delta=0.1)


class ValuationSeriesTest(unittest.TestCase):
    def _calls(self):
        rows = [
            {"TRADE_DATE": "2024-01-05", "PE_TTM": 20, "PB_MRQ": 5.0, "PS_TTM": 4.0},
            {"TRADE_DATE": "2024-01-08", "PE_TTM": 30, "PB_MRQ": 5.5, "PS_TTM": 4.5},  # 同周被覆盖
            {"TRADE_DATE": "2024-01-12", "PE_TTM": 15, "PB_MRQ": 5.2, "PS_TTM": 4.2},
            {"TRADE_DATE": "2024-01-19", "PE_TTM": -5, "PB_MRQ": 4.8, "PS_TTM": 3.9},
            {"TRADE_DATE": "2024-01-26", "PE_TTM": 25, "PB_MRQ": 5.1, "PS_TTM": 4.1},
        ]
        return [value_call(rows)]

    def test_weekly_dedupe_and_positive_filter(self):
        val = _valuation(self._calls())
        self.assertTrue(val["available"])
        self.assertEqual(val["sample"]["points"], 4)          # 5 条日频压成 4 周
        self.assertEqual(val["metrics"]["pe"]["points"], 3)   # PE 为负的一周不进分位
        self.assertEqual(val["metrics"]["pe"]["max"], 25)
        self.assertEqual(val["metrics"]["ps"]["points"], 4)

    def test_percentile_uses_midpoint(self):
        val = _valuation(self._calls())
        # PE 样本 [20, 15, 25]：小于 25 的 2 个，等于 25 的 1 个
        self.assertAlmostEqual(val["metrics"]["pe"]["percentile"], 83.3, places=1)
        # PB 样本 [5.0, 5.2, 4.8, 5.1]：小于 5.1 的 2 个，等于 1 个
        self.assertAlmostEqual(val["metrics"]["pb"]["percentile"], 62.5, places=1)

    def test_ps_current_comes_from_series_tail(self):
        val = _valuation(self._calls())
        self.assertAlmostEqual(val["metrics"]["ps"]["current"], 4.1)

    def test_chart_keeps_all_weeks_when_window_off(self):
        val = _valuation(self._calls(), years=0)
        chart = val["chart"]
        self.assertEqual([p["date"] for p in chart["points"]],
                         ["2024-01-05", "2024-01-12", "2024-01-19", "2024-01-26"])
        self.assertEqual(chart["negative_ranges"], [["2024-01-19", "2024-01-19"]])
        self.assertEqual(val["metrics"]["pe"]["points"], 3)  # 分位仍用全历史

    def test_empty_series_is_not_available(self):
        val = _valuation([])
        self.assertFalse(val["available"])
        self.assertEqual(val["metrics"], {})
        self.assertEqual(val["chart"]["points"], [])


class ValuationChartWindowTest(unittest.TestCase):
    """走势图窗口：最近 10 年；不足 10 年按全部可用历史；分位仍用全历史。"""

    def _calls(self, first_year: int = 2014):
        rows = []
        for year in range(first_year, 2027):
            for month, day in ((1, 5), (7, 5)):
                rows.append({"TRADE_DATE": f"{year}-{month:02d}-{day:02d}",
                             "PE_TTM": 20.0, "PB_MRQ": 3.0, "PS_TTM": 2.0})
        return [value_call(rows)]

    def test_window_starts_ten_years_before_last_point(self):
        val = _valuation(self._calls())
        chart = val["chart"]
        self.assertEqual(chart["end"], "2026-07-05")
        self.assertEqual(chart["start"], "2016-07-05")      # 截止日当天保留
        self.assertEqual(chart["years"], config.VALUATION_YEARS)
        self.assertFalse(chart["limited"])
        self.assertEqual(chart["count"], 21)                # 26 个周度点里切掉 2014~2016H1

    def test_percentile_and_sample_still_use_full_history(self):
        val = _valuation(self._calls())
        self.assertEqual(val["metrics"]["pe"]["points"], 26)
        self.assertEqual(val["sample"]["start"], "2014-01-05")
        self.assertEqual(val["chart"]["count"], 21)

    def test_short_history_uses_everything_and_flags_limited(self):
        val = _valuation(self._calls(first_year=2022))
        chart = val["chart"]
        self.assertEqual(chart["start"], "2022-01-05")
        self.assertEqual(chart["count"], 10)                # 5 年 × 2 个半年点
        self.assertTrue(chart["limited"])
        self.assertLess(chart["span_years"], config.VALUATION_YEARS)

    def test_window_off_keeps_every_point(self):
        val = _valuation(self._calls(), years=0)
        self.assertEqual(val["chart"]["count"], 26)
        self.assertFalse(val["chart"]["limited"])

    def test_years_before_edge_cases(self):
        self.assertEqual(_years_before("2026-11-10", 10), "2016-11-10")
        self.assertEqual(_years_before("2024-02-29", 10), "2014-02-28")   # 闰日回退一天
        self.assertEqual(_years_before("", 10), "")                        # 空值 → 不截断
        self.assertEqual(_years_before("not-a-date", 10), "")

    def test_empty_series_keeps_window_meta(self):
        chart = _valuation([])["chart"]
        self.assertEqual(chart["years"], config.VALUATION_YEARS)
        self.assertEqual(chart["span_years"], 0.0)
        self.assertFalse(chart["limited"])


class ValuationChartTest(unittest.TestCase):
    def test_negative_ranges_are_paired(self):
        rows = [
            {"TRADE_DATE": "2024-01-05", "PE_TTM": 20},
            {"TRADE_DATE": "2024-01-12", "PE_TTM": -1},
            {"TRADE_DATE": "2024-01-19", "PE_TTM": -2},
            {"TRADE_DATE": "2024-01-26", "PE_TTM": 25},
            {"TRADE_DATE": "2024-02-02", "PE_TTM": 0},
        ]
        chart = _valuation_chart(rows, "")
        self.assertEqual(chart["negative_ranges"],
                         [["2024-01-12", "2024-01-19"], ["2024-02-02", "2024-02-02"]])
        self.assertEqual(chart["points"][1]["pe"], None)
        self.assertIsNone(chart["latest"]["pe"])
        self.assertTrue(chart["pe_negative_latest"])

    def test_start_filters_old_points(self):
        rows = [{"TRADE_DATE": "2024-01-05", "PE_TTM": 20},
                {"TRADE_DATE": "2024-02-05", "PE_TTM": 21}]
        chart = _valuation_chart(rows, "2024-02-01")
        self.assertEqual(chart["count"], 1)
        self.assertEqual(chart["start"], "2024-02-05")


class ForecastTest(unittest.TestCase):
    def test_units_sorted_and_coverage(self):
        calls = [
            payload_call("data_consensus", {
                "targetPrice": 1700.0,
                "forecasts": [
                    {"year": 2027, "eps": 70, "revenue": 2e6, "netProfit": 9e5,
                     "pe": 20, "pb": 5, "ps": 9, "revenueYoy": 5, "netProfitYoy": 6,
                     "institutionCnt": 0},
                    {"year": 2026, "eps": 66, "revenue": 1.9e6, "netProfit": 8.4e5,
                     "pe": 21, "institutionCnt": 3},
                ],
            }),
            payload_call("data_rating", {"forecastInstitutions": 5, "ratingCnt": 9,
                                         "ratingBuyCnt": 3, "ratingIncCnt": 2}),
        ]
        fc = _forecast(calls, CODE)
        self.assertTrue(fc["available"])
        self.assertAlmostEqual(fc["target_price"], 1700.0)
        self.assertEqual([f["year"] for f in fc["forecasts"]], [2026, 2027])
        self.assertAlmostEqual(fc["forecasts"][0]["revenue_yi"], 190.0)   # 万元 → 亿元
        self.assertAlmostEqual(fc["forecasts"][0]["net_profit_yi"], 84.0)
        self.assertEqual(fc["coverage"], 3)
        self.assertEqual(fc["rating_coverage"], 5)
        self.assertEqual(fc["rating"]["records"], 9)

    def test_coverage_falls_back_to_rating_when_forecast_rows_lack_count(self):
        calls = [
            payload_call("data_consensus", {"targetPrice": 20.0, "forecasts": [
                {"year": 2026, "pe": 15, "institutionCnt": 0}]}),
            payload_call("data_rating", {"forecastInstitutions": 4}),
        ]
        self.assertEqual(_forecast(calls, CODE)["coverage"], 4)

    def test_no_forecast_rows_keeps_coverage_zero(self):
        calls = [payload_call("data_rating", {"forecastInstitutions": 4})]
        fc = _forecast(calls, CODE)
        self.assertFalse(fc["available"])
        self.assertEqual(fc["coverage"], 0)
        self.assertEqual(fc["rating_coverage"], 4)

    def test_target_price_alone_counts_as_available(self):
        calls = [payload_call("data_consensus", {"targetPrice": 20.0, "forecasts": []})]
        self.assertTrue(_forecast(calls, CODE)["available"])


class MainopTest(unittest.TestCase):
    def _calls(self):
        rows = [
            {"REPORT_DATE": "2025-12-31", "MAINOP_TYPE": "1", "ITEM_NAME": "华东",
             "MAIN_BUSINESS_INCOME": 50e8, "MBI_RATIO": 0.5, "MAIN_BUSINESS_COST": 30e8},
            {"REPORT_DATE": "2025-12-31", "MAINOP_TYPE": "2", "ITEM_NAME": "产品A",
             "MAIN_BUSINESS_INCOME": 60e8, "MBI_RATIO": 0.6, "MAIN_BUSINESS_COST": 24e8},
            {"REPORT_DATE": "2025-12-31", "MAINOP_TYPE": "2", "ITEM_NAME": "产品B",
             "MAIN_BUSINESS_INCOME": 40e8},
            {"REPORT_DATE": "2024-12-31", "MAINOP_TYPE": "2", "ITEM_NAME": "旧产品",
             "MAIN_BUSINESS_INCOME": 10e8, "MBI_RATIO": 1.0},
        ]
        return [value_call(rows, "RPT_F10_FN_MAINOP")]

    def test_only_type2_of_target_period(self):
        mainop = _mainop(self._calls(), [{"date": "2025-12-31"}])
        self.assertEqual(mainop["period"], "2025-12-31")
        self.assertEqual([p["name"] for p in mainop["products"]], ["产品A", "产品B"])

    def test_ratio_and_gross_margin(self):
        products = {p["name"]: p for p in
                    _mainop(self._calls(), [{"date": "2025-12-31"}])["products"]}
        self.assertAlmostEqual(products["产品A"]["ratio_pct"], 60.0)
        self.assertAlmostEqual(products["产品A"]["gross_margin"], 60.0)
        self.assertIsNone(products["产品B"]["ratio_pct"])      # 缺 MBI_RATIO
        self.assertIsNone(products["产品B"]["gross_margin"])   # 缺成本

    def test_ratio_recomputed_when_all_missing(self):
        rows = [
            {"REPORT_DATE": "2025-12-31", "MAINOP_TYPE": "2", "ITEM_NAME": "A",
             "MAIN_BUSINESS_INCOME": 75e8},
            {"REPORT_DATE": "2025-12-31", "MAINOP_TYPE": "2", "ITEM_NAME": "B",
             "MAIN_BUSINESS_INCOME": 25e8},
        ]
        products = _mainop([value_call(rows, "RPT_F10_FN_MAINOP")],
                           [{"date": "2025-12-31"}])["products"]
        self.assertAlmostEqual(products[0]["ratio_pct"], 75.0)
        self.assertAlmostEqual(products[1]["ratio_pct"], 25.0)

    def test_empty_rows(self):
        mainop = _mainop([], [])
        self.assertFalse(mainop["available"])
        self.assertEqual(mainop["products"], [])


class DcfRemovedTest(unittest.TestCase):
    """DCF 已下线：函数、数据键、配置项都不该再出现。"""

    def test_function_gone(self):
        self.assertFalse(hasattr(compute, "_dcf"))

    def test_no_dcf_key_in_report_data(self):
        data = support.report_data()
        self.assertNotIn("dcf", data)
        self.assertNotIn("fcf_yield", data["meta"])

    def test_config_keys_gone(self):
        for name in ("DCF_G", "DCF_YEARS", "REQUIRED_FCF_YIELD"):
            self.assertFalse(hasattr(config, name), name)

    def test_no_dcf_in_source(self):
        source = Path(compute.__file__).read_text(encoding="utf-8")
        self.assertNotIn("dcf", source.lower())


class CashValuationUnitTest(unittest.TestCase):
    def test_cash_falls_back_to_annual_when_latest_missing(self):
        annual = [{"date": "2025-12-31", "cash": 2.3e9, "debt": 5e8, "net_profit_total": 5.1e8}]
        cv = _cash_valuation(annual, {"date": "2026-09-30"}, {}, 5e9)
        self.assertAlmostEqual(cv["cash_yi"], 23.0)
        self.assertEqual(cv["cash_period"], "2025-12-31")
        self.assertAlmostEqual(cv["debt_yi"], 5.0)

    def test_per_share_none_without_shares(self):
        annual = [{"date": "2025-12-31", "cash": 1e9, "net_profit_total": 1e8}]
        cv = _cash_valuation(annual, {"date": "2025-12-31", "cash": 1e9}, {}, 1e9)
        self.assertTrue(cv["applicable"])
        self.assertIsNone(cv["anchors"][0]["per_share"])

    def test_missing_market_cap_skips_margin_and_pe(self):
        annual = [{"date": "2025-12-31", "cash": 1e9, "net_profit_total": 2e8}]
        cv = _cash_valuation(annual, {"date": "2025-12-31", "cash": 1e9}, {}, None)
        self.assertTrue(cv["applicable"])
        self.assertIsNone(cv["ex_cash_cap_yi"])
        self.assertIsNone(cv["ex_cash_pe"])
        self.assertIsNone(cv["anchors"][0]["margin_pct"])


if __name__ == "__main__":
    unittest.main()
