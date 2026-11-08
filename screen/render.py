# -*- coding: utf-8 -*-
"""单文件 HTML 渲染：五节，无外部资源，不生成 JSON/Markdown。"""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any

import config

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "report.html"


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def n(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return esc(value)


def pct(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return esc(value)


def yi(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) / 1e8:,.{digits}f}"
    except (TypeError, ValueError):
        return esc(value)


def _status(status: str) -> str:
    label = {"hit": "命中", "clear": "通过", "unknown": "数据不足"}.get(status, status)
    return f'<span class="status {esc(status)}">{esc(label)}</span>'


def _score_class(value: float | None) -> str:
    if value is None:
        return ""
    return "good" if value >= 65 else ("bad" if value < 45 else "")


def _bar(value: float | None, cls: str = "") -> str:
    v = 0 if value is None else max(0, min(100, float(value)))
    return f'<div class="scorebar {cls}"><i style="width:{v:.1f}%"></i></div>'


def _line_chart(points: list[dict[str, Any]], series: list[dict[str, Any]], *,
                height: int = 220, y_min: float | None = None, y_max: float | None = None,
                y_fmt=None, value_fmt=None, x_labels: int = 7, dots: bool = False,
                bands: list[tuple[int, int]] | None = None, mark_latest: bool = True,
                aria_label: str = "", legend: bool = True) -> str:
    """轻量 SVG 折线图：无 JS、无外部资源，缺失值断线。"""
    if not points:
        return '<p class="small">暂无图表数据。</p>'
    keys = [s["key"] for s in series]
    values = [p.get(k) for p in points for k in keys if p.get(k) is not None]
    if not values:
        return '<p class="small">暂无可绘制的数值。</p>'

    y_fmt = y_fmt or (lambda v: n(v, 2))
    value_fmt = value_fmt or (lambda v: n(v, 2))
    lo, hi = min(values), max(values)
    if y_min is not None:
        lo = min(lo, y_min)
    if y_max is not None:
        hi = max(hi, y_max)
    if hi <= lo:
        hi = lo + 1.0
    span = hi - lo
    if y_min is None:
        lo -= span * 0.05
    if y_max is None:
        hi += span * 0.05
    if hi <= lo:
        hi = lo + 1.0

    width, left, right, top, bottom = 720, 52, 48, 14, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    last = len(points) - 1

    def x(i: int) -> float:
        return left + (plot_w * i / last if last else plot_w / 2)

    def y(v: float) -> float:
        return top + (hi - v) / (hi - lo) * plot_h

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
             f"<title>{esc(aria_label)}</title>"]
    for start, end in bands or []:
        start, end = max(0, start), min(last, end)
        if end < start:
            continue
        x1, x2 = x(start), x(end)
        parts.append(f'<rect class="band" x="{x1:.1f}" y="{top}" width="{max(3.0, x2 - x1):.1f}" '
                     f'height="{plot_h}" />')
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        yy = y(v)
        parts.append(f'<line class="grid" x1="{left}" y1="{yy:.1f}" x2="{width - right}" y2="{yy:.1f}" />')
        parts.append(f'<text class="tick" x="{left - 8}" y="{yy + 4:.1f}" text-anchor="end">{esc(y_fmt(v))}</text>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" />')

    for s in series:
        path: list[str] = []
        started = False
        for i, point in enumerate(points):
            v = point.get(s["key"])
            if v is None:
                started = False
                continue
            path.append(f'{"M" if not started else "L"}{x(i):.1f},{y(v):.1f}')
            started = True
        if path:
            dash = ' stroke-dasharray="5 4"' if s.get("dash") else ""
            parts.append(f'<path d="{" ".join(path)}" fill="none" stroke="{s["color"]}" '
                         f'stroke-width="1.8"{dash} />')
        if dots:
            for i, point in enumerate(points):
                v = point.get(s["key"])
                if v is not None:
                    parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.6" fill="{s["color"]}" />')

    if mark_latest and points:
        for s in series:
            v = points[-1].get(s["key"])
            if v is None:
                continue
            x_last, y_last = x(last), y(v)
            parts.append(f'<line class="latest-line" x1="{x_last:.1f}" y1="{top}" '
                         f'x2="{x_last:.1f}" y2="{top + plot_h}" />')
            parts.append(f'<circle cx="{x_last:.1f}" cy="{y_last:.1f}" r="4" fill="{s["color"]}" '
                         f'stroke="#fff" stroke-width="1.5" />')
            anchor = "end" if x_last > left + plot_w * 0.72 else "start"
            tx = x_last - 7 if anchor == "end" else x_last + 7
            ty = max(top + 10, min(top + plot_h - 2, y_last - 8))
            parts.append(f'<text class="latest" x="{tx:.1f}" y="{ty:.1f}" '
                         f'text-anchor="{anchor}" fill="{s["color"]}">{esc(value_fmt(v))}</text>')

    label_count = min(x_labels, len(points))
    if label_count <= 1:
        indices = [0]
    else:
        indices = sorted({round(i * last / (label_count - 1)) for i in range(label_count)})
    for i in indices:
        label = str(points[i].get("label") or points[i].get("date") or "")[:7]
        parts.append(f'<text class="tick" x="{x(i):.1f}" y="{height - 8}" text-anchor="middle">'
                     f'{esc(label)}</text>')
    parts.append("</svg>")

    legend_html = ""
    if legend:
        items = "".join(
            f'<span><i style="background:{s["color"]}"></i>{esc(s["label"])}</span>' for s in series
        )
        legend_html = f'<div class="chart-legend">{items}</div>'
    return f'<div class="chart">{legend_html}{"".join(parts)}</div>'


def _negative_bands(points: list[dict[str, Any]]) -> list[tuple[int, int]]:
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for i, point in enumerate(points):
        if point.get("pe_negative"):
            if start is None:
                start = i
        elif start is not None:
            bands.append((start, i - 1))
            start = None
    if start is not None:
        bands.append((start, len(points) - 1))
    return bands


def _margin_chart(trend: dict[str, Any]) -> str:
    points = trend.get("points") or []
    if not points:
        return ('<h3>近 15 个季度利润率趋势</h3>'
                '<p class="small">暂无季度利润表数据。</p>')
    latest = points[-1]
    series = [
        {"key": "gross", "label": "毛利率", "color": "#1f5f8b"},
        {"key": "net", "label": "净利率（归母）", "color": "#1f7a4d"},
    ]
    first_label = esc(points[0].get("label"))
    last_label = esc(latest.get("label"))
    note = (f"覆盖 {first_label}–{last_label}，共 {len(points)} 个季度；"
            f"最新 {last_label}：毛利率 {pct(latest.get('gross'))} / "
            f"净利率（归母） {pct(latest.get('net'))}")
    if len(points) < config.TREND_QUARTERS:
        note += f"；少于 {config.TREND_QUARTERS} 个季度"
    chart = _line_chart(
        points, series, height=240, y_min=0.0, y_max=100.0,
        y_fmt=lambda v: pct(v, 0), value_fmt=lambda v: pct(v, 1),
        x_labels=config.TREND_QUARTERS, dots=True, mark_latest=False,
        aria_label="近 15 个季度毛利率和净利率",
    )
    return (
        "<h3>近 15 个季度利润率趋势</h3>"
        '<p class="small">单季口径；净利率为归母口径；季度数据未经审计。</p>'
        f"{chart}<p class=\"small\">{note}</p>"
    )


def _valuation_charts(chart: dict[str, Any]) -> str:
    points = chart.get("points") or []
    if not points:
        return '<p class="small">暂无近 15 个季度估值数据。</p>'
    specs = [
        ("pe", "PE(TTM)", "#1f5f8b"),
        ("pb", "PB(MRQ)", "#1f7a4d"),
        ("ps", "PS(TTM)", "#9a6700"),
    ]
    latest_map = chart.get("latest") or {}
    panels = []
    for key, label, color in specs:
        latest = latest_map.get(key)
        if latest:
            note = f"最新 {latest.get('date')}：{n(latest.get('value'))}"
        elif key == "pe" and chart.get("pe_negative_latest"):
            note = f"最新 {points[-1].get('date')}：PE 为负，不适用"
        else:
            note = f"最新 {points[-1].get('date')}：数据缺失"
        bands = _negative_bands(points) if key == "pe" else []
        panel = _line_chart(
            points, [{"key": key, "label": label, "color": color}],
            height=200, y_fmt=lambda v: n(v, 2), value_fmt=lambda v: n(v, 2),
            x_labels=6, mark_latest=True, bands=bands,
            aria_label=f"近 15 个季度 {label} 走势", legend=False,
        )
        panels.append(
            f'<div class="chart-panel"><h4>{esc(label)}</h4>{panel}'
            f'<p class="small">{esc(note)}</p></div>'
        )
    start, end = chart.get("start") or "—", chart.get("end") or "—"
    return (
        '<div class="chart-grid">' + "".join(panels) + "</div>"
        f'<p class="small">数据范围：{esc(start)} 至 {esc(end)}；周频；'
        "灰色区间为 PE 为负（亏损），该区间不连线。分位表仍按全部可用历史计算。</p>"
    )


def _section_business(data: dict[str, Any]) -> str:
    meta = data["meta"]
    business = meta.get("business") or "暂无披露"
    if len(business) > 700:
        business = business[:700] + "…"
    annual = sorted(data["financials"].get("annual") or [], key=lambda x: x.get("year") or 0)[-5:]
    rows = []
    for y in annual:
        rows.append(
            "<tr>"
            f"<td>{esc(y.get('year'))}</td>"
            f"<td>{yi(y.get('revenue'))}</td>"
            f"<td>{yi(y.get('net_profit'))}</td>"
            f"<td>{pct(y.get('roe'))}</td>"
            f"<td>{pct(y.get('roic'))}</td>"
            f"<td>{yi(y.get('fcf'))}</td>"
            f"<td>{pct((y.get('fcf_margin') or 0) * 100 if y.get('fcf_margin') is not None else None)}</td>"
            f"<td>{pct(y.get('gross_margin'))}</td>"
            "</tr>"
        )
    mainop = data.get("mainop") or {}
    product_rows = []
    for p in mainop.get("products") or []:
        product_rows.append(
            "<tr>"
            f"<td>{esc(p.get('name'))}</td>"
            f"<td>{yi(p.get('revenue'))}</td>"
            f"<td>{pct(p.get('ratio_pct'))}</td>"
            f"<td>{pct(p.get('gross_margin'))}</td>"
            "</tr>"
        )
    product_table = ""
    if product_rows:
        product_table = f"""
  <h3>产品/业务结构（{esc(mainop.get('period') or '最新年报')}）</h3>
  <table>
    <thead><tr><th>产品/业务</th><th>营业收入（亿）</th><th>收入占比</th><th>毛利率</th></tr></thead>
    <tbody>{''.join(product_rows)}</tbody>
  </table>
  <p class="small">收入占比来自 F10 主营构成；毛利率 =（收入 − 成本）/ 收入。分类口径以公司年报为准。</p>
"""
    else:
        product_table = '<p class="small">产品/业务分部：暂无披露。</p>'
    moat = data.get("moat") or {}
    reasons = "".join(f"<li>{esc(x)}</li>" for x in moat.get("reasons") or [])
    margin_chart = _margin_chart(data["financials"].get("margin_trend") or {})
    return f"""
<section>
  <h2>一、生意本身</h2>
  <div class="kv">
    <div class="k">行业</div><div>{esc(meta.get('industry'))}</div>
    <div class="k">主营</div><div>{esc(business)}</div>
    <div class="k">最新报告期</div><div>{esc(meta.get('latest_date') or '—')}</div>
  </div>
  {product_table}
  <h3>护城河规则结论</h3>
  <div class="grid">
    <div class="metric"><div class="k">规则判定</div><div class="v">{esc(moat.get('level') or '数据不足')}</div>
      <div class="note">量化评分 {n(moat.get('score'), 1)} / 100</div></div>
  </div>
  <ul>{reasons or '<li>数据不足，暂不判断。</li>'}</ul>
  <h3>五年经营轨迹</h3>
  <table>
    <thead><tr><th>年度</th><th>营收（亿）</th><th>归母净利（亿）</th><th>ROE</th><th>ROIC</th><th>FCF（亿）</th><th>FCF/营收</th><th>毛利率</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="8">数据不足</td></tr>'}</tbody>
  </table>
  {margin_chart}
  <p class="small">只写主营、行业、五年量化轨迹和护城河规则结论；不含上下游、政策、管理层评价。</p>
</section>"""


def _section_risks(data: dict[str, Any]) -> str:
    risks = data.get("risks") or {}
    checks = risks.get("checks") or []
    hits = sum(1 for c in checks if c.get("status") == "hit")
    unknown = sum(1 for c in checks if c.get("status") == "unknown")
    rows = []
    for c in checks:
        rows.append(
            "<tr>"
            f"<td>{esc(c.get('name'))}</td>"
            f"<td>{_status(c.get('status', 'unknown'))}</td>"
            f"<td>{esc(c.get('detail'))}</td>"
            f"<td>{esc(c.get('severity'))}</td>"
            "</tr>"
        )
    fatal = risks.get("fatal") or []
    fatal_html = ""
    if fatal:
        fatal_html = '<div class="flags"><b>致命项</b><ul>' + "".join(f"<li>{esc(x)}</li>" for x in fatal) + "</ul></div>"
    return f"""
<section>
  <h2>二、经营质量与风险</h2>
  <p class="muted">10 项高信号检查，全部由同一批年报数据计算；未判定不当作通过。</p>
  <div class="grid">
    <div class="metric"><div class="k">检查项</div><div class="v">{len(checks)}</div><div class="note">命中 {hits} 项；数据不足 {unknown} 项</div></div>
    <div class="metric"><div class="k">风险状态</div><div class="v">{'有命中' if hits else '无命中'}</div><div class="note">命中不等于造假，只表示需要追问</div></div>
  </div>
  {fatal_html}
  <table>
    <thead><tr><th>检查</th><th>状态</th><th>计算/证据</th><th>严重度</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>"""


def _section_valuation(data: dict[str, Any]) -> str:
    val = data.get("valuation") or {}
    metrics = val.get("metrics") or {}
    sample = val.get("sample") or {}
    mrows = []
    for key in ("pe", "pb", "ps"):
        m = metrics.get(key)
        if not m:
            continue
        mrows.append(
            "<tr>"
            f"<td>{esc(m.get('label'))}</td>"
            f"<td>{n(m.get('current'))}</td>"
            f"<td>{pct(m.get('percentile'))}</td>"
            f"<td>{n(m.get('min'))} ~ {n(m.get('max'))}</td>"
            f"<td>{esc(m.get('points'))}</td>"
            "</tr>"
        )
    sample_note = "暂无历史估值样本"
    if sample:
        sample_note = f"{esc(sample.get('start'))} 至 {esc(sample.get('end'))}，{esc(sample.get('points'))} 个周样本"
    valuation_charts = _valuation_charts(val.get("chart") or {})

    fc = data.get("forecast") or {}
    frows = []
    for f in fc.get("forecasts") or []:
        frows.append(
            "<tr>"
            f"<td>{esc(f.get('year'))}E</td>"
            f"<td>{n(f.get('revenue_yi'))}</td>"
            f"<td>{n(f.get('net_profit_yi'))}</td>"
            f"<td>{n(f.get('eps'))}</td>"
            f"<td>{pct(f.get('net_profit_yoy'))}</td>"
            f"<td>{n(f.get('pe'))}</td>"
            "</tr>"
        )
    coverage = fc.get("coverage") or 0
    coverage_note = f"覆盖机构 {coverage} 家" if coverage else "覆盖机构数未披露"
    if coverage and coverage < 3:
        coverage_note += "；低于 3 家，预测参考价值有限"
    target = fc.get("target_price")
    price = data["meta"].get("price")
    target_note = "无目标价"
    if target:
        upside = ((target / price - 1) * 100) if price else None
        target_note = f"{n(target)} 元" + (f"（较现价 {pct(upside)}）" if upside is not None else "")
    rating = fc.get("rating") or {}
    rating_note = "暂无评级数据"
    if rating:
        rating_note = (f"买入 {rating.get('buy', 0)} 条、增持 {rating.get('increase', 0)} 条；"
                       f"评级记录 {rating.get('records', 0)} 条（不是机构数）")
    dcf = data.get("dcf") or {}
    dcf_rows = []
    if dcf.get("applicable"):
        dcf_rows = [
            ("FCF0（最近年报）", f"{n(dcf.get('fcf0_yi'))} 亿"),
            ("第一阶段增速 g1", pct(dcf.get("g1_pct"))),
            ("折现率 / 永续增速", f"{pct(dcf.get('wacc_pct'))} / {pct(dcf.get('g_pct'))}"),
            ("合理价", f"{n(dcf.get('fair_value'))} 元"),
            ("相对现价", pct(dcf.get("margin_pct"))),
        ]
    dcf_html = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in dcf_rows)

    flags = data.get("flags") or []
    flags_html = ""
    if flags:
        flags_html = '<div class="flags"><b>预期差提示</b><ul>' + "".join(f"<li>{esc(x)}</li>" for x in flags) + "</ul></div>"

    return f"""
<section>
  <h2>三、企业估值与机构预期</h2>
  <h3>历史估值分位</h3>
  <p class="small">样本：{sample_note}。分位按自身历史，不与同业混用；PE 为负时不采用 PE。</p>
  <table>
    <thead><tr><th>指标</th><th>当前</th><th>历史分位</th><th>区间</th><th>样本点数</th></tr></thead>
    <tbody>{''.join(mrows) or '<tr><td colspan="5">暂无历史估值数据</td></tr>'}</tbody>
  </table>

  <h3>近 15 个季度估值走势（周频）</h3>
  {valuation_charts}

  <h3>机构未来盈利预期</h3>
  <p class="small">{esc(coverage_note)}。预测净利与营收单位为亿元；预测不是事实。</p>
  <table>
    <thead><tr><th>年度</th><th>预测营收（亿）</th><th>预测归母（亿）</th><th>预测 EPS</th><th>净利同比</th><th>对应 PE</th></tr></thead>
    <tbody>{''.join(frows) or '<tr><td colspan="6">暂无机构覆盖</td></tr>'}</tbody>
  </table>
  <div class="grid">
    <div class="metric"><div class="k">机构目标价</div><div class="v">{target_note}</div><div class="note">目标价 ≠ 本报告合理价</div></div>
    <div class="metric"><div class="k">评级分布</div><div class="v" style="font-size:14px">{esc(rating_note)}</div><div class="note">评级记录条数不等于覆盖机构数</div></div>
  </div>

  <h3>本报告的估值</h3>
  <table><tbody>{dcf_html or '<tr><td>DCF</td><td>不适用：' + esc(dcf.get('reason') or '数据不足') + '</td></tr>'}</tbody></table>
  <p class="small">FCF 收益率：{pct(data['meta'].get('fcf_yield'))}；要求收益率 {pct(config.REQUIRED_FCF_YIELD)}。</p>
  {flags_html}
</section>"""


def _section_score(data: dict[str, Any]) -> str:
    q = data.get("quality") or {}
    v = data.get("valuation_score") or {}
    decision = data.get("decision") or {}
    confidence = data.get("confidence")
    qs, vs = q.get("score"), v.get("score")

    qrows = []
    for g in q.get("groups") or []:
        qrows.append(
            "<tr>"
            f"<td>{esc(g.get('label'))}</td>"
            f"<td>{n(g.get('score'), 1)} / {n(g.get('max'), 0)}</td>"
            f"<td>{pct(g.get('coverage'))}</td>"
            "</tr>"
        )
    vrows = []
    for part in v.get("parts") or []:
        vrows.append(
            "<tr>"
            f"<td>{esc(part.get('label'))}</td>"
            f"<td>{n(part.get('score'), 1)}</td>"
            f"<td>{esc(part.get('raw'))}</td>"
            "</tr>"
        )
    key = decision.get("key", "unknown")
    return f"""
<section>
  <h2>四、综合评分</h2>
  <div class="grid">
    <div class="metric"><div class="k">质量分 Q</div><div class="v">{n(qs, 1)}</div><div class="note">{esc(q.get('grade'))}</div>
      {_bar(qs, _score_class(qs))}</div>
    <div class="metric"><div class="k">估值分 V</div><div class="v">{n(vs, 1)}</div><div class="note">{esc(v.get('grade'))}</div>
      {_bar(vs, _score_class(vs))}</div>
    <div class="metric"><div class="k">置信度</div><div class="v">{n(confidence, 0)}</div><div class="note">年报、估值样本、字段完整度</div>
      {_bar(confidence)}</div>
    <div class="metric"><div class="k">结论</div><div class="v" style="font-size:19px">{esc(decision.get('label'))}</div>
      <div class="note">{esc(decision.get('reason'))}</div></div>
  </div>
  <h3>质量分构成</h3>
  <table><thead><tr><th>维度</th><th>得分</th><th>数据覆盖</th></tr></thead><tbody>{''.join(qrows)}</tbody></table>
  <h3>估值分构成</h3>
  <table><thead><tr><th>维度</th><th>得分 / 100</th><th>原始值</th></tr></thead><tbody>{''.join(vrows)}</tbody></table>
  <div class="small">
    决策规则：Q≥75 且 V≥65 → 可买；Q≥75 且 V 45~65 → 等价格；Q≥75 且 V&lt;45 → 太贵；
    Q 55~75 → 观察；Q&lt;55 或致命项 → 回避；置信度&lt;60 → 不下结论。
  </div>
  <p class="small">机构预期只做“预期差提示”，不直接加减 Q/V 分数。</p>
</section>"""


def _section_tracking(data: dict[str, Any]) -> str:
    rows = []
    for item in data.get("tracking") or []:
        rows.append(
            "<tr>"
            f"<td>{esc(item.get('metric'))}</td>"
            f"<td>{esc(item.get('current'))}</td>"
            f"<td>{esc(item.get('threshold'))}</td>"
            f"<td>{esc(item.get('frequency'))}</td>"
            "</tr>"
        )
    return f"""
<section>
  <h2>五、后续跟踪</h2>
  <p class="muted">由本次评分和阈值自动生成；后续只需核对是否越线。</p>
  <table><thead><tr><th>指标</th><th>当前值</th><th>阈值</th><th>频率</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
</section>"""


def render_html(data: dict[str, Any]) -> str:
    meta = data["meta"]
    decision = data.get("decision") or {}
    key = decision.get("key", "unknown")
    price = meta.get("price")
    price_text = f"¥ {n(price)}" if price is not None else "价格未取得"
    title = f"{meta.get('name')}（{meta.get('code')}）企业质量初筛"
    content = f"""
<div class="hero">
  <h1>{esc(meta.get('name'))} <span style="font-size:15px;opacity:.75">{esc(meta.get('code'))}</span>
    <span class="badge {esc(key)}">{esc(decision.get('label'))}</span></h1>
  <div class="sub">{esc(meta.get('industry'))} · 企业质量初筛 · 只做定量判断</div>
  <div class="price">{price_text}<span style="font-size:13px;font-weight:400;opacity:.8;margin-left:10px">市值 {n(meta.get('market_cap_yi'))} 亿元</span></div>
  <div class="meta">行情日期 {esc(meta.get('quote_date') or '—')} · 最新报告期 {esc(meta.get('latest_date') or '—')} · 生成 {datetime.now():%Y-%m-%d %H:%M}</div>
</div>
{_section_business(data)}
{_section_risks(data)}
{_section_valuation(data)}
{_section_score(data)}
{_section_tracking(data)}
"""
    template = TEMPLATE.read_text(encoding="utf-8")
    sources = ("腾讯自选股 WeStock：data_profile / data_quote / data_finance / data_consensus / data_rating；"
               "东方财富：RPT_F10_FN_MAINOP 产品分部、RPT_VALUEANALYSIS_DET 历史估值、"
               "RPT_F10_FINANCE_GCASHFLOW 资本支出。")
    method = ("质量分 Q：资本回报 30、现金创造力 25、资产负债表 20、成长与稳定 15、会计质量 10；"
              "估值分 V：历史分位 50、FCF 收益率 30、DCF 折价 20。权重与阈值见 config.py。")
    limits = ("年报不足 5 年、机构覆盖不足 3 家、估值样本过短时，结论会降级；"
              "金融股与强周期股不适合直接套用 FCF/DCF。")
    disclaimer = ("本报告由规则程序生成，仅供初筛和后续研究参考，不构成投资建议。"
                  f"程序版本 {config.VERSION}。")
    html_text = template
    for token, value in {
        "{{TITLE}}": esc(title),
        "{{CONTENT}}": content,
        "{{METHOD}}": esc(method),
        "{{SOURCES}}": esc(sources),
        "{{LIMITS}}": esc(limits),
        "{{DISCLAIMER}}": esc(disclaimer),
    }.items():
        html_text = html_text.replace(token, value)
    return html_text
