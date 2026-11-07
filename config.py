# -*- coding: utf-8 -*-
"""全局阈值与权重。

所有评分都显式写在这里，不把魔法数字散落在计算代码里。
修改权重/阈值不会改变数据口径，但会改变结论；版本号写入报告页脚。
"""
from __future__ import annotations

VERSION = "0.1.0"

DEFAULT_OUT_DIR = "~/企业质量初筛"

# ---- 估值参数 -------------------------------------------------------------
WACC = 9.0                  # 无风险利率 + 风险溢价，默认 9%；取不到 WACC 时使用
DCF_G = 2.5                 # 永续增速，固定
DCF_YEARS = 10
REQUIRED_FCF_YIELD = 5.0    # FCF 收益率达到 5% 视为估值合理线
RISK_FREE = 2.0

# ---- 质量分权重（合计 100） ----------------------------------------------
QUALITY_WEIGHTS = {
    "returns": 30,
    "cash": 25,
    "balance": 20,
    "durability": 15,
    "accounting": 10,
}

# ---- 估值分权重（合计 100） ----------------------------------------------
VALUATION_WEIGHTS = {
    "multiples": 50,
    "fcf_yield": 30,
    "dcf": 20,
}

# ---- 风险阈值 -------------------------------------------------------------
CFO_NI_FLOOR = 0.8
FCF_NEGATIVE_YEARS = 3
NET_DEBT_EBIT_MAX = 3.0
INTEREST_COVER_MIN = 3.0
GOODWILL_EQUITY_MAX = 0.20
GOODWILL_EQUITY_FATAL = 0.50
NONRECURRING_RATIO_MIN = 0.70
SHARE_DILUTION_MAX = 0.02
CURRENT_RATIO_MIN = 1.0
QUICK_RATIO_MIN = 0.8
REVENUE_GROWTH_NEGATIVE = 0.0
AR_INV_GROWTH_ALERT = 0.10

# ---- 决策矩阵 -------------------------------------------------------------
DECISION_RULES = [
    ("buy", "可买（初筛通过）", "质量与估值同时通过"),
    ("watch_price", "好公司，等价格", "质量通过，估值不够便宜"),
    ("expensive", "好公司，但太贵", "质量通过，估值明显偏贵"),
    ("watch", "观察，不建议现在买", "质量中等或关键数据不完整"),
    ("avoid", "回避", "质量不足或出现致命风险"),
    ("unknown", "数据不足，不下结论", "关键数据不足，无法可靠判断"),
]
