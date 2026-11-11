# -*- coding: utf-8 -*-
"""把接口返回整理成计算用数据；不落盘、不生成 JSON 文件。"""
from __future__ import annotations

from datetime import date
from typing import Any

import config
from screen.util import num, year_of

ANNUAL_SUFFIX = "-12-31"


def _response(call: dict[str, Any] | None) -> dict[str, Any]:
    if not call:
        return {}
    resp = call.get("response")
    return resp if isinstance(resp, dict) else {}


def _find_call(calls: list[dict[str, Any]], tool: str) -> dict[str, Any] | None:
    for call in reversed(calls):
        if call.get("tool") == tool:
            return call
    return None


def _data(call: dict[str, Any] | None) -> Any:
    return _response(call).get("data")


def _code_data(payload: Any, code: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if payload.get(code) and isinstance(payload[code], dict):
        return payload[code]
    # data_finance 的外层还有 data/code
    inner = payload.get("data")
    if isinstance(inner, dict):
        if inner.get(code) and isinstance(inner[code], dict):
            return inner[code]
        for value in inner.values():
            if isinstance(value, dict) and ({"balance", "income", "cashflow"} & set(value)):
                return value
    return payload


def _rows(call: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not call:
        return []
    resp = _response(call)
    result = resp.get("result")
    if isinstance(result, dict) and isinstance(result.get("data"), list):
        return [x for x in result["data"] if isinstance(x, dict)]
    data = resp.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _merge_rows(calls: list[dict[str, Any]], tool: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call in calls:
        if call.get("tool") == tool:
            rows.extend(_rows(call))
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("TRADE_DATE") or row.get("REPORT_DATE") or "")
        if key and key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _date(row: dict[str, Any]) -> str:
    raw = str(row.get("EndDate") or row.get("REPORT_DATE") or row.get("date") or "")
    return raw[:10] if len(raw) >= 10 else ""


def _first_num(*values: Any) -> float | None:
    """按顺序取第一个能解析成数值的字段。

    不能用 `num(a) or num(b)`：那样会把合法的 0 当成缺失（归母净利恰为 0 时会误用 TTM）。
    """
    for value in values:
        v = num(value)
        if v is not None:
            return v
    return None


def _annual_dates(dates: list[str]) -> list[str]:
    return sorted([d for d in dates if d.endswith(ANNUAL_SUFFIX)], reverse=True)


def _quarter_label(d: str) -> str:
    try:
        year = d[:4]
        month = int(d[5:7])
        quarter = (month - 1) // 3 + 1
        return f"{year[2:]}Q{quarter}"
    except (ValueError, TypeError):
        return d


def _margin_trend(merged: dict[str, dict[str, dict[str, Any]]],
                  quarters: int = config.TREND_QUARTERS) -> dict[str, Any]:
    """最近 N 个报告期的单季毛利率、归母净利率。

    只用接口已返回的 _Q 字段，不做累计差分；缺失就留空，图上断线。
    """
    dates = sorted(merged)[-quarters:]
    points: list[dict[str, Any]] = []
    for d in dates:
        inc = merged.get(d, {}).get("income", {})
        revenue = num(inc.get("OperatingRevenue_Q"))
        if revenue is None:
            revenue = num(inc.get("TotalOperatingRevenue_Q"))
        cost = num(inc.get("OperatingCost_Q"))
        parent_np = num(inc.get("NPParentCompanyOwners_Q"))
        gross = ((revenue - cost) / revenue * 100.0) if (revenue and cost is not None) else None
        net = (parent_np / revenue * 100.0) if (revenue and parent_np is not None) else None
        points.append({
            "date": d,
            "label": _quarter_label(d),
            "revenue": revenue,
            "gross": gross,
            "net": net,
        })
    return {
        "points": points,
        "count": len(points),
        "start": dates[0] if dates else "",
        "end": dates[-1] if dates else "",
    }


def _period_record(d: str, parts: dict[str, dict[str, Any]], capex: dict[int, float]) -> dict[str, Any]:
    inc = parts.get("income", {})
    bal = parts.get("balance", {})
    cf = parts.get("cashflow", {})
    y = year_of(d)
    revenue = _first_num(inc.get("OperatingRevenue"), inc.get("TotalOperatingRevenue"))
    parent_np = _first_num(inc.get("NPParentCompanyOwners"), inc.get("NPParentCompanyOwnersTTM"))
    net_margin = num(inc.get("NetProfitRatio"))
    total_np = (revenue * net_margin / 100.0) if revenue is not None and net_margin is not None else None
    ocf = _first_num(cf.get("NetOperateCashFlow"), cf.get("NetOperateCashFlowTTM"))
    cx = capex.get(y) if y is not None else None
    fcf = (ocf - cx) if (ocf is not None and cx is not None) else None
    equity = num(bal.get("SEWithoutMI"))
    total_equity = num(bal.get("TotalShareholderEquity"))
    debt = num(bal.get("InterestBearDebt"))
    cash = num(bal.get("CashEquivalents"))
    goodwill = num(bal.get("GoodWill"))
    goodwill_imputed = bool(bal) and "GoodWill" not in bal
    if goodwill is None and goodwill_imputed:
        goodwill = 0.0
    ebit = _first_num(bal.get("EBIT"), inc.get("EBIT"))
    fin_exp = num(inc.get("FinancialExpense"))
    shares = num(bal.get("PaidInCapital"))
    return {
        "date": d,
        "year": y,
        "revenue": revenue,
        "net_profit": parent_np,
        "net_profit_total": total_np,
        "deducted": num(inc.get("NPDeductNonRecurringPL")),
        "gross_margin": num(inc.get("GrossIncomeRatio")),
        "net_margin": net_margin,
        "roe": _first_num(inc.get("ROEWeighted"), inc.get("ROE")),
        "roa": num(inc.get("ROA")),
        "roic": num(inc.get("ROIC")),
        "ocf": ocf,
        "ocf_ttm": num(cf.get("NetOperateCashFlowTTM")),
        "icf": num(cf.get("NetInvestCashFlow")),
        "fcf_fin": num(cf.get("NetFinanceCashFlow")),
        "capex": cx,
        "fcf": fcf,
        "fcf_margin": (fcf / revenue) if (fcf is not None and revenue) else None,
        "total_assets": num(bal.get("TotalAssets")),
        "equity": equity,
        "total_equity": total_equity,
        "debt": debt,
        "cash": cash,
        "goodwill": goodwill,
        "goodwill_imputed": goodwill_imputed,
        "current_ratio": num(bal.get("CurrentRatio")),
        "quick_ratio": num(bal.get("QuickRatio")),
        "working_capital": num(bal.get("WorkingCapital")),
        "ebit": ebit,
        "finance_expense": fin_exp,
        "shares": shares,
        "ar": num(bal.get("BillAccReceivable")),
        # 应收票据在部分公司（如茅台）走「应收款项融资」，单看 BillAccReceivable 会算成零应收。
        "receivable_fin": num(bal.get("ReceivablesFin")),
        "inventory": num(bal.get("Inventories")),
        "payable": num(bal.get("NotAccountsPayable")),
        "other_ar": num(bal.get("OtherReceivableED")),
        "other_ap": num(bal.get("OtherPayableED")),
        "contract_liability": num(bal.get("ContractLiability")),
        "advance_payment": num(bal.get("AdvancePayment")),
        "short_loan": num(bal.get("ShortTermLoan")),
        "ncl_1y": num(bal.get("NonCurrentLiabilityIn1Year")),
        "construction": num(bal.get("TConstruInProcess")),
        "fixed_asset": num(bal.get("TotalFixedAsset")),
        "sell_expense": num(inc.get("OperatingExpense")),
        "admin_expense": num(inc.get("TotalAdminExpense")),
        "rnd_expense": num(inc.get("RAndD")),
        "np_ttm": num(inc.get("NPParentCompanyOwnersTTM")),
    }


def _structure(annual: list[dict[str, Any]], years: int = 5) -> dict[str, Any]:
    """第一节用的结构指标（按年度升序），只做展示，不参与 Q/V 打分。

    - 占款比 = 应付账款 ÷（应收 + 应收款项融资 + 存货）：>1 两头通吃，越小越是自己垫钱。
      手册 6.4 写的是（应收+存货）÷ 应付，但对茅台这种存货是基酒的公司会得出 15 倍假信号，
      所以反过来做分子分母。
    - 合同负债/营收：销售端的预收议价能力，和占款比一起读才有意义。
    - 在建工程/固定资产：连续上升 = 扩产期，2~3 年后折旧压利润。
    """
    rows: list[dict[str, Any]] = []
    for rec in list(reversed(annual))[-years:]:
        ar = (rec.get("ar") or 0.0) + (rec.get("receivable_fin") or 0.0)
        inv = rec.get("inventory") or 0.0
        ap = rec.get("payable")
        revenue = rec.get("revenue")
        cl = (rec.get("contract_liability") or 0.0) + (rec.get("advance_payment") or 0.0)
        cip, fa = rec.get("construction"), rec.get("fixed_asset")
        rows.append({
            "year": rec.get("year"),
            "bargain": (ap / (ar + inv)) if (ap is not None and (ar + inv) > 0) else None,
            "payable": ap,
            "ar_inv": (ar + inv) if (ar or inv) else None,
            "contract_ratio": (cl / revenue * 100.0) if (revenue and cl) else None,
            "contract": cl if cl else None,
            "construction_ratio": (cip / fa * 100.0) if (cip is not None and fa) else None,
            "debt": rec.get("debt"),
        })
    bargain = [r["bargain"] for r in rows if r["bargain"] is not None]
    # 趋势是「最后一个有数据的年 − 第一个有数据的年」，标签必须跟着实际跨度走：
    # 写死「三年」而窗口是 5 年时，读者会拿 5 年的变化当成 3 年的。
    bargain_years = [r["year"] for r in rows if r["bargain"] is not None and r.get("year")]
    if len(bargain_years) >= 2:
        span_years = bargain_years[-1] - bargain_years[0] + 1
    else:
        span_years = len(bargain_years) or None
    cl_ratios = [r["contract_ratio"] for r in rows if r["contract_ratio"] is not None]
    cl_vals = [r["contract"] for r in rows if r["contract"] is not None]
    return {
        "rows": rows,
        "bargain_latest": bargain[-1] if bargain else None,
        "bargain_trend": (bargain[-1] - bargain[0]) if len(bargain) >= 2 else None,
        "bargain_trend_years": span_years,
        "contract_latest": cl_ratios[-1] if cl_ratios else None,
        "contract_yoy": ((cl_vals[-1] / cl_vals[-2] - 1) * 100.0
                         if len(cl_vals) >= 2 and cl_vals[-2] else None),
    }


def build_financials(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    fin_call = _find_call(calls, "data_finance")
    payload = _code_data(_data(fin_call), code)
    sections = payload if isinstance(payload, dict) else {}
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    for section in ("income", "balance", "cashflow"):
        for row in sections.get(section) or []:
            d = _date(row)
            if d:
                merged.setdefault(d, {})[section] = row

    capex: dict[int, float] = {}
    for row in _merge_rows(calls, "RPT_F10_FINANCE_GCASHFLOW"):
        d = str(row.get("REPORT_DATE") or "")[:10]
        y = year_of(d)
        v = num(row.get("CONSTRUCT_LONG_ASSET"))
        # 东财这个字段是「年初至今累计」：同一年的 03-31/06-30/09-30/12-31 是递增的。
        # 只认 12-31 的年报行，否则降序遍历时会被同年 Q1 的数覆盖，把年度 capex 低估、
        # FCF 虚高（600519：2025 年报 31.28 亿 vs Q1 9.01 亿）。
        if y is not None and v is not None and d.endswith(ANNUAL_SUFFIX):
            capex[y] = v

    all_dates = sorted(merged, reverse=True)
    annual_dates = _annual_dates(all_dates)
    annual = [_period_record(d, merged[d], capex) for d in annual_dates[:6]]
    latest_date = all_dates[0] if all_dates else ""
    latest = _period_record(latest_date, merged.get(latest_date, {}), capex) if latest_date else {}
    # 最新报告期是季报时，不能用“单季 OCF - 全年 capex”算 FCF；
    # 展示和估值统一使用最近年报 FCF，TTM 只作为参考字段。
    if annual:
        latest["fcf"] = annual[0].get("fcf")
        latest["fcf_margin"] = annual[0].get("fcf_margin")
        latest["fcf_basis"] = "最近年报"

    # 最新报告期的 TTM 字段（如果接口给了）
    if latest_date and latest_date in merged:
        inc = merged[latest_date].get("income", {})
        cf = merged[latest_date].get("cashflow", {})
        latest.update({
            "revenue_ttm": num(inc.get("OperatingRevenueTTM")),
            "net_profit_ttm": num(inc.get("NPParentCompanyOwnersTTM")),
            "ocf_ttm": num(cf.get("NetOperateCashFlowTTM")),
            "eps_ttm": num(inc.get("EPSTTM")),
        })

    return {
        "annual": annual,
        "latest": latest,
        "capex_years": sorted(capex),
        "margin_trend": _margin_trend(merged),
        "structure": _structure(annual),
    }


def _quote(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    payload = _data(_find_call(calls, "data_quote"))
    q = _code_data(payload, code)
    return q if isinstance(q, dict) else {}


def _profile(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    payload = _data(_find_call(calls, "data_profile"))
    p = _code_data(payload, code)
    return p if isinstance(p, dict) else {}


def market_cap_yi(quote: dict[str, Any],
                  price: float | None = None) -> tuple[float | None, float | None]:
    """返回 (亿元市值, 元市值)；接口单位可能是元/万元/亿元，用价格×股本校准。

    `price` 传入时按该价重算（用于收盘口径），不再用接口那个实时市值。
    """
    shares = num(quote.get("total_shares"))
    if price and price > 0 and shares:
        yuan = price * shares
        return (yuan / 1e8, yuan)
    raw = num(quote.get("total_market_cap"))
    price = num(quote.get("price"))
    calc = (price * shares) if (price and shares) else None
    if raw is None:
        return (None, calc)
    factor = 1e8
    if calc:
        candidates = (1.0, 1e4, 1e8)
        factor = min(candidates, key=lambda f: abs(raw * f - calc))
    yuan = raw * factor
    return (yuan / 1e8, yuan)


def _close_price(valuation: dict[str, Any], quote: dict[str, Any],
                 financials: dict[str, Any]) -> tuple[float | None, str]:
    """取「估值口径日」（估值序列最后交易日）的收盘价，全篇估值统一用它。

    优先级：
      1. 行情日期 == 口径日 → 行情价就是那天收盘（盘后运行）；
      2. 有 `prev_close` → 盘中运行时它就是上一交易日收盘，正好是口径日；
      3. PE(TTM) × EPS(TTM) 反推（与图上那条线同源，可用 PB×BPS 交叉验证）；
         口径日 PE 为负时不反推（负 PE 乘 EPS 无意义），直接落到下一档；
      4. 兜底用行情实时价。
    返回 (价格, 口径说明)；说明会写进报告头，避免读者误以为这是实时价。
    """
    as_of = str((valuation.get("sample") or {}).get("end") or "")
    quote_date = str(quote.get("time") or "")[:10]
    live = num(quote.get("price"))
    prev_close = num(quote.get("prev_close"))
    pe = ((valuation.get("metrics") or {}).get("pe") or {}).get("current")
    eps = (financials.get("latest") or {}).get("eps_ttm")
    derived = (pe * eps) if (num(pe) and num(eps) and pe > 0 and eps > 0) else None

    def _basis(by_pe: bool = False) -> str:
        """口径说明。没有东财估值序列时 as_of 为空，不能拼成「 收盘」。"""
        note = "（按 PE×EPS 反推）" if by_pe else ""
        if as_of:
            return f"{as_of} 收盘{note}"
        return f"收盘{note}" if by_pe else "上一交易日收盘"

    if as_of and quote_date and as_of == quote_date and live:
        return live, _basis()
    if prev_close and prev_close > 0:
        # 反推值比 prev_close 差 5% 以上，通常是除权或序列错位；此时信任与图同源的反推值
        if derived and abs(derived - prev_close) / prev_close > 0.05:
            return derived, _basis(by_pe=True)
        return prev_close, _basis()
    if derived:
        return derived, _basis(by_pe=True)
    return live, "实时价"


def _years_before(iso: str, years: int) -> str:
    """把 ISO 日期往前推 N 年；解析失败返回空串（等于不截断）。"""
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return ""
    try:
        return d.replace(year=d.year - years).isoformat()
    except ValueError:                       # 2 月 29 日 → 前推到 2 月 28 日
        return d.replace(year=d.year - years, day=28).isoformat()


def _valuation_chart(ordered: list[dict[str, Any]], start: str = "",
                     years: int = 0) -> dict[str, Any]:
    """最近 N 年的周频估值点；PE 为负时置空并标记 `pe_negative`。

    负值区间不在这一层算：报告只需要「哪几段要打灰底」，`render._negative_bands()`
    直接按 `pe_negative` 取连续下标，省一份没人读的日期区间。

    `ordered` 已是周频压缩后的序列。窗口从**最后一条可用数据**往前推 N 年，
    而不是从今天往前推：停牌、退市前最后一周也不会把图拉空。
    数据本身不足 N 年时，自然只画全部可用历史（`limited=True`）。
    """
    points: list[dict[str, Any]] = []
    for row in ordered:
        d = str(row.get("TRADE_DATE") or "")[:10]
        if not d or (start and d < start):
            continue
        pe = num(row.get("PE_TTM"))
        pb = num(row.get("PB_MRQ"))
        ps = num(row.get("PS_TTM"))
        points.append({
            "date": d,
            "pe": pe if (pe is not None and pe > 0) else None,
            "pe_negative": bool(pe is not None and pe <= 0),
            "pb": pb if (pb is not None and pb > 0) else None,
            "ps": ps if (ps is not None and ps > 0) else None,
        })

    latest: dict[str, dict[str, Any] | None] = {}
    for key in ("pe", "pb", "ps"):
        value = points[-1].get(key) if points else None
        latest[key] = {"date": points[-1]["date"], "value": value} if value is not None else None

    span_years = 0.0
    if len(points) > 1:
        try:
            span_years = round(
                (date.fromisoformat(points[-1]["date"])
                 - date.fromisoformat(points[0]["date"])).days / 365.25, 2)
        except ValueError:
            span_years = 0.0

    return {
        "points": points,
        "start": points[0]["date"] if points else "",
        "end": points[-1]["date"] if points else "",
        "count": len(points),
        "years": years,
        "span_years": span_years,
        # 截断后仍覆盖不到目标年数 → 说明该股可用历史本来就不够长
        "limited": bool(years and span_years and span_years < years - 0.25),
        "latest": latest,
        "pe_negative_latest": bool(points and points[-1]["pe_negative"]),
    }


def _valuation(calls: list[dict[str, Any]],
               years: int = config.VALUATION_YEARS) -> dict[str, Any]:
    """估值序列：分位（全历史）+ 走势图（近 N 年）。

    所有“当前值”都取序列最后一点（最后交易日收盘），不接受行情实时值——
    全篇估值口径统一到收盘，见 `_close_price()`。
    口径日该指标为负或缺失时，该指标本次标为「不可用」（current / percentile 为 None），
    不回退到历史最后一个正值：那个值不属于口径日，也不该进 V 分。
    """
    rows = _merge_rows(calls, "RPT_VALUEANALYSIS_DET")
    weekly: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        d = str(row.get("TRADE_DATE") or "")[:10]
        try:
            y, m, day = (int(x) for x in d.split("-"))
            key = date(y, m, day).isocalendar()[:2]
        except (ValueError, TypeError):
            continue
        weekly[key] = row
    ordered = [weekly[k] for k in sorted(weekly)]
    series: dict[str, list[float]] = {"pe": [], "pb": [], "ps": []}
    for row in ordered:
        for key, field in (("pe", "PE_TTM"), ("pb", "PB_MRQ"), ("ps", "PS_TTM")):
            v = num(row.get(field))
            if v is not None and v > 0:
                series[key].append(v)
    if not ordered:
        return {
            "metrics": {},
            "sample": {},
            "available": False,
            "chart": {
                "points": [], "start": "", "end": "", "count": 0,
                "years": years, "span_years": 0.0, "limited": False,
                "latest": {}, "pe_negative_latest": False,
            },
        }

    # 当前值取**序列最后一点**（= 最后一个交易日收盘），不用行情实时值。
    # 否则分位表的「当前」和走势图上的「最新」会差一个交易日（实测 600519：
    # 图 21.99 / 表 21.95），读者对不上。
    last_row = ordered[-1] if ordered else {}
    current = {
        "pe": num(last_row.get("PE_TTM")),
        "pb": num(last_row.get("PB_MRQ")),
        "ps": num(last_row.get("PS_TTM")),
    }
    labels = {"pe": "PE(TTM)", "pb": "PB", "ps": "PS(TTM)"}
    metrics: dict[str, dict[str, Any]] = {}
    for key, values in series.items():
        if not values:
            continue
        cur = current.get(key)
        if cur is None or cur <= 0:
            # 口径日该指标为负/缺失 → 本次「不可用」，不回退到上一个正值。
            # 回退会让表里的「最新收盘」和图上最后一个点不是同一天，还会把一个
            # 口径日不存在的 PE 送进 V 的「预测 PE 相对当前 PE」。分位留空，
            # min/max/points 仍然展示，读者仍能看到历史区间。
            metrics[key] = {
                "label": labels[key],
                "current": None,
                "percentile": None,
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "points": len(values),
            }
            continue
        p = (sum(1 for v in values if v < cur) + 0.5 * sum(1 for v in values if v == cur)) / len(values) * 100.0
        metrics[key] = {
            "label": labels[key],
            "current": round(cur, 2),
            "percentile": round(p, 1),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "points": len(values),
        }
    return {
        "metrics": metrics,
        "sample": {
            "start": str(ordered[0].get("TRADE_DATE") or "")[:10],
            "end": str(ordered[-1].get("TRADE_DATE") or "")[:10],
            "points": len(ordered),
        },
        "chart": _valuation_chart(
            ordered,
            (_years_before(str(ordered[-1].get("TRADE_DATE") or "")[:10], years)
             if years and years > 0 else ""),
            years=years,
        ),
        "available": bool(metrics),
    }


def _as_int(value: Any) -> int | None:
    v = num(value)
    return int(v) if v is not None else None


def _forecast(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    payload = _data(_find_call(calls, "data_consensus"))
    c = _code_data(payload, code)
    forecasts: list[dict[str, Any]] = []
    for row in (c.get("forecasts") or []) if isinstance(c, dict) else []:
        if not isinstance(row, dict):
            continue
        forecasts.append({
            "year": _as_int(row.get("year")),
            "eps": num(row.get("eps")),
            "revenue_yi": (num(row.get("revenue")) / 1e4) if num(row.get("revenue")) is not None else None,
            "net_profit_yi": (num(row.get("netProfit")) / 1e4) if num(row.get("netProfit")) is not None else None,
            "pe": num(row.get("pe")),
            "pb": num(row.get("pb")),
            "ps": num(row.get("ps")),
            "revenue_yoy": num(row.get("revenueYoy")),
            "net_profit_yoy": num(row.get("netProfitYoy")),
            "institution_cnt": _as_int(row.get("institutionCnt")) or 0,
        })
    forecasts.sort(key=lambda x: x["year"] or 0)

    rating_payload = _data(_find_call(calls, "data_rating"))
    rating = _code_data(rating_payload, code)
    rating = rating if isinstance(rating, dict) else {}
    # V 只看盈利预测/目标价；评级记录不能冒充预测覆盖。
    rating_coverage = _as_int(rating.get("forecastInstitutions")) or 0
    forecast_coverage = max([f["institution_cnt"] for f in forecasts] + [0])
    # 预测行没带机构数时，用评级接口的机构数兜底；没有预测行时保持 0。
    if forecasts and forecast_coverage == 0:
        forecast_coverage = rating_coverage
    target = num(c.get("targetPrice")) if isinstance(c, dict) else None
    return {
        "available": bool(forecasts or target),
        "target_price": target,
        "forecasts": forecasts,
        "coverage": forecast_coverage,
        "rating_coverage": rating_coverage,
        "rating": {
            "buy": _as_int(rating.get("ratingBuyCnt")) or 0,
            "increase": _as_int(rating.get("ratingIncCnt")) or 0,
            "records": _as_int(rating.get("ratingCnt")) or 0,
            "forecast_institutions": _as_int(rating.get("forecastInstitutions")) or 0,
        } if rating else {},
    }


def _cash_valuation(annual: list[dict[str, Any]],
                    latest: dict[str, Any],
                    quote: dict[str, Any],
                    cap_yuan: float | None,
                    industry: str = "") -> dict[str, Any]:
    """现金扣除与底线估值（仅展示，不进入 V 分）。

    口径（2026-11 定稿）：
      · 现金底仓 = 货币资金，不扣有息负债；
      · 净利润总额取最近年报的 net_profit_total（营业收入 × 净利率的近似值）；
      · 扣现金市值 = 总市值 − 货币资金；
      · 底线价值(N) = 货币资金 + N × 最近年报净利润总额；
      · 年限 N 见 config.CASH_ANCHOR_YEARS，是情景假设，不是目标价。
    金融股（银行/保险/证券）的现金与利润口径不适用，直接返回不适用。
    """
    industry = str(industry or "")
    if any(k in industry for k in ("银行", "保险", "证券")):
        return {"applicable": False, "reason": "金融股不适用", "anchors": []}

    annual = annual or []
    latest = latest or {}
    first = annual[0] if annual else {}
    cash = num(latest.get("cash"))
    cash_period = str(latest.get("date") or "")
    if cash is None:
        cash = num(first.get("cash"))
        cash_period = str(first.get("date") or "")
    debt = num(latest.get("debt"))
    if debt is None:
        debt = num(first.get("debt"))
    np_total = num(first.get("net_profit_total"))
    profit_period = str(first.get("date") or "")
    cap = num(cap_yuan)
    shares = num(quote.get("total_shares"))

    cash_yi = cash / 1e8 if cash is not None else None
    debt_yi = debt / 1e8 if debt is not None else None
    cap_yi = cap / 1e8 if cap is not None else None
    ex_cash_yuan = (cap - cash) if (cap is not None and cash is not None) else None
    ex_cash_yi = ex_cash_yuan / 1e8 if ex_cash_yuan is not None else None
    cash_ratio = (cash / cap * 100.0) if (cash is not None and cap) else None
    np_yi = np_total / 1e8 if np_total is not None else None
    ex_cash_pe = (ex_cash_yuan / np_total
                  if (ex_cash_yuan is not None and ex_cash_yuan > 0
                      and np_total is not None and np_total > 0) else None)
    earnings_yield = (np_total / cap * 100.0
                      if (np_total is not None and np_total > 0 and cap) else None)

    anchors: list[dict[str, Any]] = []
    reason = ""
    if cash is None:
        reason = "缺少货币资金"
    elif np_total is None:
        reason = "缺少最近年报净利润总额"
    elif np_total <= 0:
        reason = "最近年报净利润总额非正"
    else:
        for years in config.CASH_ANCHOR_YEARS:
            value = cash + years * np_total
            per_share = (value / shares) if (shares and shares > 0) else None
            margin = ((value - cap) / value * 100.0) if (cap and value > 0) else None
            # 安全边际 =（底线 − 市值）/ 底线，分母是底线：市值远高于底线时会算出
            # −488% 这种读不懂的数。同格再给「市值 ÷ 底线」，读者一眼知道差几倍。
            cap_times = (cap / value) if (cap and value > 0) else None
            anchors.append({
                "years": years,
                "value_yi": value / 1e8,
                "per_share": per_share,
                "margin_pct": margin,
                "cap_times": cap_times,
            })

    return {
        "applicable": bool(anchors),
        "reason": reason,
        "cash_yi": cash_yi,
        "cash_period": cash_period,
        "debt_yi": debt_yi,
        "market_cap_yi": cap_yi,
        "cash_ratio_pct": cash_ratio,
        "ex_cash_cap_yi": ex_cash_yi,
        "negative_ex_cash": bool(ex_cash_yuan is not None and ex_cash_yuan < 0),
        "net_profit_yi": np_yi,
        "profit_period": profit_period,
        "ex_cash_pe": ex_cash_pe,
        "earnings_yield_pct": earnings_yield,
        "anchors": anchors,
    }


def _mainop(calls: list[dict[str, Any]], annual: list[dict[str, Any]]) -> dict[str, Any]:
    """产品/业务分部：取最近年报 MAINOP_TYPE=2，计算收入占比和毛利率。"""
    rows: list[dict[str, Any]] = []
    for call in calls:
        if call.get("tool") == "RPT_F10_FN_MAINOP":
            rows.extend(_rows(call))
    if not rows:
        return {"available": False, "period": "", "products": []}

    dates = sorted({str(r.get("REPORT_DATE") or "")[:10] for r in rows if str(r.get("REPORT_DATE") or "")[:10]}, reverse=True)
    target = annual[0].get("date") if annual else ""
    annual_dates = [d for d in dates if d.endswith(ANNUAL_SUFFIX)]
    if target not in dates:
        target = annual_dates[0] if annual_dates else (dates[0] if dates else "")

    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if str(row.get("REPORT_DATE") or "")[:10] != target:
            continue
        if str(row.get("MAINOP_TYPE") or "") != "2":
            continue
        name = str(row.get("ITEM_NAME") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        revenue = num(row.get("MAIN_BUSINESS_INCOME"))
        cost = num(row.get("MAIN_BUSINESS_COST"))
        ratio = num(row.get("MBI_RATIO"))
        if ratio is not None and ratio > 1.5:
            ratio = ratio / 100.0
        gross = ((revenue - cost) / revenue * 100.0) if (revenue and cost is not None and revenue > 0) else None
        products.append({
            "name": name,
            "revenue": revenue,
            "revenue_yi": (revenue / 1e8) if revenue is not None else None,
            "ratio_pct": (ratio * 100.0) if ratio is not None else None,
            "cost": cost,
            "gross_margin": gross,
        })
    products.sort(key=lambda x: x.get("revenue") or 0, reverse=True)
    if products:
        total = sum((p.get("ratio_pct") or 0) for p in products)
        if total <= 0:
            rev_sum = sum((p.get("revenue") or 0) for p in products)
            for p in products:
                p["ratio_pct"] = ((p.get("revenue") or 0) / rev_sum * 100.0) if rev_sum else None
    return {"available": bool(products), "period": target, "products": products}

def build_report_data(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    financials = build_financials(calls, code)
    quote = _quote(calls, code)
    profile = _profile(calls, code)
    annual = financials["annual"]
    latest = financials["latest"]
    valuation = _valuation(calls)
    # 全篇估值口径统一到「估值口径日」的收盘价，避免图表用收盘、表用实时。
    price, price_basis = _close_price(valuation, quote, financials)
    cap_yi, cap_yuan = market_cap_yi(quote, price=price)

    latest_year = annual[0]["year"] if annual else (latest.get("year"))

    return {
        "meta": {
            "code": code,
            "name": str(profile.get("name") or quote.get("name") or code),
            "industry": str(profile.get("industry") or profile.get("sector") or "暂无披露"),
            "business": str(profile.get("business") or ""),
            "price": price,
            "price_basis": price_basis,
            "price_date": str((valuation.get("sample") or {}).get("end") or ""),
            "live_price": num(quote.get("price")),
            "market_cap_yi": cap_yi,
            "market_cap_yuan": cap_yuan,
            "quote_date": str(quote.get("time") or "")[:10],
            "report_year": latest_year,
            "latest_date": latest.get("date") or "",
            "annual_count": len(annual),
            # 估值倍数也统一取序列最后一点（收盘口径），不再用行情实时 PE/PB
            "pe": ((valuation.get("metrics") or {}).get("pe") or {}).get("current"),
            "pb": ((valuation.get("metrics") or {}).get("pb") or {}).get("current"),
            "ps": ((valuation.get("metrics") or {}).get("ps") or {}).get("current"),
        },
        "financials": financials,
        "profile": profile,
        "valuation": valuation,
        "forecast": _forecast(calls, code),
        "mainop": _mainop(calls, annual),
        "cash_valuation": _cash_valuation(
            annual, latest, quote, cap_yuan,
            str(profile.get("industry") or profile.get("sector") or "")),
    }
