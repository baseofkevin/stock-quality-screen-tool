# -*- coding: utf-8 -*-
"""生成浏览器里的报告导航页：每只股票一行，含结论、扩展指标与两个链接。"""
from __future__ import annotations

import html
import os
import uuid
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import url2pathname

from screen.batch import (CAP_COLUMN, EASTMONEY_COLUMN, EASTMONEY_LINK_TEXT,
                          EMPTY_TEXT, INDUSTRY2_COLUMN, LINK_COLUMN,
                          MARGIN_COLUMN, SCORE_COLUMN, STAR_COLUMN,
                          TURNOVER_PCT_COLUMN, CsvTable, eastmoney_url,
                          link_target, summary_cell)

LINK_TEXT = "报告链接"

# 列定义集中在这里：表头、空表 colspan 全部由它推出来，
# 以后再加列只改这一处，不会出现「表头 10 列、数据 9 列」的错位。
COLUMNS: tuple[str, ...] = (
    "代码",
    "名称",
    "综合评分",
    INDUSTRY2_COLUMN,
    MARGIN_COLUMN,
    TURNOVER_PCT_COLUMN,
    STAR_COLUMN,
    CAP_COLUMN,
    "报告",
    "东方财富网",
)


def _path_from_target(cell: str, base_dir: Path) -> Path | None:
    target = link_target(cell)
    if not target:
        return None
    if target.startswith("file://"):
        parsed = urlparse(target)
        if parsed.scheme != "file":
            return None
        try:
            path = Path(url2pathname(parsed.path))
        except ValueError:
            return None
    else:
        path = Path(os.path.expanduser(target))
        if not path.is_absolute():
            path = base_dir / path
    return path


def _badge_class(score: str) -> str:
    if "买" in score:
        return "buy"
    if "回避" in score:
        return "avoid"
    # 「跳过：上市不足 3 年」不是观察类：它没有结论，归到灰色 unknown 徽标
    if "数据不足" in score or "失败" in score or "无效" in score or "跳过" in score:
        return "unknown"
    return "watch"


def _plain(value: str) -> str:
    """单元格里没值就显示占位符，有值就转义输出。"""
    text = str(value or "").strip()
    return html.escape(text) if text else f'<span class="na">{EMPTY_TEXT}</span>'


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_index_html(table: CsvTable, out_dir: str | Path) -> Path:
    """在报告目录生成导航页，按钮直接打开同目录下的 HTML。

    导航页文件名跟输入 CSV 主名一致（`rows.csv` → `rows.html`），
    和同一次运行的产物对得上号。
    """
    out = Path(out_dir).resolve()
    target = out / f"{Path(table.path).stem}.html"
    rows_html = []
    counts = {"buy": 0, "watch": 0, "avoid": 0, "unknown": 0, "missing": 0}

    for row in table.rows:
        code_raw = str(row.get(table.code_column, ""))
        code = html.escape(code_raw)
        name_raw = str(row.get("名称", "") or row.get("name", ""))
        name = html.escape(name_raw)
        score = html.escape(str(row.get(SCORE_COLUMN, "")))
        report_path = _path_from_target(str(row.get(LINK_COLUMN, "")), table.path.parent)
        href = ""
        if report_path is not None and report_path.is_file():
            try:
                href = quote(report_path.resolve().relative_to(out).as_posix())
            except ValueError:
                href = report_path.resolve().as_uri()
        if href:
            link = f'<a class="btn" href="{html.escape(href)}">{LINK_TEXT}</a>'
        else:
            link = '<span class="btn disabled">无报告</span>'
            counts["missing"] += 1
        eastmoney = link_target(str(row.get(EASTMONEY_COLUMN, "")))
        if not eastmoney:
            eastmoney = eastmoney_url(code_raw)
        if eastmoney:
            eastmoney_link = (f'<a class="btn alt" href="{html.escape(eastmoney)}" '
                              f'target="_blank" rel="noopener">{EASTMONEY_LINK_TEXT}</a>')
        else:
            eastmoney_link = '<span class="btn disabled">无链接</span>'
        badge = _badge_class(str(row.get(SCORE_COLUMN, "")))
        counts[badge] += 1

        # 五列全部原样透传；毛利率由 summary_cell 压成「是 / 否」
        industry2 = summary_cell(row, INDUSTRY2_COLUMN)
        margin = summary_cell(row, MARGIN_COLUMN)
        pct = summary_cell(row, TURNOVER_PCT_COLUMN)
        stars = summary_cell(row, STAR_COLUMN)
        cap = summary_cell(row, CAP_COLUMN)

        if margin == "是":
            margin_html = '<span class="yes">是</span>'
        elif margin == "否":
            margin_html = '<span class="no">否</span>'
        else:
            margin_html = f'<span class="na">{EMPTY_TEXT}</span>'

        stars_html = (f'<span class="stars">{html.escape(stars)}</span>' if stars
                      else f'<span class="na">{EMPTY_TEXT}</span>')
        pct_html = (f'{html.escape(pct)}<span class="unit">%</span>' if pct
                    else f'<span class="na">{EMPTY_TEXT}</span>')

        # data-search 带上新增的几列：搜「白色家电」「是」也能筛出对应行
        search = " ".join(x for x in (code_raw, name_raw, score, industry2,
                                      margin, pct, stars, cap) if x)
        rows_html.append(
            f'<tr data-search="{html.escape(search)}">'
            f'<td class="code">{code}</td>'
            f'<td>{name}</td>'
            f'<td><span class="badge {badge}">{score or EMPTY_TEXT}</span></td>'
            f'<td>{_plain(industry2)}</td>'
            f'<td class="center">{margin_html}</td>'
            f'<td class="num">{pct_html}</td>'
            f'<td class="center">{stars_html}</td>'
            f'<td class="num">{_plain(cap)}</td>'
            f'<td class="action">{link}</td>'
            f'<td class="action">{eastmoney_link}</td>'
            "</tr>"
        )

    total = len(table.rows)
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>报告导航 - {html.escape(table.path.stem)}</title>
<style>
  :root {{ --ink:#1f2933; --muted:#66788a; --line:#d9e2ec; --brand:#1f5f8b; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#f4f7fa; color:var(--ink);
         font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC",sans-serif; }}
  header {{ background:#fff; border-bottom:1px solid var(--line); padding:22px 28px 18px; }}
  h1 {{ margin:0 0 6px; font-size:22px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .stats {{ margin-top:14px; display:flex; flex-wrap:wrap; gap:10px; }}
  .stat {{ background:#f4f7fa; border:1px solid var(--line); border-radius:8px; padding:6px 10px; font-size:13px; }}
  .wrap {{ padding:18px 28px 40px; }}
  .toolbar {{ margin-bottom:12px; }}
  input[type=search] {{ width:min(420px,100%); padding:9px 12px; border:1px solid var(--line);
                        border-radius:8px; font-size:14px; outline:none; background:#fff; }}
  input[type=search]:focus {{ border-color:var(--brand); box-shadow:0 0 0 3px rgba(31,95,139,.12); }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line);
           border-radius:10px; overflow:hidden; }}
  th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; }}
  th {{ background:#eaf1f7; color:#334e68; font-weight:600; white-space:nowrap; }}
  tr:last-child td {{ border-bottom:0; }}
  tr:hover td {{ background:#f8fbfd; }}
  td.code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:#486581; white-space:nowrap; }}
  td.action {{ width:150px; }}
  td.num {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
  td.center {{ text-align:center; white-space:nowrap; }}
  .unit {{ color:var(--muted); font-size:12px; margin-left:1px; }}
  .na {{ color:#b0bcc8; }}
  .yes {{ color:#1f7a4d; font-weight:600; }}
  .no {{ color:#8a94a0; }}
  .stars {{ color:#c98a00; letter-spacing:1px; font-weight:700; }}
  .btn {{ display:inline-block; padding:7px 14px; border-radius:7px; background:var(--brand);
          color:#fff; text-decoration:none; font-weight:600; text-align:center; white-space:nowrap; }}
  .btn:hover {{ background:#174a6d; }}
  .btn.alt {{ background:#b3261e; }}
  .btn.alt:hover {{ background:#8f1d17; }}
  .btn.disabled {{ background:#c7d2dc; color:#64748b; cursor:not-allowed; }}
  .badge {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:600; }}
  .badge.buy {{ background:#dff3e6; color:#1f7a4d; }}
  .badge.watch {{ background:#fff4d6; color:#8a5a00; }}
  .badge.avoid {{ background:#fde2e0; color:#b3261e; }}
  .badge.unknown {{ background:#e9eef3; color:#52606d; }}
  .empty {{ padding:28px; text-align:center; color:var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>企业质量初筛报告导航</h1>
  <div class="sub">{html.escape(table.path.name)} · 共 {total} 行 · 点击「{LINK_TEXT}」直接打开 HTML</div>
  <div class="stats">
    <span class="stat">买入类 {counts['buy']}</span>
    <span class="stat">观察类 {counts['watch']}</span>
    <span class="stat">回避 {counts['avoid']}</span>
    <span class="stat">数据不足/失败 {counts['unknown']}</span>
    <span class="stat">无报告 {counts['missing']}</span>
  </div>
</header>
<div class="wrap">
  <div class="toolbar"><input id="q" type="search" placeholder="搜索代码、名称或结论…"></div>
  <table id="table">
    <thead><tr>{''.join(f'<th>{html.escape(c)}</th>' for c in COLUMNS)}</tr></thead>
    <tbody>{''.join(rows_html) if rows_html else f'<tr><td colspan="{len(COLUMNS)}" class="empty">没有数据</td></tr>'}</tbody>
  </table>
</div>
<script>
  const input = document.getElementById('q');
  const rows = Array.from(document.querySelectorAll('#table tbody tr[data-search]'));
  input.addEventListener('input', () => {{
    const q = input.value.trim().toLowerCase();
    rows.forEach(row => {{
      row.style.display = !q || row.dataset.search.toLowerCase().includes(q) ? '' : 'none';
    }});
  }});
</script>
</body>
</html>
"""
    _write_atomic(target, doc)
    return target
