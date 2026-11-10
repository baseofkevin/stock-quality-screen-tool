# -*- coding: utf-8 -*-
"""测试公共工具：fixture 装载、合成年报、CSV 读写。

约定：
- `report_data()` 每次都重新构建，测试可以随意修改返回值，不会污染其他用例。
- `annual_rows()` 用标量或列表覆盖默认字段，方便构造“某一项特别差/缺失”的公司。
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screen.compute import build_report_data  # noqa: E402
from screen.fetch import load_bundle  # noqa: E402
from screen.score import compute_scores  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "mini_bundle.json"

# 一个“健康公司”的默认年报记录；测试只覆盖关心的字段。
ANNUAL_DEFAULTS = {
    "revenue": 100e8,
    "net_profit": 12e8,
    "net_profit_total": 12.5e8,
    "deducted": 11.5e8,
    "gross_margin": 40.0,
    "net_margin": 12.0,
    "roe": 15.0,
    "roa": 8.0,
    "roic": 12.0,
    "ocf": 14e8,
    "ocf_ttm": None,
    "np_ttm": None,
    "icf": -5e8,
    "fcf_fin": -2e8,
    "capex": 2e8,
    "fcf": 12e8,
    "fcf_margin": 0.12,
    "total_assets": 200e8,
    "equity": 80e8,
    "total_equity": 85e8,
    "debt": 10e8,
    "cash": 20e8,
    "goodwill": 0.0,
    "goodwill_imputed": False,
    "current_ratio": 2.0,
    "quick_ratio": 1.5,
    "working_capital": 20e8,
    "ebit": 16e8,
    "finance_expense": 1e8,
    "shares": 10e8,
    "ar": 5e8,
    "receivable_fin": 0.0,
    "inventory": 6e8,
    "payable": 6e8,
    "other_ar": 0.5e8,
    "other_ap": 1e8,
    "contract_liability": 8e8,
    "advance_payment": 0.0,
    "short_loan": None,
    "ncl_1y": None,
    "construction": 1e8,
    "fixed_asset": 50e8,
    "sell_expense": 3e8,
    "admin_expense": 4e8,
    "rnd_expense": 1e8,
}


def raw_bundle() -> dict:
    return load_bundle(FIXTURE)


def report_data() -> dict:
    raw = raw_bundle()
    return build_report_data(raw["calls"], raw["code"])


def scored_data() -> dict:
    return compute_scores(report_data())


def annual_rows(count: int = 5, start: int = 2020, **fields) -> list[dict]:
    """生成 count 个年报记录。

    fields 的值可以是标量（每年相同），也可以是长度等于 count 的列表（逐年取值）。
    """
    rows = []
    for i in range(count):
        row = dict(ANNUAL_DEFAULTS)
        row["year"] = start + i
        row["date"] = f"{start + i}-12-31"
        for key, value in fields.items():
            row[key] = value[i] if isinstance(value, (list, tuple)) else value
        rows.append(row)
    return rows


def with_annual(rows: list[dict]) -> dict:
    """包成 `_quality` / `_risk_checks` 需要的 data 结构。"""
    return {"financials": {"annual": rows}}


def margin_data(points: list[tuple]) -> dict:
    """构造带季度毛利率/净利率序列的 data（用于 ① 毛利率环比改善三条件）。

    points: [(报告期, 单季营收, 单季毛利率%), ...] 或
            [(报告期, 单季营收, 单季毛利率%, 单季净利率%), ...]，按时间升序。
    """
    rows = []
    for p in points:
        rows.append({"date": p[0], "label": p[0], "revenue": p[1], "gross": p[2],
                     "net": p[3] if len(p) > 3 else None})
    return {"financials": {"annual": [], "margin_trend": {"points": rows}}}


def write_csv(path: Path, rows: list[dict], header: list[str], *,
              encoding: str = "utf-8-sig", newline: str = "\r\n") -> None:
    text = newline.join([",".join(header)] + [",".join(str(r.get(k, "")) for k in header) for r in rows])
    path.write_bytes((text + newline).encode(encoding))


def read_csv_rows(path: Path) -> list[dict]:
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    return list(csv.DictReader(io.StringIO(raw.decode(encoding), newline="")))


def read_csv_text(path: Path) -> str:
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    return raw.decode(encoding)
