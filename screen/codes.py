# -*- coding: utf-8 -*-
"""股票代码的市场前缀：全项目唯一一份规则。

同一件事以前写了三遍（`fetch.normalize_code` / `batch.eastmoney_url` /
`providers.eastmoney.to_secucode`），三处目前一致，但加一个号段就得改三处、
漏一处就出「查不到这只股票」的怪问题。现在只在这里判断号段，三处各自只保留
「无法识别时是抛错还是返回空串」「输出哪种格式」这点差别。

号段规则（与交易所一致）：
    920 / 4 / 8 开头 → 北交所（bj）
    6 / 9 开头       → 上交所（sh），含 688 科创板与 900 B 股
    其余 6 位数字    → 深交所（sz），含 000/002/300
"""
from __future__ import annotations

MARKETS = ("sh", "sz", "bj")


def split(raw: str) -> tuple[str | None, str] | None:
    """拆成 (显式前缀或 None, 6 位数字)；无法识别返回 None。

    显式前缀要保留，不能一律按号段重算：`sz600519` 这种写法虽然号段对不上，
    但调用方明确指定了交易所，照原样用（腾讯接口两种写法都认）。
    """
    s = str(raw or "").strip().lower()
    if "." in s:
        left, right = s.rsplit(".", 1)
        if left.isdigit() and right in MARKETS:
            return right, left
        s = s.replace(".", "")
    if len(s) == 8 and s[:2] in MARKETS and s[2:].isdigit():
        return s[:2], s[2:]
    if len(s) == 6 and s.isdigit():
        return None, s
    return None


def market_of(digits: str) -> str:
    """6 位数字 → 交易所前缀。"""
    if digits.startswith("920"):
        return "bj"
    if digits.startswith(("6", "9")):
        return "sh"
    if digits.startswith(("4", "8")):
        return "bj"
    return "sz"


def normalize(raw: str) -> str:
    """600519 / sh600519 / 600519.SH → sh600519；无法识别抛 ValueError。"""
    parts = split(raw)
    if parts is None:
        raise ValueError(f"股票代码应为 600519 / sh600519 / 600519.SH：{raw!r}")
    market, digits = parts
    return f"{market or market_of(digits)}{digits}"


def six(raw: str) -> str:
    """→ 600519（不带前缀）；无法识别抛 ValueError。"""
    return normalize(raw)[2:]


def secucode(raw: str) -> str:
    """→ 600519.SH（东方财富 datacenter 用的写法）；无法识别抛 ValueError。"""
    parts = split(raw)
    if parts is None:
        raise ValueError(f"代码格式错误：{raw!r}")
    market, digits = parts
    return f"{digits}.{(market or market_of(digits)).upper()}"


def eastmoney_url(raw: str) -> str:
    """→ 东方财富个股页；无法识别返回空串。

    这里不抛错：批量里代码列可能混进空行或备注，标「无链接」比整批失败合适。
    """
    parts = split(raw)
    if parts is None:
        return ""
    market, digits = parts
    market = market or market_of(digits)
    if market == "bj":
        # 北交所在东方财富用的是 /bj/920001.html 这种路径，不是 bj920001.html
        return f"https://quote.eastmoney.com/bj/{digits}.html#fullScreenChart"
    return f"https://quote.eastmoney.com/{market}{digits}.html#fullScreenChart"
