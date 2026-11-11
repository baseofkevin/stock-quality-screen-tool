# -*- coding: utf-8 -*-
"""数值格式化：全项目唯一一份实现。

以前三套并存（`score._p/_n/_yi`、`render.n/pct/yi`、`util.pct/yi/ratio/text`），
同一个数字在不同章节可能差一个千分位或一个「亿」，改口径要改三处。现在只留这里，
调用方按需取：

    num / num_sep   两位小数；num 不带千分位，num_sep 带（金额用）
    pct             百分数，默认一位
    signed_pct      带正负号的百分数（增速）
    yi / yi_suffix  元 → 亿；yi 只给数字，yi_suffix 补「 亿」

两条约定：
  1. None 一律输出 `—`（U+2014），不用 0 或空串冒充数据；
  2. 传进来不是数字（比如接口直接给了中文）时原样转义输出，不抛错——
     报告缺一格比整份报告生成失败好。
"""
from __future__ import annotations

import html
from typing import Any

DASH = "—"


def _raw(value: Any) -> str:
    return html.escape(str("" if value is None else value), quote=True)


def num(value: Any, digits: int = 2) -> str:
    """1.234 → "1.23"；None → "—"。不带千分位。"""
    if value is None:
        return DASH
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return _raw(value)


def num_sep(value: Any, digits: int = 2) -> str:
    """1234.5 → "1,234.50"；None → "—"。带千分位，给金额和倍数用。"""
    if value is None:
        return DASH
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return _raw(value)


def pct(value: Any, digits: int = 1) -> str:
    """12.34 → "12.3%"；None → "—"。"""
    if value is None:
        return DASH
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return _raw(value)


def signed_pct(value: Any, digits: int = 1) -> str:
    """0.1234（小数）→ "+12.3%"；None → "—"。"""
    if value is None:
        return DASH
    try:
        return f"{float(value) * 100:+.{digits}f}%"
    except (TypeError, ValueError):
        return _raw(value)


def yi(value: Any, digits: int = 2) -> str:
    """1e8（元）→ "1.00"，单位由调用方在表头写。"""
    if value is None:
        return DASH
    try:
        return f"{float(value) / 1e8:,.{digits}f}"
    except (TypeError, ValueError):
        return _raw(value)


def yi_suffix(value: Any, digits: int = 2) -> str:
    """1e8（元）→ "1.00 亿"，单位跟着数值走。"""
    if value is None:
        return DASH
    try:
        return f"{float(value) / 1e8:,.{digits}f} 亿"
    except (TypeError, ValueError):
        return _raw(value)
