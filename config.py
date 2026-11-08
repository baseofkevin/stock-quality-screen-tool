# -*- coding: utf-8 -*-
"""全局阈值与权重。

所有评分都显式写在这里，不把魔法数字散落在计算代码里。
修改权重/阈值不会改变数据口径，但会改变结论；版本号写入报告页脚。
"""
from __future__ import annotations

from pathlib import Path

VERSION = "0.6.1"

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = str(PROJECT_DIR / "html-report")

# ---- 图表窗口 -------------------------------------------------------------
TREND_QUARTERS = 15         # 利润率、估值曲线都只看最近 15 个报告季度

# ---- 估值参数 -------------------------------------------------------------
WACC = 9.0                  # 无风险利率 + 风险溢价，默认 9%；取不到 WACC 时使用
DCF_G = 2.5                 # 永续增速，固定
DCF_YEARS = 10
REQUIRED_FCF_YIELD = 5.0    # FCF 收益率达到 5% 视为估值合理线
RISK_FREE = 2.0

# ---- 现金扣除与底线估值（仅展示，不进入 V 分） ---------------------------
CASH_ANCHOR_YEARS = (3, 5, 10, 15, 20)   # 底线价值 = 货币资金 + N × 最近年报净利润总额

# ---- 质量分权重（合计 100） ----------------------------------------------
QUALITY_WEIGHTS = {
    "returns": 30,
    "cash": 25,
    "balance": 20,
    "durability": 15,
    "accounting": 10,
}

# ---- 估值分权重（合计 100，机构口径） ------------------------------------
# V = 机构对企业的估值 60 + 预期未来净利增速 40
# 机构估值内部：目标价空间 40 + 预测 PE 相对当前 PE 20
VALUATION_WEIGHTS = {
    "target_upside": 40,
    "forecast_pe": 20,
    "profit_growth": 40,
}

# 打分区间：原始值从低到高线性映射到 0~100
VALUATION_RANGES = {
    "target_upside": (-30.0, 30.0),   # 目标价空间，0% 得 50 分
    "forecast_pe": (-20.0, 20.0),     # 当前 PE / 预测 PE - 1，0% 得 50 分
    "profit_growth": (-15.0, 25.0),   # 未来 1~3 年净利增速均值，0% 得 37.5 分
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

# ---- 质量调整后的买入门槛 ------------------------------------------------
# Q 越高，要求的 V 越低；Q<45 时无论 V 多高都禁止买入。
QUALITY_HARD_FLOOR = 45.0
BUY_MIN_V = {
    "high": 65.0,          # Q >= 75
    "medium_high": 70.0,   # 65 <= Q < 75
    "medium": 75.0,        # 55 <= Q < 65
    "weak": 80.0,          # 45 <= Q < 55
}
BUY_KEYS = ("buy", "buy_ok", "buy_small", "buy_trial")

# ---- 可买的数据前置条件 ---------------------------------------------------
# 可买不能只看 Q/V；数据不够时先降为“观察”，不输出可买。
BUY_MIN_INSTITUTION_COVERAGE = 3       # 机构覆盖少于 3 家，不给出可买
BUY_MIN_QUALITY_COVERAGE = 80.0        # Q 分数据覆盖低于 80%，不给出可买
BUY_CRITICAL_CHECKS = (                # 这些风险检查缺失时，不给出可买
    "cfo_ni", "leverage", "goodwill", "nonrecurring", "liquidity",
)

# ---- 决策矩阵 -------------------------------------------------------------
DECISION_RULES = [
    ("buy", "推荐买入", "高质量且估值便宜"),
    ("buy_ok", "可买", "质量中等偏上，估值便宜"),
    ("buy_small", "小仓买入", "质量一般，估值足够便宜"),
    ("buy_trial", "小仓试错", "质量偏弱，但估值明显低估"),
    ("watch_price", "好公司，等价格", "质量通过，估值不够便宜"),
    ("expensive", "好公司，但太贵", "质量通过，估值明显偏贵"),
    ("watch", "观察", "质量或估值不够，或数据不完整"),
    ("avoid", "回避", "质量低于硬门槛或出现致命风险"),
    ("unknown", "数据不足，不下结论", "关键数据不足，无法可靠判断"),
]
