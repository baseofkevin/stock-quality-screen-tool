# -*- coding: utf-8 -*-
"""质量分 Q、估值分 V、14 条风险检查、决策矩阵与跟踪清单。"""
from __future__ import annotations

from typing import Any

import config
from screen.fmt import num as _n, pct as _p, signed_pct as _delta_pct, yi_suffix as _yi
from screen.util import cagr, clamp, div, inverse, linear, mean, median, num, stdev

STATUS_LABEL = {"hit": "命中", "watch": "提示", "clear": "通过", "unknown": "数据不足", "na": "不适用"}


def _years(data: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(data["financials"]["annual"], key=lambda x: x.get("year") or 0)


def _latest(data: dict[str, Any]) -> dict[str, Any]:
    ys = _years(data)
    return ys[-1] if ys else {}


def _prev(data: dict[str, Any]) -> dict[str, Any]:
    ys = _years(data)
    return ys[-2] if len(ys) >= 2 else {}


def _group(parts: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """组名和组权重都从 config 取，调用方只给 key（returns / cash / ...）。"""
    label = config.QUALITY_GROUP_LABELS[key]
    weight = config.QUALITY_WEIGHTS[key]
    available = [p for p in parts if p.get("score") is not None]
    got = sum(float(p["score"]) for p in available)
    max_available = sum(float(p["max"]) for p in available)
    max_possible = sum(float(p["max"]) for p in parts)
    # 缺失项按 0 分计入组内总分，避免“数据缺失反而满分”；覆盖度单独展示。
    score = (got / max_possible * weight) if max_available else None
    return {
        "key": key,
        "label": label,
        "weight": weight,
        "score": score,
        "max": weight,
        "coverage": (max_available / sum(float(p["max"]) for p in parts) * 100.0) if parts else 0.0,
        "items": parts,
    }


def _item(label: str, score: float | None, maximum: float, raw: str) -> dict[str, Any]:
    return {"label": label, "score": score, "max": maximum, "raw": raw}


def _band(group: str, item: str, value: float | None, m: dict[str, dict[str, float]]) -> float | None:
    """按 config.QUALITY_ITEM_RANGES 把原始值映射成该子项得分。

    区间和方向都写在 config 里（0.9.8 起）：以前 13 组 low/high 硬编码在这里，
    改 QUALITY_ITEM_MAX 的满分却忘了改区间，Q 会悄悄偏一点，测试也看不出来。
    """
    low, high, direction = config.QUALITY_ITEM_RANGES[group][item]
    points = m[group][item]
    return linear(value, low, high, points) if direction == "up" else inverse(value, low, high, points)


def grade_of(total: float | None) -> str:
    """Q 分 → 档名（优秀 / 良好 / ...）。分档表在 config.QUALITY_GRADES。"""
    if total is None:
        return "数据不足"
    return next(label for cut, label in config.QUALITY_GRADES if total >= cut)



def _quality(data: dict[str, Any]) -> dict[str, Any]:
    """质量分 Q：五个维度、16 个子项，组内缺失按 0 分。

    0.9.0 的四处口径修正（权重表本身一个字没动）：
    - A1 毛利率稳定性乘一个「水平」修正，低毛利公司的稳定不值满分；
    - A2 应计利润取近 3 年中位数，避开单年预收/应付集中结算；
    - A3 现金组加 FCF/营收（绝对量陪跑），避免只看“为正年数”；
    - A4 资本回报组加 ROIC 高于 WACC 的年数，ROE 降权到 6。
    """
    ys = _years(data)
    if len(ys) < config.MIN_ANNUAL_YEARS:
        return {"score": None, "grade": "数据不足", "groups": [], "coverage": 0.0}

    m = config.QUALITY_ITEM_MAX
    roic = median([y.get("roic") for y in ys])
    roe = median([y.get("roe") for y in ys])
    spread = (roic - config.WACC) if roic is not None else None
    # A4：中位数只说明“典型年份”，看不出持续性；000725 就是 5 年里 1 年达标
    roic_known = [y["roic"] for y in ys if y.get("roic") is not None]
    above = sum(1 for v in roic_known if v > config.WACC)

    fcf_pairs = [(y.get("fcf"), y.get("net_profit")) for y in ys]
    fcf_known = [p for p in fcf_pairs if p[0] is not None]
    positive = sum(1 for f, _ in fcf_known if f > 0)
    fcf_ni = median([div(f, n) for f, n in fcf_pairs if (f is not None and n and n > 0)])
    cfo_ni = median([div(y.get("ocf"), y.get("net_profit")) for y in ys
                     if y.get("net_profit") and y["net_profit"] > 0])
    # A3：FCF/营收 —— 比值不受规模影响，与护城河「现金创造」同一口径
    fcf_margin = median([y.get("fcf_margin") for y in ys if y.get("fcf_margin") is not None])
    fcf_margin_pct = (fcf_margin * 100.0) if fcf_margin is not None else None

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
    gm_list = [y.get("gross_margin") for y in ys if y.get("gross_margin") is not None]
    gm_med, gm_std = median(gm_list), stdev(gm_list)
    # A1：σ 只说明稳不稳，不说明高不高；毛利率 5% 的公司 σ 再小也不叫稳定
    gm_level = None
    if gm_med is not None:
        gm_level = clamp((gm_med - config.QUALITY_GM_LEVEL_FLOOR)
                         / (config.QUALITY_GM_LEVEL_FULL - config.QUALITY_GM_LEVEL_FLOOR), 0.0, 1.0)
    gm_stability = None
    if gm_level is not None and gm_std is not None:      # 只有 1 年毛利率时 σ 为空，不能乘 None
        gm_base = _band("durability", "gm_stability", gm_std, m)
        gm_stability = gm_base * gm_level if gm_base is not None else None
    roe_std = stdev([y.get("roe") for y in ys])
    # 与风险检查一致：用最近 3 年，避免 IPO 当年一次性扩张拉高稀释率
    dilution_base = ys[-4] if len(ys) >= 4 else ys[0]
    dilution = cagr(dilution_base.get("shares"), ys[-1].get("shares"),
                    (ys[-1].get("year") or 0) - (dilution_base.get("year") or 0))

    # A2：应计利润取近 3 年中位数；单年值仍写进 raw，便于和年报对账
    accrual_series = [
        (y["net_profit"] - y["ocf"]) / y["total_assets"] * 100.0
        for y in ys[-config.QUALITY_ACCRUAL_YEARS:]
        if y.get("net_profit") is not None and y.get("ocf") is not None and y.get("total_assets")
    ]
    accrual = median(accrual_series)
    accrual_one = accrual_series[-1] if accrual_series else None
    deducted_ratio = div(latest.get("deducted"), latest.get("net_profit"))

    returns = _group([
        _item("ROIC−WACC", _band("returns", "spread", spread, m), m["returns"]["spread"],
              f"{_p(spread)}"),
        _item("ROIC>WACC 年数",
              (above / len(roic_known) * m["returns"]["above_wacc"]) if roic_known else None,
              m["returns"]["above_wacc"],
              f"{above}/{len(roic_known)}" if roic_known else "—"),
        _item("ROE 中位数", _band("returns", "roe", roe, m), m["returns"]["roe"], f"{_p(roe)}"),
    ], "returns")
    cash = _group([
        _item("FCF 为正年数", (positive / len(fcf_known) * m["cash"]["fcf_years"]) if fcf_known else None,
              m["cash"]["fcf_years"], f"{positive}/{len(fcf_known)}" if fcf_known else "—"),
        _item("FCF/净利润", _band("cash", "fcf_ni", fcf_ni, m), m["cash"]["fcf_ni"],
              f"{_n(fcf_ni)}"),
        _item("CFO/净利润", _band("cash", "cfo_ni", cfo_ni, m), m["cash"]["cfo_ni"],
              f"{_n(cfo_ni)}"),
        _item("FCF/营收", _band("cash", "fcf_margin", fcf_margin_pct, m),
              m["cash"]["fcf_margin"], f"{_p(fcf_margin_pct)}"),
    ], "cash")
    goodwill_pct = goodwill_ratio * 100 if goodwill_ratio is not None else None
    balance = _group([
        _item("净负债/EBIT", _band("balance", "net_debt_ebit", net_debt_ebit, m),
              m["balance"]["net_debt_ebit"], f"{_n(net_debt_ebit)}"),
        _item("利息保障", _band("balance", "interest", interest, m), m["balance"]["interest"],
              "净利息收入" if interest == 99.0 else f"{_n(interest)}x"),
        _item("商誉/净资产", _band("balance", "goodwill", goodwill_pct, m),
              m["balance"]["goodwill"], f"{_p(goodwill_pct)}"),
    ], "balance")
    durability = _group([
        _item("营收 CAGR", _band("durability", "rev_cagr", rev_cagr, m),
              m["durability"]["rev_cagr"], f"{_p(rev_cagr)}"),
        _item("毛利率稳定性", gm_stability, m["durability"]["gm_stability"],
              f"σ {_n(gm_std)}｜中位 {_p(gm_med)}（水平 ×{gm_level:.2f}）" if gm_level is not None
              else f"σ {_n(gm_std)}"),
        _item("ROE 稳定性", _band("durability", "roe_stability", roe_std, m),
              m["durability"]["roe_stability"], f"σ {_n(roe_std)}"),
        _item("股本稀释", _band("durability", "dilution", dilution, m),
              m["durability"]["dilution"], f"{_p(dilution)}"),
    ], "durability")
    deducted_pct = deducted_ratio * 100 if deducted_ratio is not None else None
    accounting = _group([
        _item("应计利润", _band("accounting", "accrual", accrual, m), m["accounting"]["accrual"],
              f"3 年中位 {_p(accrual)}（单年 {_p(accrual_one)}）"),
        _item("扣非占比", _band("accounting", "deducted", deducted_pct, m),
              m["accounting"]["deducted"], f"{_p(deducted_pct)}"),
    ], "accounting")

    groups = [returns, cash, balance, durability, accounting]
    available = [g for g in groups if g["score"] is not None]
    weight = sum(g["weight"] for g in available)
    total = (sum(float(g["score"]) for g in available) / weight * 100.0) if weight else None
    coverage = (sum(g["weight"] * g["coverage"] / 100.0 for g in groups) / sum(g["weight"] for g in groups) * 100.0
                if groups else 0.0)
    return {
        "score": round(total, 1) if total is not None else None,
        "grade": grade_of(total),          # 分档表在 config.QUALITY_GRADES
        "groups": groups,
        "coverage": round(coverage, 1),
    }


def _growth(now: float | None, before: float | None) -> float | None:
    if now is None or before is None or before == 0:
        return None
    return (now - before) / abs(before)


def _ar_total(row: dict[str, Any]) -> float | None:
    """应收 = 应收账款 + 应收款项融资（票据在部分公司记入后者，茅台即如此）。"""
    if not row:
        return None
    ar, rf = row.get("ar"), row.get("receivable_fin")
    if ar is None and rf is None:
        return None
    return (ar or 0.0) + (rf or 0.0)


def _contract_liab(row: dict[str, Any]) -> float | None:
    """合同负债 + 预收款项（新准则下预收多已并入合同负债，老报表仍有余额）。"""
    if not row:
        return None
    cl, ap = row.get("contract_liability"), row.get("advance_payment")
    if cl is None and ap is None:
        return None
    return (cl or 0.0) + (ap or 0.0)


def _expense(row: dict[str, Any]) -> float | None:
    """期间费用 = 销售费用 + 管理费用 + 研发费用。"""
    if not row:
        return None
    parts = [row.get("sell_expense"), row.get("admin_expense"), row.get("rnd_expense")]
    if all(p is None for p in parts):
        return None
    return sum(p or 0.0 for p in parts)


def _quarter_index(d: str) -> int | None:
    try:
        year, month = int(d[:4]), int(d[5:7])
    except (ValueError, TypeError):
        return None
    return year * 4 + (month - 1) // 3


def _delta(now: float | None, before: float | None) -> float | None:
    """差（比率型指标给 pct 点差，营收给增速），任一缺失即 None。"""
    if now is None or before is None:
        return None
    return now - before


def _change_level(delta: float | None, *, eps: float = config.MARGIN_IMPROVE_EPS,
                  up: str = "改善", flat: str = "持平", down: str = "走弱") -> str:
    """把变化量翻成等级：改善 / 持平 / 走弱（营收用 增长 / 持平 / 下滑）。"""
    if delta is None:
        return "—"
    if delta > eps:
        return up
    if delta < -eps:
        return down
    return flat


def _rest_note(rows: list[dict[str, Any]], weak: list[dict[str, Any]]) -> str:
    """结论句的后半段：其余项是改善/持平。缺数据的那几项统一在结尾补。"""
    rest = [r for r in rows if r["level"] in ("改善", "增长", "持平")]
    return f"；其余 {len(rest)} 项改善或持平"


def _margin_improve(data: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """① 毛利率环比改善三条件：环比增、营收环比不降、高于上年同季。

    按「季度序号」取上一季 / 上年同季，不按位置取——接口缺季时，
    位置相邻的两个点可能相差一整年（年报 + 三季报），环比会算错。

    返回 (状态, 表格用说明, 结构化对比)。对比里给毛利率 / 净利率 / 营业收入
    各自的同比与环比变化（六个数字），并点名「哪个指标的哪个口径没改善」，
    供报告在图表下方逐行展开。
    """
    points = ((data.get("financials") or {}).get("margin_trend") or {}).get("points") or []
    usable = [p for p in points if p.get("gross") is not None and p.get("revenue")]
    if not usable:
        return "unknown", "无可用单季数据", {}
    by_index = {_quarter_index(str(p.get("date"))): p for p in usable}
    cur = usable[-1]
    ci = _quarter_index(str(cur.get("date")))
    prev = by_index.get(ci - 1) if ci else None
    yoy = by_index.get(ci - 4) if ci else None
    if prev is None or yoy is None:
        missing = "、".join(n for n, v in (("上一季", prev), ("上年同季", yoy)) if v is None)
        return "unknown", f"季报不连续（缺{missing}），无法做环比/同比判定", {}

    eps = config.MARGIN_IMPROVE_EPS
    c1 = cur["gross"] - prev["gross"] > eps                 # 毛利率环比增
    c2 = cur["revenue"] >= prev["revenue"]                  # 营收环比不降
    c3 = cur["gross"] - yoy["gross"] > eps                  # 毛利率高于上年同季
    met = sum([c1, c2, c3])

    # 六个变化：营收用增速（%），毛利率/净利率用 pct 点差
    rev_yoy = _growth(cur.get("revenue"), yoy.get("revenue"))
    rev_qoq = _growth(cur.get("revenue"), prev.get("revenue"))
    g_yoy, g_qoq = _delta(cur["gross"], yoy.get("gross")), _delta(cur["gross"], prev.get("gross"))
    n_yoy, n_qoq = _delta(cur.get("net"), yoy.get("net")), _delta(cur.get("net"), prev.get("net"))
    specs = [
        ("营业收入", "同比", rev_yoy, "rev"),
        ("毛利率", "同比", g_yoy, "pp"),
        ("净利率", "同比", n_yoy, "pp"),
        ("营业收入", "环比", rev_qoq, "rev"),
        ("毛利率", "环比", g_qoq, "pp"),
        ("净利率", "环比", n_qoq, "pp"),
    ]
    rows = []
    for metric, basis, delta, unit in specs:
        if unit == "rev":
            level = _change_level(delta, eps=0.001, up="增长", down="下滑")
            text = "—" if delta is None else f"{delta * 100:+.1f}%"
        else:
            level = _change_level(delta)
            text = "—" if delta is None else f"{delta:+.2f}pct"
        rows.append({"metric": metric, "basis": basis, "delta": delta,
                     "unit": unit, "level": level, "text": text})
    by_key = {(r["metric"], r["basis"]): r for r in rows}
    weak = [r for r in rows if r["level"] in ("走弱", "下滑")]
    # 按指标分组（毛利率 → 营业收入 → 净利率），组内同比在前：读者是顺着指标看的
    _metric_order = {"毛利率": 0, "营业收入": 1, "净利率": 2}
    _basis_order = {"同比": 0, "环比": 1}
    weak.sort(key=lambda r: (_metric_order.get(r["metric"], 9), _basis_order.get(r["basis"], 9)))
    cond_fail = [n for n, ok in (("C1", c1), ("C2", c2), ("C3", c3)) if not ok]

    def _point(point: dict[str, Any], key: str, digits: int = 2) -> str:
        v = point.get(key)
        return "—" if v is None else f"{v:.{digits}f}%"

    cur_label, prev_label, yoy_label = (cur.get("label"), prev.get("label"), yoy.get("label"))
    yoy_line = (f"同比（{cur_label} vs {yoy_label}）："
                f"营业收入 {_yi(cur.get('revenue'))}（{by_key[('营业收入', '同比')]['text']}，"
                f"上年同季 {_yi(yoy.get('revenue'))}）"
                f"｜毛利率 {_point(cur, 'gross')}（{by_key[('毛利率', '同比')]['text']}，"
                f"上年同季 {_point(yoy, 'gross')}）"
                f"｜净利率（归母） {_point(cur, 'net')}（{by_key[('净利率', '同比')]['text']}，"
                f"上年同季 {_point(yoy, 'net')}）")
    qoq_line = (f"环比（{cur_label} vs {prev_label}）："
                f"营业收入 {_yi(cur.get('revenue'))}（{by_key[('营业收入', '环比')]['text']}，"
                f"上一季 {_yi(prev.get('revenue'))}）"
                f"｜毛利率 {_point(cur, 'gross')}（{by_key[('毛利率', '环比')]['text']}，"
                f"上一季 {_point(prev, 'gross')}）"
                f"｜净利率（归母） {_point(cur, 'net')}（{by_key[('净利率', '环比')]['text']}，"
                f"上一季 {_point(prev, 'net')}）")

    if met == 3:
        label = "改善（C1/C2/C3 成立）"
        verdict = "C1/C2/C3 三项条件全部成立：毛利率环比、营业收入环比、毛利率同比都在改善。"
        if weak:
            verdict += ("；另需注意 " + "、".join(
                f"「{r['metric']}{r['basis']}」{r['text']}" for r in weak) + "，不在三条件之内。")
    elif met == 2:
        label = f"未改善（{cond_fail[0]} 不成立）"
        if weak:
            verdict = ("未改善的是" + "、".join(
                f"「{r['metric']}{r['basis']}」（{r['text']}）" for r in weak)
                + _rest_note(rows, weak) + "。")
        else:
            verdict = (f"三条件里 {cond_fail[0]} 不成立，但幅度都在容差（±{eps:.2f}pct）内，"
                       "只能说没有明显改善。")
    else:
        label = f"走弱（{'/'.join(cond_fail)} 不成立）"
        if weak:
            verdict = ("变差的是" + "、".join(
                f"「{r['metric']}{r['basis']}」（{r['text']}）" for r in weak)
                + _rest_note(rows, weak) + "。")
        else:
            verdict = "三条件里有两项以上不成立，且没有单项继续改善，毛利率已经走弱。"

    # 缺数据的两项（通常是净利率）不能算进「改善」里，结尾统一交代一句
    missing = [r for r in rows if r["level"] == "—"]
    if missing:
        miss_txt = "、".join(f"{r['metric']}{r['basis']}" for r in missing)
        verdict = verdict.rstrip("。") + f"；{miss_txt}缺数据未判定。"

    detail = (f"{label}｜同比：毛利率 {by_key[('毛利率', '同比')]['text']}、"
              f"净利率 {by_key[('净利率', '同比')]['text']}、营收 {by_key[('营业收入', '同比')]['text']}"
              f"｜环比：毛利率 {by_key[('毛利率', '环比')]['text']}、"
              f"净利率 {by_key[('净利率', '环比')]['text']}、营收 {by_key[('营业收入', '环比')]['text']}")

    if met == 3:
        badge = "毛利率同比、环比均改善"
    elif weak:
        # 同一指标的同比、环比都没改善时合成一句（「营业收入同比、环比下滑」），别列两遍
        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in weak:
            grouped.setdefault(r["metric"], []).append(r)
        names = []
        for metric, items in grouped.items():
            if {i["basis"] for i in items} == {"同比", "环比"}:
                names.append(f"{metric}同比、环比{items[0]['level']}")
            else:
                names.append(f"{metric}{items[0]['basis']}{items[0]['level']}")
        badge = "；".join(names[:2]) + (f" 等 {len(names)} 项" if len(names) > 2 else "")
    else:
        badge = "、".join(f"{n} 不成立" for n in cond_fail) or "未改善"

    status = "clear" if met == 3 else ("watch" if met == 2 else "hit")
    compare = {
        "label": label,
        "badge": badge,
        "yoy_line": yoy_line,
        "qoq_line": qoq_line,
        "verdict": verdict,
        "rows": rows,
        "weak": weak,
        "cond": {"C1": c1, "C2": c2, "C3": c3},
        "prev_label": prev_label,
        "yoy_label": yoy_label,
        "cur_label": cur_label,
    }
    return status, detail, compare


def _risk_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    ys = _years(data)
    latest = _latest(data)
    prev = _prev(data)
    checks: list[dict[str, Any]] = []

    def add(key: str, group: str, name: str, status: str, detail: str,
            severity: str = "中", tag: str | None = None) -> dict[str, Any]:
        checks.append({"key": key, "group": group, "name": name, "status": status,
                       "detail": detail, "severity": severity,
                       "tag": _CHECK_TAGS.get((key, status), "") if tag is None else tag})
        return checks[-1]

    # ================= 真伪 =================
    # 1 净现比 TTM 四档 + FCF 负年数（原「利润含金量」与「FCF 持续性」合并）
    np_ttm = latest.get("np_ttm") or latest.get("net_profit")
    ocf_ttm = latest.get("ocf_ttm") or latest.get("ocf")
    cash_ni = div(ocf_ttm, np_ttm) if (np_ttm is not None and np_ttm > 0) else None
    fcf_known = [y.get("fcf") for y in ys if y.get("fcf") is not None]
    fcf_neg = sum(1 for v in fcf_known if v <= 0)
    # 金融股 / 缺现金流量表的样本没有可用 FCF，不能写成“0 年中 0 年为负”这种空话
    fcf_txt = (f"FCF {len(fcf_known)} 年中 {fcf_neg} 年为负" if fcf_known
               else "FCF 无可用年度（口径不适用）")
    if cash_ni is None:
        add("cash_flow", "真伪", "现金流质量", "unknown",
            f"归母净利为负或缺失，净现比无法计算；{fcf_txt}", "高")
    else:
        if cash_ni > config.CASH_NI_GOOD:
            tier = "优秀"
        elif cash_ni >= config.CASH_NI_OK:
            tier = "健康"
        elif cash_ni >= config.CASH_NI_WEAK:
            tier = "警惕"
        else:
            tier = "危险"
        two = [y for y in ys[-2:]
               if y.get("net_profit") and y["net_profit"] > 0 and y.get("ocf") is not None]
        low2 = len(two) == 2 and all(y["ocf"] / y["net_profit"] < config.CASH_NI_TWO_YEAR for y in two)
        detail = f"净现比(TTM) {_n(cash_ni)}（{tier}）；{fcf_txt}"
        if low2:
            detail += "；连续 2 年 < 0.5"
        if cash_ni < config.CASH_NI_WEAK or low2 or fcf_neg >= config.FCF_NEGATIVE_YEARS:
            status = "hit"
        elif cash_ni < config.CASH_NI_OK:
            status = "watch"
        else:
            status = "clear"
        add("cash_flow", "真伪", "现金流质量", status, detail, "高")

    # 2 扣非/归母缺口 + 扣非增速缺口 + 期间费用率（原「非经常性利润」，费用率并入）
    ded_ratio = div(latest.get("deducted"), latest.get("net_profit"))
    if ded_ratio is None or (latest.get("net_profit") or 0) <= 0:
        add("nonrecurring", "真伪", "利润口径", "unknown", "扣非净利润缺失或归母为负", "高")
    else:
        ded_g = _growth(latest.get("deducted"), prev.get("deducted"))
        np_g = _growth(latest.get("net_profit"), prev.get("net_profit"))
        detail = f"扣非/归母 {_p(ded_ratio * 100)}"
        if ded_g is not None and np_g is not None:
            detail += f"；扣非增速 {_delta_pct(ded_g)} vs 归母 {_delta_pct(np_g)}"
        exp_gap = None
        if _expense(latest) is not None and _expense(prev) is not None:
            exp_g = _growth(_expense(latest), _expense(prev))
            rev_g = _growth(latest.get("revenue"), prev.get("revenue"))
            if exp_g is not None and rev_g is not None:
                exp_gap = exp_g - rev_g
                exp_ratio = div(_expense(latest), latest.get("revenue"))
                detail += (f"；期间费用率 {_p(exp_ratio * 100)}"
                           f"（增速差 {exp_gap * 100:+.1f}pct）")
        if ded_ratio < config.NONRECURRING_RATIO_MIN:
            status = "hit"
        elif exp_gap is not None and exp_gap > config.EXPENSE_GROWTH_GAP:
            status = "watch"
        else:
            status = "clear"
        add("nonrecurring", "真伪", "利润口径", status, detail, "高")

    # ================= 趋势 =================
    # 3 ① 毛利率环比改善（三条件）+ 毛利率/净利率/营收的同比与环比对照
    status, detail, compare = _margin_improve(data)
    add("margin_improve", "趋势", "① 毛利率环比改善", status, detail, "高")["compare"] = compare

    # 4 ② 合同负债/营收（同比 + 占比）
    cl_now = _contract_liab(latest)
    cl_prev = _contract_liab(prev)
    if cl_now is None:
        add("contract_liability", "趋势", "② 合同负债", "unknown", "合同负债/预收款项字段缺失", "高")
    else:
        cl_g = _growth(cl_now, cl_prev)
        cl_ratio = div(cl_now, latest.get("revenue"))
        detail = f"合同负债 {_yi(cl_now)}（占营收 {_p((cl_ratio or 0) * 100) if cl_ratio is not None else '—'}，同比 {_delta_pct(cl_g)}）"
        if cl_g is not None and cl_g >= config.CL_GROWTH_MIN and (cl_ratio or 0) >= config.CL_REV_MIN:
            status = "clear"
            detail = "需求扩张；" + detail
        elif cl_g is not None and cl_g <= -config.CL_GROWTH_MIN:
            prev2 = ys[-3] if len(ys) >= 3 else {}
            cl_prev2 = _contract_liab(prev2)
            g2 = _growth(cl_prev, cl_prev2) if cl_prev is not None else None
            if g2 is not None and g2 <= -config.CL_GROWTH_MIN:
                status = "hit"
                detail = "连续两期下滑；" + detail
            else:
                status = "watch"
                detail = "预收转弱；" + detail
        else:
            status = "clear"
            detail = "平稳；" + detail
        add("contract_liability", "趋势", "② 合同负债", status, detail, "高")

    # ================= 质量 =================
    # 5 应收增速差（口径只用应收账款/应收票据：应收款项融资属于票据结算，不是赊销）
    ar_now = latest.get("ar")
    ar_ratio = div(ar_now, latest.get("revenue"))
    ar_pairs = [(ys[i - 1], ys[i]) for i in range(1, len(ys))][-2:]
    ar_gaps = []
    for before, now in ar_pairs:
        ag = _growth(now.get("ar"), before.get("ar"))
        rg = _growth(now.get("revenue"), before.get("revenue"))
        ar_gaps.append((ag - rg) if (ag is not None and rg is not None) else None)
    if ar_ratio is None or ar_ratio < config.AR_BASE_RATIO_MIN:
        add("ar_gap", "质量", "应收增速差", "unknown",
            f"应收占营收 {_p(ar_ratio * 100, 3) if ar_ratio is not None else '—'}，基数过小，增速差无意义", "高")
    else:
        gaps_txt = "、".join(_delta_pct(g) if g is None else f"{g * 100:+.1f}pct" for g in ar_gaps)
        detail = f"应收增速差（应收增速−营收增速）近两年 {gaps_txt}；应收占营收 {_p(ar_ratio * 100)}"
        latest_gap = ar_gaps[-1] if ar_gaps else None
        both = len(ar_gaps) == 2 and all(g is not None and g > config.AR_REV_GAP_ALERT for g in ar_gaps)
        # 档位与基数解耦：先判「这个科目够不够大」，再判命中/关注。
        # 否则 0.5%~2% 的应收只要连续两年超 15pct 就直接 hit，把只有几千万的科目
        # 送进一致性闸门（命中 1 项 → 买入类降「观察」），正是小基数保护要防的事。
        material = ar_ratio >= config.AR_MATERIAL_RATIO
        if latest_gap is not None and latest_gap > config.AR_REV_GAP_ALERT:
            if both and material:
                status = "hit"
                detail = "连续两年 > 15pct；" + detail
            else:
                # 应收占营收 <2% 时只提示（茅台票据 1.17% 能造出 +2580pct）
                if not material:
                    detail = ("连续两年 > 15pct，但应收不足营收 2%，仅提示；"
                              if both else "应收不足营收 2%，仅提示；") + detail
                status = "watch"
        else:
            status = "clear"
        add("ar_gap", "质量", "应收增速差", status, detail, "高")

    # 6 存货增速差
    inv_now = latest.get("inventory")
    inv_ratio = div(inv_now, latest.get("revenue"))
    if inv_ratio is None or inv_ratio < config.INV_MATERIAL_RATIO:
        add("inventory_gap", "质量", "存货增速差", "unknown",
            f"存货占营收 {_p(inv_ratio * 100, 2) if inv_ratio is not None else '—'}，占比过小，增速差不作判定", "中")
    else:
        ig = _growth(inv_now, prev.get("inventory"))
        rg = _growth(latest.get("revenue"), prev.get("revenue"))
        gap = (ig - rg) if (ig is not None and rg is not None) else None
        detail = (f"存货 {_delta_pct(ig)} vs 营收 {_delta_pct(rg)}（差 {gap * 100:+.1f}pct）；"
                  f"存货占营收 {_p(inv_ratio * 100)}" if gap is not None
                  else f"存货占营收 {_p(inv_ratio * 100)}，增速差无法计算")
        ig2 = _growth(prev.get("inventory"), ys[-3].get("inventory")) if len(ys) >= 3 else None
        rg2 = _growth(prev.get("revenue"), ys[-3].get("revenue")) if len(ys) >= 3 else None
        gap2 = (ig2 - rg2) if (ig2 is not None and rg2 is not None) else None
        if gap is not None and gap > config.INV_REV_GAP_HIGH:
            status = "hit"
        elif (gap is not None and gap > config.INV_REV_GAP_ALERT
              and gap2 is not None and gap2 > config.INV_REV_GAP_ALERT):
            status = "hit"
            detail = "连续两年 > 15pct；" + detail
        elif gap is not None and gap > config.INV_REV_GAP_ALERT:
            status = "watch"
        else:
            status = "clear"
        add("inventory_gap", "质量", "存货增速差", status, detail, "中")

    # 7 三流组合（经营 / 投资 / 筹资）
    ocf, icf, fin_cf = latest.get("ocf"), latest.get("icf"), latest.get("fcf_fin")
    if ocf is None or icf is None or fin_cf is None:
        add("cashflow_pattern", "质量", "三流组合", "unknown", "经营/投资/筹资现金流字段不全", "中")
    else:
        signs = "".join("+" if v >= 0 else "-" for v in (ocf, icf, fin_cf))
        detail = f"{signs}（经营 {_yi(ocf)}｜投资 {_yi(icf)}｜筹资 {_yi(fin_cf)}）"
        if ocf < 0 and fin_cf > 0:
            status, detail = "hit", "靠输血续命；" + detail
        elif ocf < 0:
            status, detail = "hit", "经营失血；" + detail
        elif icf > 0:
            status, detail = "watch", "投资现金流为正（需确认是否理财/存款到期）；" + detail
        elif fin_cf > 0:
            status, detail = "watch", "经营造血但仍在净融资；" + detail
        else:
            status, detail = "clear", "经营造血 + 投资扩张 + 净还债；" + detail
        add("cashflow_pattern", "质量", "三流组合", status, detail, "中")

    # 8 在建工程 / 固定资产（连续递增 = 扩产）
    ratios = []
    for row in ys[-3:]:
        r = div(row.get("construction"), row.get("fixed_asset"))
        ratios.append(r)
    if all(r is None for r in ratios):
        add("construction", "质量", "在建工程", "unknown", "无在建工程科目（轻资产或未披露）", "中")
    else:
        seq = [f"{_p(r * 100) if r is not None else '—'}" for r in ratios]
        detail = f"在建工程/固资 {' → '.join(seq)}"
        rising = (len(ratios) == 3 and None not in ratios
                  and ratios[2] > ratios[1] > ratios[0])
        debt_up = (_growth(latest.get("debt"), prev.get("debt")) or 0) > 0
        if rising:
            detail = (("借钱扩产（同期有息负债增加）" if debt_up else "自有资金扩产（同期有息负债未增）")
                      + "：" + detail)
            add("construction", "质量", "在建工程", "watch", detail, "中",
                tag="借钱扩产" if debt_up else "自有资金扩产")
        else:
            add("construction", "质量", "在建工程", "clear", detail, "中")

    # 9 每股口径（股本扩张 且 每股营收/每股 OCF 未增）
    base = ys[-4] if len(ys) >= 4 else (ys[0] if ys else {})
    shares_g = _growth(latest.get("shares"), base.get("shares"))
    if shares_g is None:
        add("per_share", "质量", "每股口径", "unknown", "股本数据不足", "中")
    else:
        rev_ps = div(latest.get("revenue"), latest.get("shares"))
        rev_ps0 = div(base.get("revenue"), base.get("shares"))
        ocf_ps = div(latest.get("ocf"), latest.get("shares"))
        ocf_ps0 = div(base.get("ocf"), base.get("shares"))
        rev_g = _growth(rev_ps, rev_ps0)
        ocf_g = _growth(ocf_ps, ocf_ps0)
        detail = (f"股本 {_delta_pct(shares_g)}｜每股营收 {_delta_pct(rev_g)}"
                  f"｜每股 OCF {_delta_pct(ocf_g)}")
        if shares_g <= 0:
            add("per_share", "质量", "每股口径", "clear", "股本未扩张；" + detail, "中")
        elif (rev_g is not None and rev_g <= 0) or (ocf_g is not None and ocf_g <= 0):
            add("per_share", "质量", "每股口径", "hit", "股本扩张但每股指标未增；" + detail, "中")
        else:
            add("per_share", "质量", "每股口径", "clear", detail, "中")

    # ================= 安全 =================
    # 10 现金短债比（+ 速动比率，记分不否决）
    short_all = [latest.get("short_loan"), latest.get("ncl_1y")]
    quick = latest.get("quick_ratio")
    quick_txt = f"；速动 {_n(quick)}" + ("（< 0.7 记 1 分）" if quick is not None and quick < config.QUICK_RATIO_WATCH else "")
    if all(v is None for v in short_all):
        # 有资产负债表但短期借款/一年内到期都是空 → 公司确实没有短期有息负债；
        # 整张表都没有（latest 为空）→ 什么都不知道，不能判“通过”。
        if latest.get("total_assets") is None:
            add("cash_debt", "安全", "现金短债比", "unknown", "缺少资产负债表数据", "高")
        else:
            add("cash_debt", "安全", "现金短债比", "clear", "无短期有息负债" + quick_txt, "高")
    elif latest.get("cash") is None:
        add("cash_debt", "安全", "现金短债比", "unknown", "货币资金字段缺失", "高")
    else:
        short = sum(v or 0.0 for v in short_all)
        if short <= 0:
            add("cash_debt", "安全", "现金短债比", "clear", "无短期有息负债" + quick_txt, "高")
        else:
            cdr = latest["cash"] / short
            if cdr > config.CASH_DEBT_RATIO_CALM:
                detail = f"无短债压力（货币资金 {_yi(latest['cash'])} vs 短债 {_yi(short)}）"
            else:
                detail = f"货币资金 {_yi(latest['cash'])} / 短债 {_yi(short)} = {_n(cdr)}"
            if cdr < config.CASH_DEBT_RATIO_FATAL:
                status = "hit"
            elif cdr < config.CASH_DEBT_RATIO_MIN:
                status = "watch"
            else:
                status = "clear"
            add("cash_debt", "安全", "现金短债比", status, detail + quick_txt, "高")

    # 11 杠杆 + 有息负债趋势（看趋势不看绝对值）
    net_debt = None
    if latest.get("debt") is not None and latest.get("cash") is not None:
        net_debt = latest["debt"] - latest["cash"]
    nd_ebit = div(net_debt, latest.get("ebit"))
    debt_g = _growth(latest.get("debt"), base.get("debt"))
    debt_txt = (f"有息负债 {_yi(base.get('debt'))} → {_yi(latest.get('debt'))}（{_delta_pct(debt_g)}）"
                if latest.get("debt") is not None else "有息负债字段缺失")
    if nd_ebit is None:
        add("leverage", "安全", "杠杆", "unknown", "有息负债/现金/EBIT 字段不足；" + debt_txt, "高")
    else:
        add("leverage", "安全", "杠杆",
            "hit" if nd_ebit > config.NET_DEBT_EBIT_MAX else "clear",
            f"净有息负债/EBIT = {_n(nd_ebit)}；{debt_txt}", "高")

    # 12 利息负担（EBIT/利息，并列毛利额/财务费用）
    fin = latest.get("finance_expense")
    ebit = latest.get("ebit")
    rev_ttm = latest.get("revenue")
    gm = latest.get("gross_margin")
    gross_profit = (rev_ttm * gm / 100.0) if (rev_ttm is not None and gm is not None) else None
    if fin is None or ebit is None:
        add("interest", "安全", "利息负担", "unknown", "利息费用或 EBIT 缺失", "高")
    elif fin <= 0:
        add("interest", "安全", "利息负担", "clear", "净利息收入，无利息覆盖压力", "高")
    else:
        cover = ebit / fin
        gross_cover = div(gross_profit, fin)
        detail = f"EBIT/利息费用 = {_n(cover, 1)}x"
        if gross_cover is not None:
            detail += f"；毛利额/利息 = {_n(gross_cover, 1)}x"
            if gross_cover < config.INTEREST_COVER_MIN and cover >= config.INTEREST_COVER_MIN:
                detail += "（为银行打工）"
        hit = cover < config.INTEREST_COVER_MIN or (
            gross_cover is not None and gross_cover < config.INTEREST_COVER_MIN)
        add("interest", "安全", "利息负担", "hit" if hit else "clear", detail, "高")

    # 13 商誉（20% 警惕 / 30% 高危）
    gw, eq = latest.get("goodwill"), latest.get("equity")
    if gw is None or eq in (None, 0):
        add("goodwill", "安全", "商誉", "unknown", "商誉或净资产字段缺失", "高")
    else:
        ratio = gw / eq
        detail = f"商誉/归母净资产 = {_p(ratio * 100)}" + (
            "（接口未返回商誉，按 0 处理，建议核对年报）" if latest.get("goodwill_imputed") else "")
        if ratio > config.GOODWILL_EQUITY_HIT:
            status = "hit"
        elif ratio > config.GOODWILL_EQUITY_WATCH:
            status = "watch"
        else:
            status = "clear"
        add("goodwill", "安全", "商誉", status, detail, "高")

    # 14 其他应收款/总资产（造假高发科目）
    oar, ta = latest.get("other_ar"), latest.get("total_assets")
    if oar is None or ta in (None, 0):
        add("other_receivable", "安全", "其他应收款", "unknown", "其他应收款或总资产字段缺失", "中")
    else:
        ratio = oar / ta
        ap_g = _growth(latest.get("other_ap"), prev.get("other_ap"))
        detail = f"其他应收款/总资产 = {_p(ratio * 100, 2)}"
        if ap_g is not None:
            detail += f"；其他应付款同比 {_delta_pct(ap_g)}"
        if ratio > config.OTHER_AR_ASSETS_MAX:
            if ap_g is not None and ap_g > 0:
                status = "hit"
                detail += "（其他应付同步增加，疑似资金体外循环）"
            else:
                status = "watch"
        else:
            status = "clear"
        add("other_receivable", "安全", "其他应收款", status, detail, "中")

    if _is_financial(data):
        for c in checks:
            if c["key"] in config.FINANCIAL_INAPPLICABLE_CHECKS:
                # 金融股的毛利率/净利率本身没有可比口径，同比环比对照也不该展示
                c.update(status="na", detail="金融股口径不适用（本工具不做该科目判定）",
                         tag="", compare={})
            elif c["key"] == "leverage" and c["status"] == "unknown":
                # 银行的“有息负债”混了同业存放/存款，绝对值与 EBIT 都不可比，
                # 只报“字段不足”而不摆那个数量级，避免读者误读。
                c["detail"] = "金融股不适用本口径（有息负债含同业负债，EBIT 不可比）"

    return checks


# 组合定性用的标签：key+状态 → 一句话里的关键词（construction 单独在检查里给）
_CHECK_TAGS = {
    ("ar_gap", "hit"): "赊销",
    ("ar_gap", "watch"): "赊销",
    ("cash_flow", "hit"): "现金弱",
    ("cash_flow", "watch"): "现金弱",
    ("cash_debt", "hit"): "短债",
    ("cash_debt", "watch"): "短债",
    ("leverage", "hit"): "加杠杆",
    ("inventory_gap", "hit"): "库存",
    ("inventory_gap", "watch"): "库存",
    ("margin_improve", "hit"): "毛利走弱",
    ("cashflow_pattern", "hit"): "失血",
    ("nonrecurring", "hit"): "非经常",
    ("other_receivable", "hit"): "体外",
    ("per_share", "hit"): "摊薄",
}


def _pattern_summary(checks: list[dict[str, Any]]) -> str:
    """把命中的检查拼成一句组合定性（手册第 6 步：单一指标不足以定性）。"""
    tags = {c.get("tag") for c in checks
            if c.get("tag") and c.get("status") in ("hit", "watch")}
    hits = [c for c in checks if c.get("status") == "hit"]
    if not tags and not hits:
        return ""
    rules = [
        ({"赊销", "现金弱"}, "疑似赊销冲量：收入靠放宽账期换来，现金没跟上"),
        ({"短债", "加杠杆"}, "借钱垫资：短债覆盖不住，还在加杠杆"),
        ({"借钱扩产"}, "借钱扩产：2~3 年后折旧压利润"),
        ({"失血"}, "经营现金流为负，靠变卖或融资维持"),
        ({"库存", "毛利走弱"}, "库存积压 + 毛利率走弱，注意降价去库"),
        ({"非经常", "体外"}, "利润靠非经常性 + 资金体外循环，需查关联方"),
        ({"摊薄"}, "股本扩张但每股指标未增，股东价值被摊薄"),
        ({"短债"}, "短债覆盖不足，先看现金能不能撑过一年"),
    ]
    phrases: list[str] = []
    for need, phrase in rules:
        if need <= tags and phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= 2:
            break
    if not phrases:
        names = [c.get("name") or c["key"] for c in hits]
        return ("命中 " + "、".join(names[:3])) if names else ""
    return " + ".join(phrases)


def _fatal(data: dict[str, Any], checks: list[dict[str, Any]]) -> list[str]:
    """致命项：只有下面 4 条会把结论直接打成“回避”。

    0.8.0 新增的现金短债比 / 净现比只做「命中后在结论行点名」，不升级为致命，
    否则会把“借钱但周转正常”的公司一刀切。
    """
    latest = _latest(data)
    fatal: list[str] = []
    if latest.get("equity") is not None and latest["equity"] <= 0:
        fatal.append("净资产为负")
    fin, ebit = latest.get("finance_expense"), latest.get("ebit")
    if fin is not None and fin > 0 and ebit is not None and ebit / fin < config.INTEREST_COVER_FATAL:
        fatal.append("利息保障 < 1")
    gw, eq = latest.get("goodwill"), latest.get("equity")
    if gw is not None and eq and gw / eq > config.GOODWILL_EQUITY_FATAL:
        fatal.append(f"商誉/净资产超过 {config.GOODWILL_EQUITY_FATAL * 100:.0f}%")
    # 必须真有 3 个年报且 3 年 OCF 都为负，才谈得上「连续 3 年」：
    # 旧写法 `_years(data)[-3:]` 在只有 2 年时切片仍非空，会把 2 年说成 3 年。
    ocf_3y = [y.get("ocf") for y in _years(data)[-3:]]
    if (len(ocf_3y) >= 3 and all(v is not None and v < 0 for v in ocf_3y)
            and latest.get("ebit") and latest.get("debt") is not None
            and latest.get("cash") is not None):
        if (latest["debt"] - latest["cash"]) / latest["ebit"] > config.FATAL_NET_DEBT_EBIT:
            fatal.append(f"连续 {config.FCF_NEGATIVE_YEARS} 年经营现金流为负且净负债/EBIT > {config.FATAL_NET_DEBT_EBIT:g}")
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
    # financials.annual 是「最新在前」的降序列表，基数必须取 annual[0]；
    # 取 annual[-1] 会退到最早一年：年数被拉长、且用更小的旧基数，成长股增速会被高估。
    base = annual[0] if annual else {}
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
        # 口径日 PE 为负时 current_pe 是 None，但不能说「缺少」——数据是有的，只是不可用
        chart = ((data.get("valuation") or {}).get("chart") or {})
        if m["current_pe"] is None and chart.get("pe_negative_latest"):
            pe_raw = "口径日 PE 为负，不参与"
    growth_raw = (f"未来 {m['growth_count']} 年均值 {m['growth']:+.1f}%"
                  if m["growth"] is not None else m["growth_reason"])

    parts = [
        {"key": "target_upside", "label": config.VALUATION_WEIGHT_TEXT["target_upside"], "score": target_score,
         "max": config.VALUATION_WEIGHTS["target_upside"], "raw": target_raw},
        {"key": "forecast_pe", "label": config.VALUATION_WEIGHT_TEXT["forecast_pe"], "score": pe_score,
         "max": config.VALUATION_WEIGHTS["forecast_pe"], "raw": pe_raw},
        {"key": "profit_growth", "label": config.VALUATION_WEIGHT_TEXT["profit_growth"], "score": growth_score,
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
    na_items = [c for c in checks if c.get("status") == "na"]
    known = total - len(unknown_items) - len(na_items)
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
        "risk_na": len(na_items),
        "critical_unknown": critical_unknown,
        "institution_coverage": coverage,
        "q_coverage": round(q_coverage, 1),
        "buy_blockers": blockers,
    }


def _gate_level(risks: dict[str, Any]) -> str | None:
    """闸门会把买入类结论压到哪一档：'avoid' / 'watch' / None（不触发）。

    单独抽出来是因为报告要写一句“有没有触发降级”：结论本身已经是回避时，
    命中数可能已经过了线，这时要说明“已达降级线但结论不是买入类”，
    而不是含糊地写“未触发”。
    """
    checks = risks.get("checks") or []
    hits = [c for c in checks if c.get("status") == "hit"]
    watches = [c for c in checks if c.get("status") == "watch"]
    if any(c.get("key") in config.RISK_HEADLINE_KEYS for c in hits) or len(hits) >= 2:
        return "avoid"
    if len(watches) >= 2 or len(hits) == 1:
        return "watch"
    return None


def _risk_gate(result: dict[str, Any], risks: dict[str, Any]) -> dict[str, Any] | None:
    """决策矩阵的一致性闸门（0.9.0）：第二节的信号必须在结论层生效。

    Q 是连续打分，第二节是阈值判定，同一科目可能在 Q 里扣分、又在第二节命中。
    结论取两者中更谨慎的一方，因此买入类结论要能被第二节否掉：

    - 命中 ≥2 项，或一票否决位（现金流质量 / 现金短债比）命中 → 降为回避；
    - 提示 ≥2 项，或命中 1 项 → 降为「观察，第二节有信号」；
    - 命中的项多到一定程度时理由里点名，读者能直接回第二节核对。

    只在**买入方向**生效：太贵、回避这些负面结论本来就更谨慎，不需要再降一次，
    也避免“数据缺失”被变成“更保守等于更好”（数据不足仍走 buy_blockers 的老规则）。
    """
    if result.get("key") not in config.BUY_KEYS:
        return None
    checks = risks.get("checks") or []
    hits = [c for c in checks if c.get("status") == "hit"]
    watches = [c for c in checks if c.get("status") == "watch"]
    headline = [c for c in hits if c.get("key") in config.RISK_HEADLINE_KEYS]
    level = _gate_level(risks)

    def _names(items: list[dict[str, Any]], limit: int = 3) -> str:
        names = [c.get("name") or c.get("key") for c in items]
        more = f" 等 {len(names)} 项" if len(names) > limit else ""
        return "、".join(names[:limit]) + more

    if level == "avoid":
        if headline:
            reason = f"第二节一票否决位命中（{_names(headline)}）"
            if len(hits) > len(headline):
                reason += f"，另有 {len(hits) - len(headline)} 项命中"
        else:
            reason = f"第二节命中 {len(hits)} 项（{_names(hits)}）"
        return {"key": "avoid", "label": "回避", "hits": len(hits), "watches": len(watches),
                "note": f"第二节：命中 {len(hits)} 项、提示 {len(watches)} 项 → 买入类结论降级为回避",
                "reason": f"{reason}，按质量与估值本可「{result['label']}」，"
                          f"但风险信号未消化，结论降为回避"}
    if level == "watch":
        part = []
        if hits:
            part.append(f"命中 {len(hits)} 项（{_names(hits)}）")
        if watches:
            part.append(f"提示 {len(watches)} 项")
        return {"key": "watch", "label": "观察，第二节有信号",
                "hits": len(hits), "watches": len(watches),
                "note": f"第二节：{'、'.join(part)} → 买入类结论降级为观察",
                "reason": f"第二节{'、'.join(part)}，按质量与估值本可「{result['label']}」，"
                          f"先看第二节原文再决定"}
    return None


def _decision(q: dict[str, Any], v: dict[str, Any], fatal: list[str],
              data_quality: dict[str, Any], risks: dict[str, Any] | None = None) -> dict[str, Any]:
    """质量调整后的估值门槛：Q 越低，要求的 V 越高；Q<45 禁止买入。

    0.9.0 起多一道一致性闸门：矩阵给出买入类结论后，还要过一遍第二节的命中/提示。
    `risks` 单独传而不是塞进 `buy_blockers`——否则读者分不清“没算出来”和“算出来不好”。
    """
    qs, vs = q.get("score"), v.get("score")
    if fatal:
        return {"key": "avoid", "label": "回避", "reason": "出现致命风险：" + "；".join(fatal)}
    if qs is None or vs is None:
        return {"key": "unknown", "label": "数据不足，不下结论", "reason": "质量分或估值分无法计算"}

    if qs < config.QUALITY_HARD_FLOOR:
        return {"key": "avoid", "label": "回避", "reason": f"质量分 {qs:.1f} 低于 {config.QUALITY_HARD_FLOOR:.0f}，禁止买入"}

    # 矩阵在 config.DECISION_MATRIX：先按 Q 落档，再按 V 落格
    result: dict[str, Any] | None = None
    for tier in config.DECISION_MATRIX:
        if qs < tier["q_min"]:
            continue
        for rule in tier["rules"]:
            if rule["v_min"] is None or vs >= rule["v_min"]:
                result = {"key": rule["key"], "label": rule["label"], "reason": rule["reason"]}
                break
        break
    if result is None:      # 矩阵没覆盖到的 Q（低于最低档）：只有改坏 config 才会到这里
        return {"key": "avoid", "label": "回避", "reason": f"质量分 {qs:.1f} 超出决策矩阵覆盖范围"}

    # 闸门先于数据完整性：命中两项的“回避”比“数据不全”的“观察”更重，不能被后者盖掉
    gate = _risk_gate(result, risks or {})
    if gate:
        return gate

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
    price = (data.get("meta") or {}).get("price")
    if target and price:
        upside = (target / price - 1) * 100
        if upside > 30 and (v.get("score") is not None and v["score"] < 60):
            flags.append(f"机构目标价较现价高 {upside:.1f}%，但规则估值分仅 {v['score']:.0f}，两者分歧较大。")
    if nxt and nxt["net_profit_yoy"] < 0:
        pe = ((data.get("valuation") or {}).get("metrics") or {}).get("pe") or {}
        if pe.get("percentile") is not None and pe["percentile"] < 30:
            flags.append("机构预测净利下滑，而当前 PE 分位很低，低估值可能已反映盈利下修。")
    return flags



def _moat(data: dict[str, Any]) -> dict[str, Any]:
    """护城河：只看量化证据，不写行业故事，也不给 0~100 分。

    三条证据（手册 8.2）：定价权、资本回报、现金创造。
    3 条成立 = 宽护城河；2 条 = 窄；≤1 条 = 无明显护城河。
    """
    if _is_financial(data):
        return {"level": "不适用", "evidence": [], "reasons": ["金融股口径不适用"], "not_applicable": True}
    ys = _years(data)
    if len(ys) < 3:
        return {"level": "数据不足", "evidence": [], "reasons": ["年报不足 3 年，无法判断持续性"]}

    gm = [y.get("gross_margin") for y in ys if y.get("gross_margin") is not None]
    roic = [y.get("roic") for y in ys if y.get("roic") is not None]
    fcfm = [y.get("fcf_margin") for y in ys if y.get("fcf_margin") is not None]

    gm_med, gm_std = median(gm), stdev(gm)
    ok1 = (gm_med is not None and gm_std is not None
           and gm_med >= config.MOAT_GROSS_MARGIN_MIN and gm_std <= config.MOAT_GROSS_MARGIN_STD)
    ev1 = {"name": "定价权", "ok": ok1,
           "detail": (f"毛利率 {_p(gm_med)}（5 年 σ {_n(gm_std)}pct）"
                      f"，要求 ≥ {config.MOAT_GROSS_MARGIN_MIN:.0f}% 且 σ ≤ {config.MOAT_GROSS_MARGIN_STD:.0f}pct")}

    roic_med = median(roic)
    spread = (roic_med - config.WACC) if roic_med is not None else None
    above = sum(1 for v in roic if v > config.WACC)
    need_above = min(config.MOAT_ROIC_ABOVE_YEARS, len(roic)) if roic else 0
    ok2 = (spread is not None and spread >= config.MOAT_ROIC_SPREAD_MIN and above >= need_above)
    ev2 = {"name": "资本回报", "ok": ok2,
           "detail": (f"ROIC {_p(roic_med)} vs WACC {config.WACC:.1f}%（{spread:+.1f}pct，{above}/{len(roic)} 年高于 WACC）"
                      if spread is not None else "ROIC 数据不足")}

    fcf_med = (median(fcfm) * 100.0) if fcfm else None
    neg = sum(1 for v in fcfm if v <= 0)
    ok3 = (fcf_med is not None and fcf_med >= config.MOAT_FCF_MARGIN_MIN and neg <= 1)
    ev3 = {"name": "现金创造", "ok": ok3,
           "detail": (f"FCF/营收 {_p(fcf_med)}，{len(fcfm)} 年中 {neg} 年为负"
                      f"，要求 ≥ {config.MOAT_FCF_MARGIN_MIN:.0f}% 且负年数 ≤ 1"
                      if fcf_med is not None else "FCF 数据不足")}

    evidence = [ev1, ev2, ev3]
    met = sum(1 for e in evidence if e["ok"])
    level = "宽护城河" if met == 3 else ("窄护城河" if met == 2 else "无明显护城河")
    reasons = [f"{'✅' if e['ok'] else '❌'} {e['name']}：{e['detail']}" for e in evidence]
    return {"level": level, "evidence": evidence, "reasons": reasons, "met": met,
            "total": len(evidence)}


def _tracking(data: dict[str, Any], q: dict[str, Any]) -> list[dict[str, str]]:
    latest = _latest(data)
    ys = _years(data)
    items = []
    spread = None
    roic = median([y.get("roic") for y in ys])
    if roic is not None:
        spread = roic - config.WACC
    items.append({"metric": "ROIC−WACC", "current": _p(spread), "threshold": "> 0", "frequency": "每年"})
    # 与第二节检查 1 同口径（TTM）、同阈值（CASH_NI_OK），不再单独维护一个 0.8 的跟踪线
    cash_ni = div(latest.get("ocf_ttm") or latest.get("ocf"),
                  latest.get("np_ttm") or latest.get("net_profit"))
    items.append({"metric": "CFO/净利润(TTM)", "current": _n(cash_ni),
                  "threshold": f"≥ {config.CASH_NI_OK:.1f}", "frequency": "每季"})
    nd = (latest.get("debt") - latest.get("cash")) if latest.get("debt") is not None and latest.get("cash") is not None else None
    items.append({"metric": "净有息负债/EBIT", "current": _n(div(nd, latest.get("ebit"))),
                  "threshold": f"≤ {config.NET_DEBT_EBIT_MAX:.0f}", "frequency": "每季"})
    items.append({"metric": "商誉/净资产", "current": _p(div(latest.get("goodwill"), latest.get("equity")) * 100 if latest.get("goodwill") is not None and latest.get("equity") else None),
                  "threshold": f"≤ {config.GOODWILL_EQUITY_WATCH * 100:.0f}%", "frequency": "每半年"})
    items.append({"metric": "营收增速", "current": _p(div((latest.get("revenue") or 0) - (_prev(data).get("revenue") or 0), _prev(data).get("revenue")) * 100 if _prev(data).get("revenue") else None),
                  "threshold": "> 0，且应收/存货不异常加速", "frequency": "每季"})
    pe = ((data.get("valuation") or {}).get("metrics") or {}).get("pe") or {}
    # percentile 可能是 None（口径日 PE 为负/缺失 → 该指标本次不可用）：
    # 直接用 pe.get('percentile', '—') 会打成「None%」，这里必须显式判 None。
    pe_pct = pe.get("percentile")
    items.append({"metric": "PE 分位", "current": f"{pe_pct}%" if pe_pct is not None else "—",
                  "threshold": "< 80%", "frequency": "每月"})
    items.append({"metric": "机构一致预期", "current": f"{len((data.get('forecast') or {}).get('forecasts') or [])} 个年度",
                  "threshold": "不下修、不空覆盖", "frequency": "每季"})
    return items


def _is_financial(data: dict[str, Any]) -> bool:
    industry = str((data.get("meta") or {}).get("industry") or "")
    return any(k in industry for k in config.FINANCIAL_INDUSTRY_KEYWORDS)


def compute_scores(data: dict[str, Any]) -> dict[str, Any]:
    financial = _is_financial(data)
    q = _quality(data)
    v = _valuation_score(data)
    if financial:
        # 银行/保险/证券：FCF、速动比率、有息负债口径都不可比，打分只会得出“低质量”的假象。
        q = {"score": None, "grade": "金融股不适用", "groups": [], "coverage": 0.0,
             "not_applicable": True}
        v = {"score": None, "grade": "金融股不适用", "parts": [], "coverage": 0.0,
             "not_applicable": True}
    checks = _risk_checks(data)
    fatal = _fatal(data, checks)
    hits = [c for c in checks if c["status"] == "hit"]
    watches = [c for c in checks if c["status"] == "watch"]
    risks = {
        "checks": checks,
        "fatal": fatal,
        "hits": len(hits),
        "watches": len(watches),
        "unknown": sum(1 for c in checks if c["status"] == "unknown"),
        "clears": sum(1 for c in checks if c["status"] == "clear"),
        "headline": [c["name"] for c in checks
                     if c["key"] in config.RISK_HEADLINE_KEYS and c["status"] in ("hit", "watch")],
        "summary": _pattern_summary(checks),
    }
    # 报告第四节要写“有没有触发降级”，这里先算好，避免 render 再抄一遍阈值
    risks["gate_level"] = _gate_level(risks)
    data_quality = _data_quality(data, q, checks)
    if financial:
        data_quality["buy_blockers"] = ["金融股不适用：FCF / 速动比率 / 有息负债口径不可比"]
    decision = _decision(q, v, fatal, data_quality, risks)
    if financial:
        decision = {
            "key": "unknown",
            "label": "金融股不适用，不做初筛",
            "reason": "银行/保险/证券的 FCF、速动比率与有息负债口径与工商企业不可比，"
                      "本工具不输出 Q/V 结论；请看第二节的风险检查原文",
        }
    data["quality"] = q
    data["moat"] = _moat(data)
    data["valuation_score"] = v
    data["risks"] = risks
    data["data_quality"] = data_quality
    data["decision"] = decision
    data["flags"] = _expectation_flags(data, v)
    data["tracking"] = _tracking(data, q)
    return data
