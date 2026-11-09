# -*- coding: utf-8 -*-
"""取数层：腾讯自选股 5 次调用 + 东方财富 3 次调用。

默认网络取数；`--bundle old-raw.json` 可离线重放旧采集包，便于测试和复盘。
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "providers" / "westock_client.js"

sys.path.insert(0, str(ROOT / "providers"))
import eastmoney  # noqa: E402


class DataError(RuntimeError):
    pass


def _env_seconds_ms(name: str, default_ms: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, str(default_ms))) / 1000.0)
    except (TypeError, ValueError):
        return default_ms / 1000.0


# 进程内全局节流：多个批量线程共用同一个腾讯接口调用节奏。
# westock_client.js 里的 WESTOCK_INTERVAL 是“每个 node 进程”的间隔，
# 4 个线程并发时实际请求速率会放大 4 倍，因此这里再加一道跨线程闸门。
GLOBAL_INTERVAL = _env_seconds_ms("WESTOCK_GLOBAL_INTERVAL_MS", 1600)
_GLOBAL_LOCK = threading.Lock()
_NEXT_CALL_AT = 0.0


def _throttle() -> None:
    global _NEXT_CALL_AT
    if GLOBAL_INTERVAL <= 0:
        return
    with _GLOBAL_LOCK:
        now = time.monotonic()
        wait = _NEXT_CALL_AT - now
        if wait > 0:
            time.sleep(wait)
        _NEXT_CALL_AT = time.monotonic() + GLOBAL_INTERVAL


_RETRY_MARKERS = (
    "不是 JSON", "限频", "429", "超时", "timed out", "Timeout",
    "连接", "ECONN", "network", "502", "503", "504",
)


def _is_retryable(exc: BaseException) -> bool:
    text = str(exc)
    return any(marker in text for marker in _RETRY_MARKERS)


def normalize_code(raw: str) -> str:
    s = str(raw or "").strip().lower()
    # 支持 600519.SH / 600519.sh / sh600519 / 600519
    if "." in s:
        left, right = s.rsplit(".", 1)
        if left.isdigit() and right in {"sh", "sz", "bj"}:
            s = right + left
        else:
            s = s.replace(".", "")
    if len(s) == 8 and s[:2] in {"sh", "sz", "bj"} and s[2:].isdigit():
        return s
    if not (len(s) == 6 and s.isdigit()):
        raise ValueError(f"股票代码应为 600519 / sh600519 / 600519.SH：{raw!r}")
    if s.startswith("920"):
        return f"bj{s}"
    if s.startswith(("6", "9")):
        return f"sh{s}"
    if s.startswith(("4", "8")):
        return f"bj{s}"
    return f"sz{s}"


def six(code: str) -> str:
    return normalize_code(code)[2:]


class WestockClient:
    def __init__(self, timeout: float = 90.0, retries: int = 0, retry_wait: float = 60.0):
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self.retry_wait = max(0.0, float(retry_wait))

    def _call_once(self, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        cmd = ["node", str(CLIENT), "call", tool, json.dumps(params, ensure_ascii=False)]
        env = os.environ.copy()
        env.setdefault("WESTOCK_TIMEOUT", str(int(self.timeout * 1000)))
        env.setdefault("WESTOCK_INTERVAL", "1600")
        _throttle()
        try:
            proc = subprocess.run(
                cmd, cwd=str(ROOT), env=env, capture_output=True, text=True,
                timeout=self.timeout + 15,
            )
        except subprocess.TimeoutExpired as exc:
            raise DataError(f"{tool} 请求超时（>{self.timeout:.0f}s）") from exc
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise DataError(f"{tool} 调用失败：{msg[0] if msg else '未知错误'}")
        try:
            obj = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise DataError(f"{tool} 返回不是 JSON：{proc.stdout[:200]}") from exc
        if isinstance(obj, dict) and obj.get("ok") is False:
            raise DataError(f"{tool} 返回失败：{obj.get('msg') or obj}")
        return obj

    def call(self, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        last: DataError | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._call_once(tool, params)
            except DataError as exc:
                last = exc
                if attempt >= self.retries or not _is_retryable(exc):
                    raise
                time.sleep(self.retry_wait + random.uniform(0, 5))
        raise last or DataError(f"{tool} 调用失败")


def _call(client: WestockClient, tool: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"tool": tool, "params": params, "response": client.call(tool, params)}


def fetch_all(code: str, timeout: float = 90.0, retries: int = 0,
              retry_wait: float = 60.0) -> dict[str, Any]:
    """返回 {code, calls, errors}；calls 与旧 raw bundle 兼容。"""
    c = normalize_code(code)
    client = WestockClient(timeout=timeout, retries=retries, retry_wait=retry_wait)
    calls: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    required = [
        ("data_finance", {"code": c, "fields": "all", "num": 20}),
        ("data_quote", {"code": c}),
    ]
    for tool, params in required:
        try:
            calls.append(_call(client, tool, params))
        except Exception as exc:  # noqa: BLE001
            raise DataError(f"关键数据 {tool} 获取失败：{exc}") from exc

    optional = [
        ("data_profile", {"code": c}),
        ("data_consensus", {"code": c}),
        ("data_rating", {"code": c}),
    ]
    for tool, params in optional:
        try:
            calls.append(_call(client, tool, params))
        except Exception as exc:  # noqa: BLE001
            errors.append({"tool": tool, "error": str(exc)})

    val = eastmoney.fetch_valuation(c, timeout=min(timeout, 30.0))
    calls.append({
        "tool": "RPT_VALUEANALYSIS_DET",
        "params": {"code": c},
        "response": {"result": {"data": val["rows"], "pages": val["pages"]}},
        "error": val.get("error"),
    })
    if val.get("error"):
        errors.append({"tool": "RPT_VALUEANALYSIS_DET", "error": val["error"]})

    mainop = eastmoney.fetch_mainop(c, timeout=min(timeout, 30.0))
    calls.append({
        "tool": "RPT_F10_FN_MAINOP",
        "params": {"code": c},
        "response": {"result": {"data": mainop["rows"], "pages": 1}},
        "error": mainop.get("error"),
    })
    if mainop.get("error"):
        errors.append({"tool": "RPT_F10_FN_MAINOP", "error": mainop["error"]})

    capex = eastmoney.fetch_capex(c, timeout=min(timeout, 30.0))
    calls.append({
        "tool": "RPT_F10_FINANCE_GCASHFLOW",
        "params": {"code": c},
        "response": {"result": {"data": capex["rows"], "pages": 1}},
        "error": capex.get("error"),
    })
    if capex.get("error"):
        errors.append({"tool": "RPT_F10_FINANCE_GCASHFLOW", "error": capex["error"]})

    return {"code": c, "calls": calls, "errors": errors}


def load_bundle(path: str | Path) -> dict[str, Any]:
    """读取旧采集包 / 测试 fixture；只作为输入，不生成新 JSON。"""
    p = Path(path)
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"采集包读取失败：{exc}") from exc
    calls = obj.get("calls")
    if not isinstance(calls, list) or not calls:
        raise DataError("采集包里没有 calls")
    code = obj.get("code") or ""
    for call in calls:
        params = call.get("params") or {}
        if not code and params.get("code"):
            code = params["code"]
    if not code:
        raise DataError("采集包里没有代码")
    return {"code": normalize_code(code), "calls": calls, "errors": obj.get("errors") or []}


def call_map(calls: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """同名工具只保留最后一条；估值分页由 compute 自己合并。"""
    out: dict[str, dict[str, Any]] = {}
    for call in calls:
        tool = call.get("tool")
        if tool:
            out[tool] = call
    return out
