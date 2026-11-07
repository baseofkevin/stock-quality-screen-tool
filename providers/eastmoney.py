# -*- coding: utf-8 -*-
"""东方财富数据：历史估值序列 + F10 资本支出。

只保留项目需要的两个报表，不引入旧 skill 的任何脚本。
接口为 datacenter.eastmoney.com；如接口字段变化，只改本文件。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

API = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


class EastMoneyError(RuntimeError):
    pass


def to_secucode(code: str) -> str:
    """sh600519 / 600519 / 600519.SH → 600519.SH。"""
    raw = str(code or "").strip().upper().replace(".", "")
    if len(raw) == 8 and raw[:2] in {"SH", "SZ", "BJ"}:
        raw = raw[2:]
    if not (len(raw) == 6 and raw.isdigit()):
        raise ValueError(f"代码格式错误：{code!r}")
    if raw.startswith("920"):
        return f"{raw}.BJ"
    if raw.startswith(("6", "9")):
        return f"{raw}.SH"
    if raw.startswith(("4", "8")):
        return f"{raw}.BJ"
    return f"{raw}.SZ"


def _get(params: dict[str, Any], timeout: float = 25.0, retries: int = 2) -> dict[str, Any]:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise EastMoneyError("接口返回不是对象")
            return data
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, EastMoneyError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise EastMoneyError(f"东方财富请求失败：{last}")


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    rows = result.get("data")
    return rows if isinstance(rows, list) else []


def _pages(payload: dict[str, Any]) -> int:
    result = payload.get("result")
    try:
        return max(1, min(int((result or {}).get("pages") or 1), 30))
    except (TypeError, ValueError):
        return 1


def _fetch_pages(report: str, columns: str, filter_text: str, *, sort: str = "REPORT_DATE",
                 order: str = "-1", page_size: int = 500, timeout: float = 25.0) -> dict[str, Any]:
    params = {
        "reportName": report,
        "columns": columns,
        "pageNumber": 1,
        "pageSize": page_size,
        "sortColumns": sort,
        "sortTypes": order,
        "source": "HSF10",
        "client": "PC",
        "filter": filter_text,
    }
    first = _get(params, timeout=timeout)
    rows = _rows(first)
    pages = _pages(first)
    for page in range(2, pages + 1):
        params["pageNumber"] = page
        rows.extend(_rows(_get(params, timeout=timeout)))
    return {"pages": pages, "rows": rows}


def fetch_valuation(code: str, *, timeout: float = 25.0) -> dict[str, Any]:
    """拉取历史估值序列（日频，计算时再压缩为周频）。"""
    try:
        secu = to_secucode(code)
        data = _fetch_pages(
            "RPT_VALUEANALYSIS_DET",
            "SECUCODE,TRADE_DATE,PE_TTM,PB_MRQ,PS_TTM",
            f'(SECUCODE="{secu}")',
            sort="TRADE_DATE",
            order="1",
            page_size=1000,
            timeout=timeout,
        )
        return {"ok": True, "rows": data["rows"], "pages": data["pages"], "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rows": [], "pages": 0, "error": str(exc)}


def fetch_mainop(code: str, *, years: int = 4, timeout: float = 25.0) -> dict[str, Any]:
    """拉取主营构成。MAINOP_TYPE=2 为产品/业务分部，含收入占比与成本。"""
    try:
        secu = to_secucode(code)
        start = f"{date.today().year - years}-12-31"
        data = _fetch_pages(
            "RPT_F10_FN_MAINOP",
            "SECUCODE,REPORT_DATE,MAINOP_TYPE,ITEM_NAME,MAIN_BUSINESS_INCOME,MBI_RATIO,MAIN_BUSINESS_COST",
            f'(SECUCODE="{secu}")(REPORT_DATE>=\'{start}\')',
            sort="REPORT_DATE",
            order="-1",
            page_size=500,
            timeout=timeout,
        )
        return {"ok": True, "rows": data["rows"], "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rows": [], "error": str(exc)}


def fetch_capex(code: str, *, years: int = 7, timeout: float = 25.0) -> dict[str, Any]:
    """拉取年报资本支出（构建长期资产支付的现金），单位元。"""
    try:
        secu = to_secucode(code)
        start = f"{date.today().year - years}-12-31"
        data = _fetch_pages(
            "RPT_F10_FINANCE_GCASHFLOW",
            "SECUCODE,REPORT_DATE,CONSTRUCT_LONG_ASSET",
            f'(SECUCODE="{secu}")(REPORT_DATE>=\'{start}\')',
            sort="REPORT_DATE",
            order="-1",
            page_size=500,
            timeout=timeout,
        )
        return {"ok": True, "rows": data["rows"], "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rows": [], "error": str(exc)}
