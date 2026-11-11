# -*- coding: utf-8 -*-
"""小工具：安全数值与统计原语。格式化统一在 screen/fmt.py，不在这里。"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable


def num(value: Any) -> float | None:
    """把接口里的字符串数字转成 float；空值/无法解析返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    s = str(value).strip().replace(",", "").replace("%", "")
    if not s or s in {"--", "-", "None", "null", "nan"}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def median(values: Iterable[float | None]) -> float | None:
    xs = [v for v in values if v is not None and math.isfinite(v)]
    if not xs:
        return None
    xs.sort()
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def mean(values: Iterable[float | None]) -> float | None:
    xs = [v for v in values if v is not None and math.isfinite(v)]
    return sum(xs) / len(xs) if xs else None


def stdev(values: Iterable[float | None]) -> float | None:
    xs = [v for v in values if v is not None and math.isfinite(v)]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def cagr(first: float | None, last: float | None, years: int | None) -> float | None:
    """复合增速，返回百分数。first/last 必须同号且 >0。"""
    if first is None or last is None or years is None or years <= 0:
        return None
    if first <= 0 or last <= 0:
        return None
    return ((last / first) ** (1.0 / years) - 1.0) * 100.0


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def linear(x: float | None, low: float, high: float, points: float) -> float | None:
    """把 low..high 线性映射到 0..points；超出范围截断。"""
    if x is None or high == low:
        return None
    return clamp((x - low) / (high - low), 0.0, 1.0) * points


def inverse(x: float | None, low: float, high: float, points: float) -> float | None:
    """越低越好：low 得满分，high 得 0 分。"""
    if x is None or high == low:
        return None
    return clamp((high - x) / (high - low), 0.0, 1.0) * points


def year_of(value: Any) -> int | None:
    m = re.search(r"(20\d{2})", str(value or ""))
    return int(m.group(1)) if m else None

