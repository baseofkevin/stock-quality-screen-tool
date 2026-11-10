# -*- coding: utf-8 -*-
"""单文件 HTML 渲染：五节，无外部资源，不生成 JSON/Markdown。"""
from __future__ import annotations

import html
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
    label = {"hit": "命中", "watch": "提示", "clear": "通过",
             "unknown": "数据不足", "na": "不适用"}.get(status, status)
    return f'<span class="status {esc(status)}">{esc(label)}</span>'


def _bargain_verdict(bargain: float | None, cl_ratio: float | None) -> str:
    if bargain is None:
        return ""
    if bargain >= config.PAYABLE_SLIP_STRONG:
        return "两头通吃"
    if bargain >= config.PAYABLE_SLIP_WEAK:
        return "正常占款"
    if cl_ratio is not None and cl_ratio >= 2.0:
        return "预收型强势"
    return "几乎不占供应商款"


def _structure_line(structure: dict[str, Any], financial: bool = False) -> str:
    """五年轨迹下方一行：货款占用（议价权）+ 合同负债/营收。"""
    bargain = structure.get("bargain_latest")
    trend = structure.get("bargain_trend")
    cl_ratio = structure.get("contract_latest")
    cl_yoy = structure.get("contract_yoy")
    if financial:
        return '<p class="small">货款占用（议价权）：金融股无应付账款/存货口径，不适用。</p>'
    if bargain is None and cl_ratio is None:
        return '<p class="small">货款占用（议价权）/ 合同负债：数据不足。</p>'
    parts = []
    if bargain is None:
        parts.append("货款占用 应付/（应收+票据+存货）= —")
    else:
        trend_txt = "—" if trend is None else f"三年 {trend:+.3f}"
        parts.append(f"货款占用 应付/（应收+票据+存货）= {bargain:.2f}（{trend_txt}）")
    if cl_ratio is not None:
        yoy_txt = "—" if cl_yoy is None else f"{cl_yoy:+.1f}%"
        parts.append(f"销售端 合同负债/营收 {cl_ratio:.2f}%（同比 {yoy_txt}）")
    verdict = _bargain_verdict(bargain, cl_ratio)
    tail = f" → {verdict}" if verdict else ""
    return ('<p class="small">' + "｜".join(parts) + esc(tail) + "</p>"
            '<p class="small">占款比 = 应付账款 ÷（应收账款 + 应收款项融资 + 存货）：'
            "&gt;1 两头通吃，&lt;0.3 几乎不占供应商款；"
            "要和合同负债一起读，只报占款比会漏掉「先款后货」型公司。</p>")


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


def _margin_chart(trend: dict[str, Any], improve: dict[str, Any] | None = None) -> str:
    title = f"近 {config.TREND_YEARS} 年季度毛利率/净利率趋势"
    badge = ""
    if improve:
        status = improve.get("status") or "unknown"
        cmp = improve.get("compare") or {}
        # badge 要回答「哪个指标、同比还是环比 没改善」，不再用一个笼统的「未改善」
        label = cmp.get("badge") or {"clear": "毛利率环比改善", "watch": "未改善", "hit": "环比走弱",
                                     "unknown": "数据不足", "na": "不适用"}.get(status, status)
        badge = f' <span class="status {esc(status)}">［{esc(label)}］</span>'
    points = trend.get("points") or []
    if not points:
        return (f'<h3>{esc(title)}{badge}</h3>'
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
        note += (f"；不足 {config.TREND_YEARS} 年"
                 f"（需 {config.TREND_QUARTERS} 个季度，已展示全部可用季度）")
    chart = _line_chart(
        points, series, height=240, y_min=0.0, y_max=100.0,
        y_fmt=lambda v: pct(v, 0), value_fmt=lambda v: pct(v, 1),
        x_labels=config.TREND_QUARTERS, dots=True, mark_latest=False,
        aria_label=f"近 {config.TREND_YEARS} 年季度毛利率和净利率趋势",
    )
    judge = ""
    if improve:
        cmp = improve.get("compare") or {}
        # 判定结论已经写在标题右侧的 badge 上（［未改善（C3 不成立）］之类），
        # 这里不再重复一句“① 毛利率环比改善判定：…”，直接从同比 / 环比两个对照讲数字。
        lines = []
        if cmp.get("yoy_line"):
            lines.append(f'<p class="small">{esc(cmp["yoy_line"])}</p>')
        if cmp.get("qoq_line"):
            lines.append(f'<p class="small">{esc(cmp["qoq_line"])}</p>')
        if cmp.get("verdict"):
            lines.append(f'<p class="small">{esc(cmp["verdict"])}</p>')
        judge = "".join(lines)
    return (
        f"<h3>{esc(title)}{badge}</h3>"
        '<p class="small">单季口径；净利率为归母口径；季度数据未经审计。</p>'
        f"{chart}<p class=\"small\">{note}</p>{judge}"
    )


def _valuation_charts(chart: dict[str, Any]) -> str:
    points = chart.get("points") or []
    if not points:
        return '<p class="small">暂无估值序列数据。</p>'
    years = chart.get("years") or config.VALUATION_YEARS
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
            aria_label=f"近 {years} 年 {label} 周频走势", legend=False,
        )
        panels.append(
            f'<div class="chart-panel"><h4>{esc(label)}</h4>{panel}'
            f'<p class="small">{esc(note)}</p></div>'
        )
    start, end = chart.get("start") or "—", chart.get("end") or "—"
    span = chart.get("span_years") or 0
    if chart.get("limited"):
        span_text = f"可用历史约 {span:.1f} 年" if span >= 1 else "可用历史不足 1 年"
        window_note = f"{span_text}，已全部展示"
    else:
        window_note = f"近 {years} 年周频"
    return (
        '<div class="chart-grid">' + "".join(panels) + "</div>"
        f'<p class="small">数据范围：{esc(start)} 至 {esc(end)}（{window_note}，'
        f"共 {n(chart.get('count'), 0)} 个周度点）。"
        "灰色区间为 PE 为负（亏损），该区间不连线；分位表按全部可用历史计算。</p>"
    )


def _section_business(data: dict[str, Any]) -> str:
    meta = data["meta"]
    business = meta.get("business") or "暂无披露"
    if len(business) > 700:
        business = business[:700] + "…"
    annual = sorted(data["financials"].get("annual") or [], key=lambda x: x.get("year") or 0)[-5:]
    structure = data["financials"].get("structure") or {}
    srows = {r.get("year"): r for r in structure.get("rows") or []}
    financial = bool((data.get("quality") or {}).get("not_applicable"))
    rows = []
    for y in annual:
        s = srows.get(y.get("year")) or {}
        debt_cell = "—" if financial else yi(s.get("debt"))
        cip_cell = "—" if financial else pct(s.get("construction_ratio"))
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
            f"<td>{debt_cell}</td>"
            f"<td>{cip_cell}</td>"
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
    evidence = moat.get("evidence") or []
    if evidence:
        reasons = "".join(
            f"<li>{'✅' if e.get('ok') else '❌'} <b>{esc(e.get('name'))}</b>：{esc(e.get('detail'))}</li>"
            for e in evidence)
        moat_note = f"三条证据 {moat.get('met')}/{moat.get('total')}"
    else:
        reasons = "".join(f"<li>{esc(x)}</li>" for x in moat.get("reasons") or [])
        moat_note = "三条证据口径不适用" if moat.get("not_applicable") else "年报不足 3 年"
    checks = (data.get("risks") or {}).get("checks") or []
    improve = next((c for c in checks if c.get("key") == "margin_improve"), None)
    structure_line = _structure_line(structure, financial)
    margin_chart = _margin_chart(data["financials"].get("margin_trend") or {}, improve)
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
      <div class="note">{esc(moat_note)}</div></div>
  </div>
  <ul>{reasons or '<li>数据不足，暂不判断。</li>'}</ul>
  <h3>五年经营轨迹</h3>
  <table>
    <thead><tr><th>年度</th><th>营收（亿）</th><th>归母净利（亿）</th><th>ROE</th><th>ROIC</th><th>FCF（亿）</th><th>FCF/营收</th><th>毛利率</th><th>有息负债（亿）</th><th>在建工程/固资</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="10">数据不足</td></tr>'}</tbody>
  </table>
  {structure_line}
  {margin_chart}
  <p class="small">只写主营、行业、五年量化轨迹和护城河规则结论；不含上下游、政策、管理层评价。</p>
</section>"""


def _section_risks(data: dict[str, Any]) -> str:
    risks = data.get("risks") or {}
    checks = risks.get("checks") or []
    hits = sum(1 for c in checks if c.get("status") == "hit")
    watches = sum(1 for c in checks if c.get("status") == "watch")
    unknown = sum(1 for c in checks if c.get("status") == "unknown")
    na = sum(1 for c in checks if c.get("status") == "na")
    known = len(checks) - unknown - na
    # 按组渲染：命中/提示/数据不足/不适用正常显示，全部通过的折成一行
    rows: list[str] = []
    for group in config.RISK_GROUPS:
        items = [c for c in checks if c.get("group") == group]
        if not items:
            continue
        rows.append(f'<tr class="group-row"><td colspan="4">{esc(group)}（{len(items)} 项）</td></tr>')
        clears = []
        for c in items:
            if c.get("status") == "clear":
                clears.append(c)
                continue
            rows.append(
                "<tr>"
                f"<td>{esc(c.get('name'))}</td>"
                f"<td>{_status(c.get('status', 'unknown'))}</td>"
                f"<td>{esc(c.get('detail'))}</td>"
                f"<td>{esc(c.get('severity'))}</td>"
                "</tr>"
            )
        if clears:
            names = "、".join(str(c.get("name")) for c in clears)
            rows.append(
                f'<tr class="fold-row"><td>其余 {len(clears)} 项未见异常</td>'
                f'<td>{_status("clear")}</td><td colspan="2">{esc(names)}</td></tr>'
            )
    fatal = risks.get("fatal") or []
    fatal_html = ""
    if fatal:
        fatal_html = ('<div class="flags"><b>致命项</b><ul>'
                      + "".join(f"<li>{esc(x)}</li>" for x in fatal) + "</ul></div>")
    summary = risks.get("summary") or ""
    summary_html = ""
    if summary:
        summary_html = f'<div class="flags"><b>组合定性</b>　{esc(summary)}</div>'
    return f"""
<section>
  <h2>二、经营质量与风险</h2>
  <p class="muted">{len(checks)} 项高信号检查，分真伪 / 趋势 / 质量 / 安全四组，
     全部由同一批年报数据计算；未判定不当作通过，通过项折叠在每组末尾。</p>
  <div class="grid">
    <div class="metric"><div class="k">风险检查</div><div class="v">{known} / {len(checks) - na}</div>
      <div class="note">已知 {known} 项；命中 {hits} 项；提示 {watches} 项；数据不足 {unknown} 项；不适用 {na} 项</div></div>
    <div class="metric"><div class="k">风险状态</div><div class="v">{'有命中' if hits else ('有提示' if watches else '无异常')}</div>
      <div class="note">命中不等于造假，只表示需要追问</div></div>
  </div>
  {summary_html}
  {fatal_html}
  <table>
    <thead><tr><th>检查</th><th>状态</th><th>计算/证据</th><th>严重度</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="small">一票否决位（现金流质量、现金短债比）命中时会在上方「组合定性」点名，
     但不直接改变结论；致命项仍只有净资产为负、利息保障 &lt;1、商誉 &gt;50%、
     连续 3 年经营现金流为负且净负债/EBIT &gt;4 四条。</p>
</section>"""


def _section_valuation(data: dict[str, Any]) -> str:
    val = data.get("valuation") or {}
    metrics = val.get("metrics") or {}
    sample = val.get("sample") or {}
    as_of = ((data.get("meta") or {}).get("price_date") or sample.get("end") or "—")
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
    # 分位覆盖的区间用实际起始年份表述（东财序列老股通常从 2018 年起），
    # 不写死年份：新股可能只有两三年，写“2018 年以来”会误导。
    since_note = "全部可用历史（周频）"
    start_year = str((sample or {}).get("start") or "")[:4]
    if start_year.isdigit():
        since_note = f"{start_year} 年以来周频"
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
    rating = fc.get("rating") or {}
    coverage = fc.get("coverage") or 0
    rating_coverage = fc.get("rating_coverage") or 0
    if frows:
        coverage_note = f"覆盖机构 {coverage} 家" if coverage else "覆盖机构数未披露"
        if coverage and coverage < 3:
            coverage_note += "；低于 3 家，预测参考价值有限"
    elif rating:
        coverage_note = (f"暂无盈利预测；评级记录 {rating.get('records', 0)} 条、"
                         f"覆盖机构 {rating_coverage} 家")
    else:
        coverage_note = "暂无机构覆盖"
    target = fc.get("target_price")
    price = data["meta"].get("price")
    target_note = "无目标价"
    if target:
        upside = ((target / price - 1) * 100) if price else None
        target_note = f"{n(target)} 元" + (f"（较现价 {upside:+.1f}%）" if upside is not None else "")
    rating_note = "暂无评级数据"
    if rating:
        rating_note = (f"买入 {rating.get('buy', 0)} 条、增持 {rating.get('increase', 0)} 条；"
                       f"评级记录 {rating.get('records', 0)} 条（不是机构数）")
    cv = data.get("cash_valuation") or {}

    def _money(value: Any) -> str:
        return "—" if value is None else f"{n(value)} 亿"

    cv_rows = []
    if cv and any(cv.get(k) is not None for k in
                  ("market_cap_yi", "cash_yi", "net_profit_yi")):
        cash_note = f"最新报告期 {cv.get('cash_period')}" if cv.get("cash_period") else ""
        profit_note = f"最近年报 {cv.get('profit_period')}；营业收入 × 净利率近似" if cv.get("profit_period") else "营业收入 × 净利率近似"
        ex_cash_note = "总市值 − 货币资金"
        if cv.get("negative_ex_cash"):
            ex_cash_note += "；市值低于货币资金"
        pe = cv.get("ex_cash_pe")
        if pe is not None:
            pe_text = f"{n(pe)}x"
        elif cv.get("negative_ex_cash"):
            pe_text = "不适用（市值低于货币资金）"
        else:
            pe_text = "不适用"
        cv_rows = [
            ("总市值", _money(cv.get("market_cap_yi")), ""),
            ("货币资金", _money(cv.get("cash_yi")), cash_note),
            ("货币资金/市值", pct(cv.get("cash_ratio_pct")), "现金底仓比例"),
            ("有息负债", _money(cv.get("debt_yi")), "仅展示，不参与计算"),
            ("扣现金市值", _money(cv.get("ex_cash_cap_yi")), ex_cash_note),
            ("最近年报净利润总额", _money(cv.get("net_profit_yi")), profit_note),
            ("扣现金 PE", pe_text, "扣现金市值 ÷ 净利润总额"),
            ("盈利收益率", pct(cv.get("earnings_yield_pct")), "净利润总额 ÷ 总市值"),
        ]
    cv_html = ""
    if cv_rows:
        body = "".join(
            f"<tr><td>{esc(k)}</td><td>{esc(v)}</td><td>{esc(note)}</td></tr>"
            for k, v, note in cv_rows)
        cv_html = (
            "<table><thead><tr><th>指标</th><th>数值</th><th>说明</th></tr></thead>"
            f"<tbody>{body}</tbody></table>"
        )
    else:
        cv_html = f'<p class="small">不适用：{esc(cv.get("reason") or "数据不足")}</p>'

    anchor_rows = []
    for anchor in cv.get("anchors") or []:
        anchor_rows.append(
            "<tr>"
            f"<td>{esc(anchor.get('years'))} 年</td>"
            f"<td>{_money(anchor.get('value_yi'))}</td>"
            f"<td>{n(anchor.get('per_share')) + ' 元' if anchor.get('per_share') is not None else '—'}</td>"
            f"<td>{pct(anchor.get('margin_pct'))}</td>"
            "</tr>"
        )
    anchor_body = "".join(anchor_rows) or (
        f'<tr><td colspan="4">不适用：{esc(cv.get("reason") or "数据不足")}</td></tr>')
    anchor_html = (
        "<table><thead><tr><th>年限 N</th><th>底线价值</th><th>每股底线</th>"
        f"<th>安全边际</th></tr></thead><tbody>{anchor_body}</tbody></table>"
    )

    flags = data.get("flags") or []
    flags_html = ""
    if flags:
        flags_html = '<div class="flags"><b>预期差提示</b><ul>' + "".join(f"<li>{esc(x)}</li>" for x in flags) + "</ul></div>"
    gaps = data.get("data_gaps") or []
    gaps_html = ""
    if gaps:
        gaps_html = ('<div class="flags"><b>取数缺口</b><ul>' +
                     "".join(f"<li>{esc(x.get('tool'))}：{esc(x.get('error'))}</li>" for x in gaps) +
                     "</ul></div>")

    return f"""
<section>
  <h2>三、企业估值与机构预期</h2>
  {gaps_html}
  <h3>PE/PB/PS 历史分位及走势图</h3>
  <p class="small">样本：{sample_note}。<b>全篇估值口径统一为 {esc(as_of)} 收盘</b>：下表“最新收盘”、
     下图最后一个点、机构目标价空间、现金底线里的市值，用的是同一个收盘价。
     上表为 {since_note}分位；下图为近 {config.VALUATION_YEARS} 年周频走势
     （可用历史不足 {config.VALUATION_YEARS} 年时按全部可用历史），PE 为负时断线。
     历史分位与走势图只展示，不进入 V 分。</p>
  <table>
    <thead><tr><th>指标</th><th>最新收盘</th><th>历史分位</th><th>区间</th><th>样本点数</th></tr></thead>
    <tbody>{''.join(mrows) or '<tr><td colspan="5">暂无历史估值数据</td></tr>'}</tbody>
  </table>

  {valuation_charts}

  <h3>机构对企业未来盈利的预期</h3>
  <p class="small">{esc(coverage_note)}。预测净利与营收单位为亿元；预测不是事实。</p>
  <table>
    <thead><tr><th>年度</th><th>预测营收（亿）</th><th>预测归母（亿）</th><th>预测 EPS</th><th>净利同比</th><th>对应 PE</th></tr></thead>
    <tbody>{''.join(frows) or '<tr><td colspan="6">暂无机构覆盖</td></tr>'}</tbody>
  </table>
  <div class="grid">
    <div class="metric"><div class="k">机构目标价</div><div class="v">{target_note}</div><div class="note">目标价 ≠ 本报告合理价</div></div>
    <div class="metric"><div class="k">评级分布</div><div class="v" style="font-size:14px">{esc(rating_note)}</div><div class="note">评级记录条数不等于覆盖机构数</div></div>
  </div>
  {flags_html}

  <h3>用现金扣除与底线估值方式对企业进行估值</h3>
  <p class="small">现金底仓直接用货币资金，不扣有息负债；净利润总额取最近年报，
     按“营业收入 × 净利率”近似；年限 N 是情景假设，不是目标价。</p>
  {cv_html}
  <p class="small" style="margin-top:10px">底线价值 = 货币资金 + N × 最近年报净利润总额。
     安全边际 =（底线价值 − 总市值）÷ 底线价值；正数表示市值低于底线。</p>
  {anchor_html}
</section>"""


def _section_score(data: dict[str, Any]) -> str:
    q = data.get("quality") or {}
    v = data.get("valuation_score") or {}
    decision = data.get("decision") or {}
    dq = data.get("data_quality") or {}
    checks = ((data.get("risks") or {}).get("checks") or [])
    risk_total = len(checks)
    risk_na = sum(1 for c in checks if c.get("status") == "na")
    # 分母用「适用项」：金融股有 5 项本来就作不了判，算进分母会让 11/14 这种假数字出现
    risk_applicable = risk_total - risk_na
    risk_hits = sum(1 for c in checks if c.get("status") == "hit")
    risk_watches = sum(1 for c in checks if c.get("status") == "watch")
    risk_unknown = sum(1 for c in checks if c.get("status") == "unknown")
    risk_known = risk_applicable - risk_unknown
    qs, vs = q.get("score"), v.get("score")
    not_applicable = bool(q.get("not_applicable") or v.get("not_applicable"))
    # 一致性行（0.9.0）：Q 与第二节各判一遍，结论取更谨慎的一方。
    # 闸门真降级时用 decision 里的 note；结论本身已是回避/等价格时说清“已达降级线但没再降”，
    # 避免读者以为程序悄悄改过结论，或以为 1 命中 4 提示毫无影响。
    gate_level = (data.get("risks") or {}).get("gate_level")
    gate_label = {"avoid": "回避", "watch": "观察"}.get(gate_level or "", "")
    if not_applicable:
        consist_note = ""
    elif decision.get("note"):
        consist_note = decision["note"]
    elif gate_level:
        consist_note = (f"第二节：命中 {risk_hits} 项、提示 {risk_watches} 项 → "
                        f"已达降级线（买入类会降为{gate_label}），但当前结论不是买入类，未再降级")
    elif risk_hits or risk_watches:
        consist_note = f"第二节：命中 {risk_hits} 项、提示 {risk_watches} 项 → 未触发降级"
    else:
        consist_note = "第二节：无命中、无提示 → 结论未被降级"

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
    # 金融股：Q/V 都是 not_applicable，groups/parts 为空，表格要给空态而不是留个空 tbody
    if not qrows and not_applicable:
        qrows.append(
            '<tr><td colspan="3">金融股不适用：银行/保险/证券没有毛利率、FCF、'
            '应收/存货、净有息负债这些科目，不套用五维口径</td></tr>'
        )
    if not vrows and not_applicable:
        vrows.append(
            '<tr><td colspan="3">金融股不适用：本工具不对银行/保险/证券输出 V 分</td></tr>'
        )
    if not_applicable:
        tail_html = (
            f'  <p class="small">数据完整度：风险检查 {risk_known}/{risk_applicable} 已知；'
            f'机构覆盖 {dq.get("institution_coverage", "—")} 家。</p>\n'
            '  <div class="small">金融股不进入“质量调整后的买入门槛”矩阵：'
            '本工具既不给“可买”，也不给“回避”，请结合第二节风险检查原文自行判断。</div>'
        )
    else:
        tail_html = (
            f'  <p class="small">数据完整度：风险检查 {risk_known}/{risk_applicable} 已知；\n'
            f'     机构覆盖 {dq.get("institution_coverage", "—")} 家；'
            f'Q 数据覆盖 {pct(dq.get("q_coverage"))}。\n'
            '     可买还需满足：机构覆盖≥3 家、Q 覆盖≥80%、关键风险检查无缺失。</p>\n'
            '  <div class="small">\n'
            '    决策规则（质量调整）：Q≥75：V≥65 推荐买入，50~65 等价格，35~50 偏贵，&lt;35 太贵；\n'
            '    Q65~75：V≥80 推荐，70~80 可买，50~70 观察，&lt;50 回避；\n'
            '    Q55~65：V≥75 小仓买入，50~75 观察，&lt;50 回避；\n'
            '    Q45~55：V≥80 小仓试错，65~80 观察，&lt;65 回避；\n'
            '    Q&lt;45：回避，禁止买入；Q 或 V 缺失 → 数据不足。\n'
            '    一致性闸门：第二节命中 ≥2 项、或现金流质量/现金短债比命中 → 买入类降为回避；\n'
            '    提示 ≥2 项、或命中 1 项 → 买入类降为“观察，第二节有信号”。\n'
            '  </div>'
        )
    return f"""
<section>
  <h2>四、综合评分</h2>
  <div class="grid">
    <div class="metric"><div class="k">质量分 Q</div><div class="v">{n(qs, 1)}</div><div class="note">{esc(q.get('grade'))} · 风险检查 {risk_known}/{risk_applicable} 已知</div>
      {f'<div class="note">{esc(consist_note)}</div>' if consist_note else ''}
      {_bar(qs, _score_class(qs))}</div>
    <div class="metric"><div class="k">估值分 V</div><div class="v">{n(vs, 1)}</div><div class="note">{esc(v.get('grade'))}</div>
      {_bar(vs, _score_class(vs))}</div>
    <div class="metric"><div class="k">结论</div><div class="v" style="font-size:19px">{esc(decision.get('label'))}</div>
      <div class="note">{esc(decision.get('reason'))}</div></div>
  </div>
  <h3>质量分构成（五个维度，第二节不参与打分）</h3>
  <p class="small">Q 只看 5 年长期水平，第二节只看当期异常；两者用同一批年报数据，但判定方式不同
     （Q 连续打分、第二节阈值判定），因此同一科目可能在 Q 里扣分、又在第二节命中。
     结论取两者中更谨慎的一方：第二节命中或提示够多时，买入类结论会被降级，负面结论不因此更保守。
     当前风险检查：{risk_known}/{risk_applicable} 已知，命中 {risk_hits} 项、提示 {risk_watches} 项、
     数据不足 {risk_unknown} 项。</p>
  <table><thead><tr><th>维度</th><th>得分</th><th>数据覆盖</th></tr></thead><tbody>{''.join(qrows)}</tbody></table>
  <p class="small">分档（优秀 ≥85 / 良好 75~85 / 中等偏上 65~75 / 中等 55~65 / 偏弱 45~55 / 差 &lt;45）
     只是标签，<b>不改变</b>下面的结论矩阵；矩阵只认 Q 的数值。</p>
  <h3>估值分构成（机构口径）</h3>
  <table><thead><tr><th>维度</th><th>得分 / 100</th><th>原始值</th></tr></thead><tbody>{''.join(vrows)}</tbody></table>
  <p class="small">V 分 = 目标价空间 40% + 预测 PE 20% + 未来净利增速 40%；缺失项按可用权重归一。
     无机构覆盖时 V 不计算，但 Q 分正常展示。</p>
{tail_html}
  <p class="small">机构预期直接决定 V 分；评级分布只展示，不参与打分。</p>
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
  <div class="price">{price_text}<span style="font-size:13px;font-weight:400;opacity:.8;margin-left:10px">市值 {n(meta.get('market_cap_yi'))} 亿元 · {esc(meta.get('price_basis') or '实时价')}</span></div>
  <div class="meta">估值口径 {esc(meta.get('price_date') or '—')} 收盘 · 数据快照 {esc(meta.get('quote_date') or '—')} · 最新报告期 {esc(meta.get('latest_date') or '—')}</div>
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
              "估值分 V：机构目标价空间 40、预测 PE 相对当前 PE 20、未来净利增速 40。"
              "历史分位、FCF 与现金底线只展示，不进入 V。权重与阈值见 config.py。")
    limits = ("机构覆盖不足 3 家、Q 数据覆盖低于 80%、关键风险检查缺失时，不给出可买；"
              "金融股与强周期股不适合直接套用 FCF。现金扣除块只展示，"
              "不扣有息负债，净利润总额为营业收入×净利率的近似值，不进入 V 分。")
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
