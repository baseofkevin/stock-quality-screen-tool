# -*- coding: utf-8 -*-
"""轻量校验：只检查计算链能否安全渲染，不维护旧六节硬约束。"""
from __future__ import annotations

import math
from typing import Any

import config


class ScreenError(RuntimeError):
    pass


class SkipStock(ScreenError):
    """不满足处理条件（如上市不足 3 年），跳过而不算失败。

    继承 ScreenError 是为了让「忘了接住」的地方仍按失败处理，
    但调用方应显式区分：批量写「跳过：…」、单股票模式退出码 0。
    """


def _finite(value: Any) -> bool:
    try:
        return value is None or math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def validate(data: dict[str, Any]) -> None:
    meta = data.get("meta") or {}
    if not meta.get("code"):
        raise ScreenError("缺少股票代码")
    annual = data.get("financials", {}).get("annual") or []
    if not annual:
        raise ScreenError("没有可用年报，无法计算质量分")
    # 年报数判定必须早于 Q 判定，否则会被「质量分无法计算」抢先，丢掉真正的原因。
    if len(annual) < config.MIN_ANNUAL_YEARS:
        raise SkipStock(f"上市不足 {config.MIN_ANNUAL_YEARS} 年（仅 {len(annual)} 个年报），本工具不处理")
    q = data.get("quality") or {}
    v = data.get("valuation_score") or {}
    if q.get("score") is None and not q.get("not_applicable"):
        raise ScreenError("质量分无法计算")
    # 估值分允许为空：无机构覆盖或缺少估值/增速时，报告应显示“数据不足”，而不是直接失败。
    for label, value in (("质量分", q.get("score")), ("估值分", v.get("score"))):
        if not _finite(value):
            raise ScreenError(f"{label}不是有效数字")
    checks = data.get("risks", {}).get("checks") or []
    if len(checks) != config.RISK_CHECK_COUNT:
        raise ScreenError(f"风险检查应为 {config.RISK_CHECK_COUNT} 项，实际 {len(checks)} 项")
    if not data.get("decision", {}).get("label"):
        raise ScreenError("缺少决策结论")
    if not data.get("data_quality"):
        raise ScreenError("缺少数据完整度信息")
    if not data.get("tracking"):
        raise ScreenError("缺少跟踪清单")
