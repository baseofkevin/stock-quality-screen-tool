# -*- coding: utf-8 -*-
"""质量分 Q、估值分 V、10 条风险检查、决策矩阵与跟踪清单。"""
from __future__ import annotations

import math
from typing import Any

import config
from screen.util import cagr, div, inverse, linear, mean, median, num, stdev

STATUS_LABEL = {"hit": "命中", "clear": "通过", "unknown": "数据不足"}


def _years(data: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(data["financials"]["annual"], key=lambda x: x.get("year") or 0)


def _latest(data: dict[str, Any]) -> dict[str, Any]:
    ys = _years(data)
    return ys[-1] if ys else {}


def _prev(data: dict[str, Any]) -> dict[str, Any]:
    ys = _years(data)
    return ys[-2] if len(ys) >= 2 else {}


def _group(parts: list[dict[str, Any]], label: str, weight: float) -> dict[str, Any]:
    available = [p for p in parts if p.get("score") is not None]
    got = sum(float(p["score"]) for p in available)
    max_available = sum(float(p["max"]) for p in available)
    max_possible = sum(float(p["max"]) for p in parts)
    # 缺失项按 0 分计入组内总分，避免“数据缺失反而满分”；覆盖度单独展示。
    score = (got / max_possible * weight) if max_available else None
    return {
        "key": label,
        "label": label,
        "weight": weight,
        "score": score,
        "max": weight,
        "coverage": (max_available / sum(float(p["max"]) for p in parts) * 100.0) if parts else 0.0,
        "items": parts,
    }


def _item(label: str, score: float | None, maximum: float, raw: str) -> dict[str, Any]:
    return {"label": label, "score": score, "max": maximum, "raw": raw}


def _quality(data: dict[str, Any]) -> dict[str, Any]:
    ys = _years(data)
    if len(ys) < 2:
        return {"score": None, "grade": "数据不足", "groups": [], "coverage": 0.0}

    roic = median([y.get("roic") for y in ys])
    roe = median([y.get("roe") for y in ys])
    spread = (roic - config.WACC) if roic is not None else None

    fcf_pairs = [(y.get("fcf"), y.get("net_profit")) for y in ys]
    fcf_known = [p for p in fcf_pairs if p[0] is not None]
    positive = sum(1 for f, _ in fcf_known if f > 0)
    fcf_ni = median([div(f, n) for f, n in fcf_pairs if (f is not None and n and n > 0)])
    cfo_ni = median([div(y.get("ocf"), y.get("net_profit")) for y in ys
                     if y.get("net_profit") and y["net_profit"] > 0])

    latest = _latest(data)
    net_debt = None
    if latest.get("debt") is not None and latest.get("cash") is not None:
        net_debt = latest["debt"] - latest["cash"]
    net_debt_ebit = div(net_debt, latest.get("ebit"))
    interest = None
    if latest.get("finance_expense") is not None and latest.get("ebit") is not None:
        interest = (latest["ebit"] / latest["finance_expense"]) if latest["finance_expense"] > 0 else 99.0
    goodwill_ratio = div(latest.get("goodwill"), latest.get("equity"))

    rev_cagr = cagr(ys[0].get("revenue"), ys[-1].get("revenue"), (ys[-1].get("year") or 0) - (ys[0].get("year") or 0))
    gm_std = stdev([y.get("gross_margin") for y in ys])
    roe_std = stdev([y.get("roe") for y in ys])
    # 与风险检查一致：用最近 3 年，避免 IPO 当年一次性扩张拉高稀释率
    dilution_base = ys[-4] if len(ys) >= 4 else ys[0]
    dilution = cagr(dilution_base.get("shares"), ys[-1].get("shares"),
                    (ys[-1].get("year") or 0) - (dilution_base.get("year") or 0))

    accrual = None
    if latest.get("net_profit") is not None and latest.get("ocf") is not None and latest.get("total_assets"):
        accrual = (latest["net_profit"] - latest["ocf"]) / latest["total_assets"] * 100.0
    deducted_ratio = div(latest.get("deducted"), latest.get("net_profit"))

    returns = _group([
        _item("ROIC−WACC", linear(spread, 0, 15, 20), 20, f"{_p(spread)}"),
        _item("ROE 中位数", linear(roe, 8, 20, 10), 10, f"{_p(roe)}"),
    ], "资本回报", config.QUALITY_WEIGHTS["returns"])
    cash = _group([
        _item("FCF 为正年数", (positive / len(fcf_known) * 10) if fcf_known else None, 10,
              f"{positive}/{len(fcf_known)}" if fcf_known else "—"),
        _item("FCF/净利润", linear(fcf_ni, 0, 1, 8), 8, f"{_n(fcf_ni)}"),
        _item("CFO/净利润", linear(cfo_ni, 0.7, 1.2, 7), 7, f"{_n(cfo_ni)}"),
    ], "现金创造力", config.QUALITY_WEIGHTS["cash"])
    balance = _group([
        _item("净负债/EBIT", inverse(net_debt_ebit, 0, 3, 8) if net_debt_ebit is not None else None,
              8, f"{_n(net_debt_ebit)}"),
        _item("利息保障", linear(interest, 3, 10, 6) if interest is not None else None, 6,
              "净利息收入" if interest == 99.0 else f"{_n(interest)}x"),
        _item("商誉/净资产", inverse(goodwill_ratio * 100 if goodwill_ratio is not None else None, 0, 20, 6),
              6, f"{_p(goodwill_ratio * 100 if goodwill_ratio is not None else None)}"),
    ], "资产负债表", config.QUALITY_WEIGHTS["balance"])
    durability = _group([
        _item("营收 CAGR", linear(rev_cagr, 0, 15, 5), 5, f"{_p(rev_cagr)}"),
        _item("毛利率稳定性", inverse(gm_std, 0, 5, 4), 4, f"σ {_n(gm_std)}"),
        _item("ROE 稳定性", inverse(roe_std, 0, 8, 3), 3, f"σ {_n(roe_std)}"),
        _item("股本稀释", inverse(dilution, 0, 3, 3), 3, f"{_p(dilution)}"),
    ], "成长与稳定", config.QUALITY_WEIGHTS["durability"])
    accounting = _group([
        _item("应计利润", inverse(accrual, 0, 10, 5), 5, f"{_p(accrual)}"),
        _item("扣非占比", linear(deducted_ratio * 100 if deducted_ratio is not None else None, 70, 100, 5),
              5, f"{_p(deducted_ratio * 100 if deducted_ratio is not None else None)}"),
    ], "会计质量", config.QUALITY_WEIGHTS["accounting"])

    groups = [returns, cash, balance, durability, accounting]
    available = [g for g in groups if g["score"] is not None]
    weight = sum(g["weight"] for g in available)
    total = (sum(float(g["score"]) for g in available) / weight * 100.0) if weight else None
    coverage = (sum(g["weight"] * g["coverage"] / 100.0 for g in groups) / sum(g["weight"] for g in groups) * 100.0
                if groups else 0.0)
    if total is None:
        grade = "数据不足"
    elif total >= 85:
        grade = "优秀"
    elif total >= 75:
        grade = "良好"
    elif total >= 65:
        grade = "中等偏上"
    elif total >= 55:
        grade = "中等"
    elif total >= 45:
        grade = "偏弱"
    else:
        grade = "差"
    return {
        "score": round(total, 1) if total is not None else None,
        "grade": grade,
        "groups": groups,
        "coverage": round(coverage, 1),
    }


def _p(v: float | None, digits: int = 1) -> str:
    return "—" if v is None else f"{v:.{digits}f}%"


def _n(v: float | None, digits: int = 2) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def _risk_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    ys = _years(data)
    latest = _latest(data)
    prev = _prev(data)
    checks: list[dict[str, Any]] = []

    def add(key: str, name: str, status: str, detail: str, severity: str = "中") -> None:
        checks.append({"key": key, "name": name, "status": status, "detail": detail, "severity": severity})

    # 1 CFO/净利润
    recent = ys[-3:]
    pairs = [(y.get("ocf"), y.get("net_profit")) for y in recent if y.get("net_profit") and y["net_profit"] > 0 and y.get("ocf") is not None]
    if len(pairs) < 2:
        add("cfo_ni", "利润含金量", "unknown", "近 3 年可用数据不足")
    else:
        bad = [f / n for f, n in pairs if f / n < config.CFO_NI_FLOOR]
        add("cfo_ni", "利润含金量", "hit" if len(bad) >= 2 else "clear",
            f"近 3 年 {len(bad)} 年 CFO/净利润 < {config.CFO_NI_FLOOR:.1f}", "高")

    # 2 FCF 持续性
    known = [y.get("fcf") for y in ys if y.get("fcf") is not None]
    if len(known) < 3:
        add("fcf", "FCF 持续性", "unknown", "FCF 可用年数不足 3 年", "高")
    else:
        neg = sum(1 for v in known if v <= 0)
        add("fcf", "FCF 持续性", "hit" if neg >= config.FCF_NEGATIVE_YEARS else "clear",
            f"{len(known)} 个年度中 {neg} 年为负", "高")

    # 3 杠杆
    net_debt = (latest.get("debt") - latest.get("cash")) if (latest.get("debt") is not None and latest.get("cash") is not None) else None
    nd_ebit = div(net_debt, latest.get("ebit"))
    if nd_ebit is None:
        add("leverage", "杠杆", "unknown", "有息负债/现金/EBIT 字段不足", "高")
    else:
        add("leverage", "杠杆", "hit" if nd_ebit > config.NET_DEBT_EBIT_MAX else "clear",
            f"净有息负债/EBIT = {nd_ebit:.2f}", "高")

    # 4 利息保障
    fin = latest.get("finance_expense")
    ebit = latest.get("ebit")
    if fin is None or ebit is None:
        add("interest", "利息保障", "unknown", "利息费用或 EBIT 缺失", "高")
    elif fin <= 0:
        add("interest", "利息保障", "clear", "净利息收入，无利息覆盖压力", "高")
    else:
        cover = ebit / fin
        add("interest", "利息保障", "hit" if cover < config.INTEREST_COVER_MIN else "clear",
            f"EBIT/利息费用 = {cover:.1f}x", "高")

    # 5 商誉
    gw = latest.get("goodwill")
    eq = latest.get("equity")
    if gw is None or eq in (None, 0):
        add("goodwill", "商誉", "unknown", "商誉或净资产字段缺失", "高")
    else:
        ratio = gw / eq
        add("goodwill", "商誉", "hit" if ratio > config.GOODWILL_EQUITY_MAX else "clear",
            f"商誉/归母净资产 = {ratio * 100:.1f}%" +
            ("（接口未返回商誉，按 0 处理，建议核对年报）" if latest.get("goodwill_imputed") else ""), "高")

    # 6 应收/存货背离
    if not prev or not latest:
        add("ar_inventory", "应收/存货背离", "unknown", "缺少上一年度数据")
    else:
        rg = div((latest.get("revenue") or 0) - (prev.get("revenue") or 0), prev.get("revenue"))
        ag = div((latest.get("ar") or 0) - (prev.get("ar") or 0), prev.get("ar"))
        ig = div((latest.get("inventory") or 0) - (prev.get("inventory") or 0), prev.get("inventory"))
        hit = (rg is not None and rg < 0 and ((ag is not None and ag > config.AR_INV_GROWTH_ALERT)
                                              or (ig is not None and ig > config.AR_INV_GROWTH_ALERT)))
        add("ar_inventory", "应收/存货背离", "hit" if hit else "clear",
            f"营收 {_p(rg * 100 if rg is not None else None)}；应收 {_p(ag * 100 if ag is not None else None)}；存货 {_p(ig * 100 if ig is not None else None)}")

    # 7 非经常性利润
    ratio = div(latest.get("deducted"), latest.get("net_profit"))
    if ratio is None or (latest.get("net_profit") or 0) <= 0:
        add("nonrecurring", "非经常性利润", "unknown", "扣非净利润缺失或归母为负")
    else:
        add("nonrecurring", "非经常性利润", "hit" if ratio < config.NONRECURRING_RATIO_MIN else "clear",
            f"扣非/归母 = {ratio * 100:.1f}%")

    # 8 少数股东
    total_np = latest.get("net_profit_total")
    parent_np = latest.get("net_profit")
    if total_np in (None, 0) or parent_np is None or total_np <= 0 or parent_np <= 0:
        add("minority", "少数股东", "unknown", "净利润总额无法从接口直接取得或为负")
    else:
        minority = 1 - parent_np / total_np
        add("minority", "少数股东", "hit" if minority > 0.30 else "clear",
            f"少数股东损益占比约 {minority * 100:.1f}%")

    # 9 股本稀释：用最近 3 年，避免把 IPO 当年的一次性扩张误判为持续稀释
    base = ys[-4] if len(ys) >= 4 else (ys[0] if ys else {})
    dilution = cagr(base.get("shares"), latest.get("shares"),
                    (latest.get("year") or 0) - (base.get("year") or 0) if base else None)
    if dilution is None:
        add("dilution", "股本稀释", "unknown", "股本数据不足")
    else:
        add("dilution", "股本稀释", "hit" if dilution / 100 > config.SHARE_DILUTION_MAX else "clear",
            f"近 3 年股本 CAGR = {dilution:.2f}%" + ("（可能含 IPO/增发，需核对）" if dilution > 10 else ""))

    # 10 短期偿债
    cr, qr = latest.get("current_ratio"), latest.get("quick_ratio")
    if cr is None or qr is None:
        add("liquidity", "短期偿债", "unknown", "流动/速动比率缺失")
    else:
        add("liquidity", "短期偿债", "hit" if (cr < config.CURRENT_RATIO_MIN and qr < config.QUICK_RATIO_MIN) else "clear",
            f"流动比率 {cr:.2f}；速动比率 {qr:.2f}")
    return checks


def _fatal(data: dict[str, Any], checks: list[dict[str, Any]]) -> list[str]:
    latest = _latest(data)
    fatal: list[str] = []
    if latest.get("equity") is not None and latest["equity"] <= 0:
        fatal.append("净资产为负")
    for c in checks:
        if c["key"] == "interest" and c["status"] == "hit" and "EBIT/利息费用" in c["detail"]:
            # 这里不直接判 <1，渲染层会给出具体值；保留命中作为高风险信号
            pass
    fin, ebit = latest.get("finance_expense"), latest.get("ebit")
    if fin is not None and fin > 0 and ebit is not None and ebit / fin < 1:
        fatal.append("利息保障 < 1")
    gw, eq = latest.get("goodwill"), latest.get("equity")
    if gw is not None and eq and gw / eq > config.GOODWILL_EQUITY_FATAL:
        fatal.append("商誉/净资产超过 50%")
    if all((y.get("ocf") or 0) < 0 for y in _years(data)[-3:]) and latest.get("ebit") and latest.get("debt") is not None and latest.get("cash") is not None:
        if (latest["debt"] - latest["cash"]) / latest["ebit"] > 4:
            fatal.append("连续 3 年经营现金流为负且净负债/EBIT > 4")
    return fatal


def _forecast_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """从机构预测中提取 V 分所需的三个原始值。

    - 目标价空间 = 目标价 / 现价 - 1；
    - 预测 PE 变化 = 当前 PE / 预测 PE - 1，正数表示预测 PE 更低；
    - 未来净利增速 = 未来 1~3 年 net_profit_yoy 均值，缺失时用复合增速兜底。
    """
    fc = data.get("forecast") or {}
    forecasts = [f for f in (fc.get("forecasts") or []) if isinstance(f, dict)]
    meta = data.get("meta") or {}

    price = num(meta.get("price"))
    target = num(fc.get("target_price"))
    target_upside = ((target / price - 1.0) * 100.0
                     if (target is not None and target > 0 and price and price > 0) else None)

    current_pe = num(meta.get("pe"))
    forecast_pe = None
    forecast_pe_year = None
    for f in forecasts:
        pe = num(f.get("pe"))
        if pe is not None and pe > 0:
            forecast_pe = pe
            forecast_pe_year = f.get("year")
            break
    pe_change = ((current_pe / forecast_pe - 1.0) * 100.0
                 if (current_pe is not None and current_pe > 0
                     and forecast_pe is not None and forecast_pe > 0) else None)

    annual = (data.get("financials") or {}).get("annual") or []
    base = annual[-1] if annual else {}
    base_np = num(base.get("net_profit"))
    growth = None
    growth_count = 0
    growth_reason = ""
    if base_np is None:
        growth_reason = "缺少最近年报净利润"
    elif base_np <= 0:
        growth_reason = "最近年报亏损，增速不参与"
    else:
        values = [num(f.get("net_profit_yoy")) for f in forecasts[:3]]
        values = [v for v in values if v is not None]
        if values:
            growth = mean(values)
            growth_count = len(values)
        else:
            last = None
            last_year = None
            for f in reversed(forecasts):
                np_yi = num(f.get("net_profit_yi"))
                if np_yi is not None and np_yi > 0:
                    last = np_yi * 1e8
                    last_year = f.get("year")
                    break
            base_year = base.get("year")
            years = (last_year - base_year) if (last_year is not None and base_year is not None) else None
            if last is not None and years is not None and years > 0:
                growth = ((last / base_np) ** (1.0 / years) - 1.0) * 100.0
                growth_count = years
            else:
                growth_reason = "机构预测不足"
    if growth is None and not growth_reason:
        growth_reason = "机构预测不足"

    return {
        "target_price": target,
        "target_upside": target_upside,
        "current_pe": current_pe,
        "forecast_pe": forecast_pe,
        "forecast_pe_year": forecast_pe_year,
        "pe_change": pe_change,
        "growth": growth,
        "growth_count": growth_count,
        "growth_reason": growth_reason,
    }


def _valuation_score(data: dict[str, Any]) -> dict[str, Any]:
    """机构口径 V 分：机构估值 60% + 未来净利增速 40%。

    机构估值内部：目标价空间 40 + 预测 PE 相对当前 PE 20。
    没有机构覆盖（或缺少估值/增速任一类）时 V 为空，但 Q 分仍正常计算。
    """
    m = _forecast_metrics(data)

    def _score(value: float | None, key: str) -> float | None:
        if value is None:
            return None
        low, high = config.VALUATION_RANGES[key]
        return linear(value, low, high, 100)

    target_score = _score(m["target_upside"], "target_upside")
    pe_score = _score(m["pe_change"], "forecast_pe")
    growth_score = _score(m["growth"], "profit_growth")

    if m["target_price"] is not None and m["target_upside"] is not None:
        target_raw = f"目标价 {_n(m['target_price'])} 元（{m['target_upside']:+.1f}%）"
    elif m["target_price"] is not None:
        target_raw = f"目标价 {_n(m['target_price'])} 元（现价缺失）"
    else:
        target_raw = "无目标价"
    if m["current_pe"] is not None and m["forecast_pe"] is not None:
        year = f"{m['forecast_pe_year']}E" if m["forecast_pe_year"] else "预测"
        pe_raw = f"当前 {_n(m['current_pe'])}x → {year} {_n(m['forecast_pe'])}x"
    else:
        pe_raw = "缺少当前 PE 或预测 PE"
    growth_raw = (f"未来 {m['growth_count']} 年均值 {m['growth']:+.1f}%"
                  if m["growth"] is not None else m["growth_reason"])

    parts = [
        {"key": "target_upside", "label": "机构目标价空间", "score": target_score,
         "max": config.VALUATION_WEIGHTS["target_upside"], "raw": target_raw},
        {"key": "forecast_pe", "label": "预测 PE 相对当前 PE", "score": pe_score,
         "max": config.VALUATION_WEIGHTS["forecast_pe"], "raw": pe_raw},
        {"key": "profit_growth", "label": "预期未来净利增速", "score": growth_score,
         "max": config.VALUATION_WEIGHTS["profit_growth"], "raw": growth_raw},
    ]
    available = [p for p in parts if p["score"] is not None]
    max_available = sum(p["max"] for p in available)
    has_valuation = target_score is not None or pe_score is not None
    has_growth = growth_score is not None
    total = (sum(p["score"] * p["max"] / 100.0 for p in available) / max_available * 100.0
             if (max_available and has_valuation and has_growth) else None)
    if total is None:
        grade = "数据不足"
    elif total >= 80:
        grade = "明显低估"
    elif total >= 65:
        grade = "低估"
    elif total >= 50:
        grade = "合理"
    elif total >= 35:
        grade = "偏高"
    else:
        grade = "明显高估"
    return {"score": round(total, 1) if total is not None else None, "grade": grade,
            "parts": parts, "coverage": round(max_available, 1)}


def _data_quality(data: dict[str, Any], q: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    """数据完整度：只做展示和“可买”前置条件，不再生成 0~100 置信度。"""
    total = len(checks)
    unknown_items = [c for c in checks if c.get("status") == "unknown"]
    known = total - len(unknown_items)
    critical_unknown = [
        c.get("name") or c.get("key")
        for c in unknown_items
        if c.get("key") in config.BUY_CRITICAL_CHECKS
    ]
    fc = data.get("forecast") or {}
    coverage = int(fc.get("coverage") or 0)
    q_coverage = float(q.get("coverage") or 0.0)

    blockers: list[str] = []
    if coverage < config.BUY_MIN_INSTITUTION_COVERAGE:
        blockers.append(f"机构覆盖 {coverage} 家（少于 {config.BUY_MIN_INSTITUTION_COVERAGE} 家）")
    if q_coverage < config.BUY_MIN_QUALITY_COVERAGE:
        blockers.append(f"Q 数据覆盖 {q_coverage:.0f}%（低于 {config.BUY_MIN_QUALITY_COVERAGE:.0f}%）")
    if critical_unknown:
        blockers.append("关键风险检查缺失：" + "、".join(critical_unknown))

    return {
        "risk_total": total,
        "risk_known": known,
        "risk_unknown": len(unknown_items),
        "critical_unknown": critical_unknown,
        "institution_coverage": coverage,
        "q_coverage": round(q_coverage, 1),
        "buy_blockers": blockers,
    }


def _decision(q: dict[str, Any], v: dict[str, Any], fatal: list[str],
              data_quality: dict[str, Any]) -> dict[str, Any]:
    """质量调整后的估值门槛：Q 越低，要求的 V 越高；Q<45 禁止买入。"""
    qs, vs = q.get("score"), v.get("score")
    if fatal:
        return {"key": "avoid", "label": "回避", "reason": "出现致命风险：" + "；".join(fatal)}
    if qs is None or vs is None:
        return {"key": "unknown", "label": "数据不足，不下结论", "reason": "质量分或估值分无法计算"}

    if qs < config.QUALITY_HARD_FLOOR:
        return {"key": "avoid", "label": "回避", "reason": f"质量分 {qs:.1f} 低于 {config.QUALITY_HARD_FLOOR:.0f}，禁止买入"}

    if qs >= 75:
        if vs >= config.BUY_MIN_V["high"]:
            result = {"key": "buy", "label": "推荐买入", "reason": "质量好且估值便宜"}
        elif vs >= 50:
            result = {"key": "watch_price", "label": "好公司，等价格", "reason": "质量通过，估值尚未到舒服区间"}
        elif vs >= 35:
            result = {"key": "expensive", "label": "好公司，但偏贵，等价格", "reason": "质量通过，估值偏贵"}
        else:
            result = {"key": "expensive", "label": "好公司，但太贵", "reason": "质量通过，估值明显偏贵"}
    elif qs >= 65:
        if vs >= 80:
            result = {"key": "buy", "label": "推荐买入", "reason": "质量中等偏上，估值明显低估"}
        elif vs >= config.BUY_MIN_V["medium_high"]:
            result = {"key": "buy_ok", "label": "可买", "reason": "质量中等偏上，估值便宜"}
        elif vs >= 50:
            result = {"key": "watch", "label": "观察", "reason": "质量中等偏上，估值不够便宜"}
        else:
            result = {"key": "avoid", "label": "回避", "reason": "质量中等偏上，但估值不便宜"}
    elif qs >= 55:
        if vs >= config.BUY_MIN_V["medium"]:
            result = {"key": "buy_small", "label": "小仓买入", "reason": "质量一般，估值足够便宜，仅小仓"}
        elif vs >= 50:
            result = {"key": "watch", "label": "观察", "reason": "质量一般，估值不够便宜"}
        else:
            result = {"key": "avoid", "label": "回避", "reason": "质量一般且估值不便宜"}
    else:
        if vs >= config.BUY_MIN_V["weak"]:
            result = {"key": "buy_trial", "label": "小仓试错", "reason": "质量偏弱，只在明显低估时小仓"}
        elif vs >= 65:
            result = {"key": "watch", "label": "观察", "reason": "质量偏弱，估值不够便宜"}
        else:
            result = {"key": "avoid", "label": "回避", "reason": "质量偏弱且估值不便宜"}

    # 数据不完整时，所有买入类结论降为观察，但不改变 Q<45 的回避。
    blockers = data_quality.get("buy_blockers") or []
    if result["key"] in config.BUY_KEYS and blockers:
        return {
            "key": "watch",
            "label": "观察，等待数据完整",
            "reason": f"按质量与估值可{result['label']}，但" + "；".join(blockers) + "，暂不买入",
        }
    return result


def _expectation_flags(data: dict[str, Any], v: dict[str, Any]) -> list[str]:
    fc = data.get("forecast") or {}
    flags: list[str] = []
    if not fc.get("available"):
        return flags
    ys = _years(data)
    hist = None
    if len(ys) >= 4:
        hist = cagr(ys[-4].get("net_profit"), ys[-1].get("net_profit"), 3)
    forecasts = fc.get("forecasts") or []
    nxt = next((f for f in forecasts if f.get("net_profit_yoy") is not None), None)
    if nxt and hist is not None and nxt["net_profit_yoy"] > hist + 15:
        flags.append(f"机构预期下一年净利增速 {nxt['net_profit_yoy']:.1f}%，明显高于公司近 3 年实际增速 {hist:.1f}%，预期偏乐观。")
    target = fc.get("target_price")
    price = data["meta"].get("price")
    if target and price:
        upside = (target / price - 1) * 100
        if upside > 30 and (v.get("score") is not None and v["score"] < 60):
            flags.append(f"机构目标价较现价高 {upside:.1f}%，但规则估值分仅 {v['score']:.0f}，两者分歧较大。")
    if nxt and nxt["net_profit_yoy"] < 0:
        pe = (data["valuation"].get("metrics") or {}).get("pe") or {}
        if pe.get("percentile") is not None and pe["percentile"] < 30:
            flags.append("机构预测净利下滑，而当前 PE 分位很低，低估值可能已反映盈利下修。")
    return flags



def _moat(data: dict[str, Any]) -> dict[str, Any]:
    """护城河只看量化证据，不写行业故事。"""
    ys = _years(data)
    if len(ys) < 3:
        return {"level": "数据不足", "score": None, "reasons": ["年报不足 3 年，无法判断持续性"]}
    roic = median([y.get("roic") for y in ys])
    spread = (roic - config.WACC) if roic is not None else None
    fcf_margin = median([(y.get("fcf_margin") * 100 if y.get("fcf_margin") is not None else None) for y in ys])
    roe = median([y.get("roe") for y in ys])
    gm_std = stdev([y.get("gross_margin") for y in ys])
    above = sum(1 for y in ys if (y.get("roic") is not None and y["roic"] > config.WACC))
    total = 0.0
    max_total = 0.0
    checks = [
        (linear(spread, 0, 15, 40), 40),
        (linear(fcf_margin, 0, 15, 25), 25),
        (linear(roe, 8, 20, 15), 15),
        (inverse(gm_std, 0, 5, 10), 10),
        (above / len(ys) * 10, 10),
    ]
    for value, weight in checks:
        if value is not None:
            total += value
            max_total += weight
    score = (total / max_total * 100.0) if max_total else None
    level = "宽护城河" if score is not None and score >= 70 else ("窄护城河" if score is not None and score >= 45 else "无明显护城河")
    if score is None:
        level = "数据不足"
    reasons = []
    if spread is not None:
        reasons.append(f"5 年 ROIC 中位数 {roic:.1f}%，相对 WACC {config.WACC:.1f}% 的差值为 {spread:+.1f}pct")
    if fcf_margin is not None:
        reasons.append(f"5 年 FCF/营收中位数 {fcf_margin:.1f}%")
    if roe is not None:
        reasons.append(f"5 年 ROE 中位数 {roe:.1f}%")
    reasons.append(f"ROIC 高于 WACC 的年度：{above}/{len(ys)}")
    return {"level": level, "score": round(score, 1) if score is not None else None, "reasons": reasons}

def _tracking(data: dict[str, Any], q: dict[str, Any]) -> list[dict[str, str]]:
    latest = _latest(data)
    ys = _years(data)
    items = []
    spread = None
    roic = median([y.get("roic") for y in ys])
    if roic is not None:
        spread = roic - config.WACC
    items.append({"metric": "ROIC−WACC", "current": _p(spread), "threshold": "> 0", "frequency": "每年"})
    items.append({"metric": "CFO/净利润", "current": _n(div(latest.get("ocf"), latest.get("net_profit"))),
                  "threshold": f"≥ {config.CFO_NI_FLOOR:.1f}", "frequency": "每季"})
    nd = (latest.get("debt") - latest.get("cash")) if latest.get("debt") is not None and latest.get("cash") is not None else None
    items.append({"metric": "净有息负债/EBIT", "current": _n(div(nd, latest.get("ebit"))),
                  "threshold": f"≤ {config.NET_DEBT_EBIT_MAX:.0f}", "frequency": "每季"})
    items.append({"metric": "商誉/净资产", "current": _p(div(latest.get("goodwill"), latest.get("equity")) * 100 if latest.get("goodwill") is not None and latest.get("equity") else None),
                  "threshold": f"≤ {config.GOODWILL_EQUITY_MAX * 100:.0f}%", "frequency": "每半年"})
    items.append({"metric": "营收增速", "current": _p(div((latest.get("revenue") or 0) - (_prev(data).get("revenue") or 0), _prev(data).get("revenue")) * 100 if _prev(data).get("revenue") else None),
                  "threshold": "> 0，且应收/存货不异常加速", "frequency": "每季"})
    pe = (data["valuation"].get("metrics") or {}).get("pe") or {}
    items.append({"metric": "PE 分位", "current": f"{pe.get('percentile', '—')}%" if pe else "—",
                  "threshold": "< 80%", "frequency": "每月"})
    items.append({"metric": "DCF 折价", "current": _p(data.get("dcf", {}).get("margin_pct")),
                  "threshold": "> 0", "frequency": "每年"})
    items.append({"metric": "机构一致预期", "current": f"{len((data.get('forecast') or {}).get('forecasts') or [])} 个年度",
                  "threshold": "不下修、不空覆盖", "frequency": "每季"})
    return items


def compute_scores(data: dict[str, Any]) -> dict[str, Any]:
    q = _quality(data)
    v = _valuation_score(data)
    checks = _risk_checks(data)
    fatal = _fatal(data, checks)
    data_quality = _data_quality(data, q, checks)
    decision = _decision(q, v, fatal, data_quality)
    data["quality"] = q
    data["moat"] = _moat(data)
    data["valuation_score"] = v
    data["risks"] = {"checks": checks, "fatal": fatal, "hits": sum(1 for c in checks if c["status"] == "hit")}
    data["data_quality"] = data_quality
    data["decision"] = decision
    data["flags"] = _expectation_flags(data, v)
    data["tracking"] = _tracking(data, q)
    return data
