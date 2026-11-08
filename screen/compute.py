# -*- coding: utf-8 -*-
"""把接口返回整理成计算用数据；不落盘、不生成 JSON 文件。"""
from __future__ import annotations

from datetime import date
from typing import Any

import config
from screen.util import cagr, num, year_of

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
    revenue = num(inc.get("OperatingRevenue")) or num(inc.get("TotalOperatingRevenue"))
    parent_np = num(inc.get("NPParentCompanyOwners")) or num(inc.get("NPParentCompanyOwnersTTM"))
    net_margin = num(inc.get("NetProfitRatio"))
    total_np = (revenue * net_margin / 100.0) if revenue is not None and net_margin is not None else None
    ocf = num(cf.get("NetOperateCashFlow"))
    if ocf is None:
        ocf = num(cf.get("NetOperateCashFlowTTM"))
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
    ebit = num(bal.get("EBIT")) or num(inc.get("EBIT"))
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
        "roe": num(inc.get("ROEWeighted")) or num(inc.get("ROE")),
        "roa": num(inc.get("ROA")),
        "roic": num(inc.get("ROIC")),
        "ocf": ocf,
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
        "ebit": ebit,
        "finance_expense": fin_exp,
        "shares": shares,
        "ar": num(bal.get("BillAccReceivable")),
        "inventory": num(bal.get("Inventories")),
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
        y = year_of(row.get("REPORT_DATE"))
        v = num(row.get("CONSTRUCT_LONG_ASSET"))
        if y is not None and v is not None:
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
    }


def _quote(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    payload = _data(_find_call(calls, "data_quote"))
    q = _code_data(payload, code)
    return q if isinstance(q, dict) else {}


def _profile(calls: list[dict[str, Any]], code: str) -> dict[str, Any]:
    payload = _data(_find_call(calls, "data_profile"))
    p = _code_data(payload, code)
    return p if isinstance(p, dict) else {}


def market_cap_yi(quote: dict[str, Any]) -> tuple[float | None, float | None]:
    """返回 (亿元市值, 元市值)；接口单位可能是元/万元/亿元，用价格×股本校准。"""
    raw = num(quote.get("total_market_cap"))
    price = num(quote.get("price"))
    shares = num(quote.get("total_shares"))
    calc = (price * shares) if (price and shares) else None
    if raw is None:
        return (None, calc)
    factor = 1e8
    if calc:
        candidates = (1.0, 1e4, 1e8)
        factor = min(candidates, key=lambda f: abs(raw * f - calc))
    yuan = raw * factor
    return (yuan / 1e8, yuan)


def _valuation_chart(ordered: list[dict[str, Any]], start: str) -> dict[str, Any]:
    """近若干季度的周频估值点；PE 为负时置空，并记录负值区间。"""
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

    ranges: list[list[str]] = []
    range_start: int | None = None
    for i, point in enumerate(points):
        if point["pe_negative"]:
            if range_start is None:
                range_start = i
        elif range_start is not None:
            ranges.append([points[range_start]["date"], points[i - 1]["date"]])
            range_start = None
    if range_start is not None and points:
        ranges.append([points[range_start]["date"], points[-1]["date"]])

    latest: dict[str, dict[str, Any] | None] = {}
    for key in ("pe", "pb", "ps"):
        value = points[-1].get(key) if points else None
        latest[key] = {"date": points[-1]["date"], "value": value} if value is not None else None

    return {
        "points": points,
        "start": points[0]["date"] if points else "",
        "end": points[-1]["date"] if points else "",
        "count": len(points),
        "negative_ranges": ranges,
        "latest": latest,
        "pe_negative_latest": bool(points and points[-1]["pe_negative"]),
    }


def _valuation(calls: list[dict[str, Any]], quote: dict[str, Any],
               chart_start: str = "") -> dict[str, Any]:
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
                "negative_ranges": [], "latest": {}, "pe_negative_latest": False,
            },
        }

    current = {
        "pe": num(quote.get("pe_ratio")),
        "pb": num(quote.get("pb_ratio")),
        "ps": series["ps"][-1] if series["ps"] else None,
    }
    labels = {"pe": "PE(TTM)", "pb": "PB", "ps": "PS(TTM)"}
    metrics: dict[str, dict[str, Any]] = {}
    for key, values in series.items():
        if not values:
            continue
        cur = current.get(key)
        if cur is None or cur <= 0:
            cur = values[-1]
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
        "chart": _valuation_chart(ordered, chart_start),
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
    coverage = max([f["institution_cnt"] for f in forecasts] + [_as_int(rating.get("forecastInstitutions")) or 0])
    target = num(c.get("targetPrice")) if isinstance(c, dict) else None
    return {
        "available": bool(forecasts or target or rating),
        "target_price": target,
        "forecasts": forecasts,
        "coverage": coverage,
        "rating": {
            "buy": _as_int(rating.get("ratingBuyCnt")) or 0,
            "increase": _as_int(rating.get("ratingIncCnt")) or 0,
            "records": _as_int(rating.get("ratingCnt")) or 0,
            "forecast_institutions": _as_int(rating.get("forecastInstitutions")) or 0,
        } if rating else {},
    }


def _dcf(annual: list[dict[str, Any]], quote: dict[str, Any]) -> dict[str, Any]:
    years = sorted([x for x in annual if x.get("year")], key=lambda x: x["year"])
    if len(years) < 5:
        return {"applicable": False, "reason": "年报不足 5 年"}
    last = years[-1]
    fcf0 = last.get("fcf")
    if fcf0 is None or fcf0 <= 0:
        return {"applicable": False, "reason": "最近年报 FCF 非正或缺失"}
    first = years[-5]
    g1 = cagr(first.get("revenue"), last.get("revenue"), last["year"] - first["year"])
    if g1 is None:
        g1 = 5.0
    g1 = max(0.0, min(15.0, g1)) / 100.0
    r = config.WACC / 100.0
    g = config.DCF_G / 100.0
    if r <= g:
        return {"applicable": False, "reason": "折现率不高于永续增速"}
    pv = 0.0
    for i in range(1, config.DCF_YEARS + 1):
        pv += fcf0 * (1 + g1) ** i / (1 + r) ** i
    terminal = fcf0 * (1 + g1) ** config.DCF_YEARS * (1 + g) / (r - g) / (1 + r) ** config.DCF_YEARS
    ev = pv + terminal
    shares = num(quote.get("total_shares"))
    price = num(quote.get("price"))
    fair = (ev / shares) if shares else None
    margin = ((fair / price - 1.0) * 100.0) if (fair and price and fair > 0) else None
    return {
        "applicable": True,
        "fcf0_yi": fcf0 / 1e8,
        "g1_pct": g1 * 100.0,
        "wacc_pct": config.WACC,
        "g_pct": config.DCF_G,
        "fair_value": fair,
        "margin_pct": margin,
        "years": config.DCF_YEARS,
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
    cap_yi, cap_yuan = market_cap_yi(quote)
    annual = financials["annual"]
    latest = financials["latest"]
    revenue = latest.get("revenue")
    net_profit = latest.get("net_profit")
    ocf = latest.get("ocf")
    fcf = latest.get("fcf")

    latest_year = annual[0]["year"] if annual else (latest.get("year"))
    net_profit_year = annual[0].get("net_profit") if annual else net_profit
    fcf_yield = None
    if fcf is not None and cap_yuan:
        fcf_yield = fcf / cap_yuan * 100.0

    chart_start = (financials.get("margin_trend") or {}).get("start") or ""

    return {
        "meta": {
            "code": code,
            "name": str(profile.get("name") or quote.get("name") or code),
            "industry": str(profile.get("industry") or profile.get("sector") or "暂无披露"),
            "business": str(profile.get("business") or ""),
            "price": num(quote.get("price")),
            "market_cap_yi": cap_yi,
            "market_cap_yuan": cap_yuan,
            "quote_date": str(quote.get("time") or "")[:10],
            "report_year": latest_year,
            "latest_date": latest.get("date") or "",
            "latest_revenue": revenue,
            "latest_net_profit": net_profit,
            "latest_ocf": ocf,
            "latest_fcf": fcf,
            "annual_count": len(annual),
            "fcf_yield": fcf_yield,
            "pe": num(quote.get("pe_ratio")),
            "pb": num(quote.get("pb_ratio")),
            "ps": (num(quote.get("ps_ratio")) or None),
        },
        "financials": financials,
        "profile": profile,
        "valuation": _valuation(calls, quote, chart_start=chart_start),
        "forecast": _forecast(calls, code),
        "mainop": _mainop(calls, annual),
        "dcf": _dcf(annual, quote),
    }
