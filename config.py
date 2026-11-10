# -*- coding: utf-8 -*-
"""全局阈值与权重。

所有评分都显式写在这里，不把魔法数字散落在计算代码里。
修改权重/阈值不会改变数据口径，但会改变结论；版本号写入报告页脚。
"""
from __future__ import annotations

from pathlib import Path

VERSION = "0.9.2"

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = str(PROJECT_DIR / "html-report")
# 批量模式的结果 Excel：与 html-report/ 同级，文件名沿用输入 CSV 的主名。
# 不写在输入 CSV 旁边——输入目录不该被产物污染，产物集中在一处才好找。
XLSX_OUT_DIR = str(PROJECT_DIR / "xlsx-output")

# ---- 图表窗口 -------------------------------------------------------------
TREND_YEARS = 5             # 利润率曲线看最近 5 年
TREND_QUARTERS = TREND_YEARS * 4   # 5 年 = 20 个报告季度
VALUATION_YEARS = 10        # PE/PB/PS 走势图取最近 10 年；不足 10 年按全部可用历史

# ---- 估值参数 -------------------------------------------------------------
WACC = 9.0                  # 无风险利率 + 风险溢价，默认 9%；用于 ROIC−WACC 与护城河
RISK_FREE = 2.0

# ---- 现金扣除与底线估值（仅展示，不进入 V 分） ---------------------------
CASH_ANCHOR_YEARS = (3, 5, 10, 15, 20)   # 底线价值 = 货币资金 + N × 最近年报净利润总额

# ---- 金融股 ---------------------------------------------------------------
# 银行 / 保险 / 证券没有可比的 FCF、速动比率与有息负债口径，
# 强行打分只会得到“低质量”的假象，因此直接标记不适用、不出结论。
FINANCIAL_INDUSTRY_KEYWORDS = ("银行", "保险", "证券")

# ---- 质量分权重（合计 100） ----------------------------------------------
QUALITY_WEIGHTS = {
    "returns": 30,
    "cash": 25,
    "balance": 20,
    "durability": 15,
    "accounting": 10,
}

# ---- 质量分子项满分（每组合计必须等于组权重，0.9.0 起集中在这里） ---------
# 组内缺失的子项按 0 分计入组总分，所以子项满分之和一旦与组权重不等，
# 该组会系统性偏高或偏低——tests/test_quality.py 有断言守着这一点。
QUALITY_ITEM_MAX = {
    "returns": {"spread": 14, "above_wacc": 10, "roe": 6},                  # 30
    "cash": {"fcf_years": 6, "fcf_ni": 8, "cfo_ni": 7, "fcf_margin": 4},    # 25
    "balance": {"net_debt_ebit": 8, "interest": 6, "goodwill": 6},          # 20
    "durability": {"rev_cagr": 5, "gm_stability": 4, "roe_stability": 3, "dilution": 3},  # 15
    "accounting": {"accrual": 5, "deducted": 5},                            # 10
}

# ---- 毛利率稳定性的「水平」门槛（0.9.0 起） ------------------------------
# σ 只说明“稳不稳”，不说明“高不高”：毛利率 5% 的公司 σ 再小也是稳定的低毛利，
# 不该在稳定性这一格拿满 4 分。以 15% 为下限、25% 为满分线，
# 上限 25 与护城河「定价权」用的是同一个门槛，两处口径可以互相解释。
QUALITY_GM_LEVEL_FLOOR = 15.0
QUALITY_GM_LEVEL_FULL = 25.0
QUALITY_ACCRUAL_YEARS = 3        # 应计利润取近 N 年中位数，避开单年一次性项目

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
# 检查 1 的四档判定用下面的 CASH_NI_*；第五节跟踪表的阈值也用 CASH_NI_OK，
# 不再单独维护一个 0.8 的“跟踪线”（两处口径打架会让读者以为哪个算错了）。
FCF_NEGATIVE_YEARS = 3
NET_DEBT_EBIT_MAX = 3.0
INTEREST_COVER_MIN = 3.0
GOODWILL_EQUITY_MAX = 0.20
GOODWILL_EQUITY_FATAL = 0.50
NONRECURRING_RATIO_MIN = 0.70
# 应收占营收不足该比例时，增长率没有意义（茅台应收只有 260 万元），该子项跳过
AR_BASE_RATIO_MIN = 0.005

# ---- 风险检查分组（0.8.0 起 14 项 / 4 组） -------------------------------
RISK_CHECK_COUNT = 14
RISK_GROUPS = ("真伪", "趋势", "质量", "安全")
# 命中后必须在结论行点名的硬判定项（不进入 _fatal()，只影响展示优先级）
RISK_HEADLINE_KEYS = ("cash_flow", "cash_debt")
# 金融股（银行/保险/证券）这些科目的口径与工商企业不可比，直接标不适用
FINANCIAL_INAPPLICABLE_CHECKS = (
    "margin_improve", "ar_gap", "inventory_gap", "construction", "cash_debt",
)

# ---- 第一节：护城河三证据（0.8.0 起替代 5 项加权评分） -------------------
MOAT_GROSS_MARGIN_MIN = 25.0     # 定价权：5 年毛利率中位数下限（%）
MOAT_GROSS_MARGIN_STD = 3.0      # 定价权：5 年毛利率标准差上限（pct）
MOAT_ROIC_SPREAD_MIN = 5.0       # 资本回报：ROIC − WACC 下限（pct）
MOAT_ROIC_ABOVE_YEARS = 4        # 资本回报：5 年中至少高于 WACC 的年数
MOAT_FCF_MARGIN_MIN = 5.0        # 现金创造：FCF/营收中位数下限（%）
MARGIN_IMPROVE_EPS = 0.05        # 毛利率环比判定容差（pct），差 0.01pct 不算改善
PAYABLE_SLIP_WEAK = 0.30         # 占款比 <0.3 = 几乎不占供应商款
PAYABLE_SLIP_STRONG = 1.00       # 占款比 ≥1 = 两头通吃

# ---- 第二节：14 项检查阈值 -----------------------------------------------
CASH_NI_GOOD = 1.00              # 净现比 >1 优秀
CASH_NI_OK = 0.70                # 0.7~1 健康
CASH_NI_WEAK = 0.30              # 0.3~0.7 警惕，<0.3 危险
CASH_NI_TWO_YEAR = 0.50          # 连续 2 年 <0.5 直接高危
CASH_DEBT_RATIO_MIN = 1.00       # 现金短债比 <1 紧张
CASH_DEBT_RATIO_FATAL = 0.50     # <0.5 高危
CASH_DEBT_RATIO_CALM = 5.00      # >5 一律显示"无短债压力"
AR_REV_GAP_ALERT = 0.15          # 应收增速差 >15pct 关注
AR_MATERIAL_RATIO = 0.02         # 应收/营收 <2% 只记录，不计命中
INV_REV_GAP_ALERT = 0.15         # 存货增速差 >15pct 关注
INV_REV_GAP_HIGH = 0.30          # >30pct 或连续 2 年 >15pct 高危
INV_MATERIAL_RATIO = 0.01        # 存货/营收 <1% 跳过（300058 存货 0.13 亿）
GOODWILL_EQUITY_WARN = 0.30      # 商誉 30% 高危机（20% 用 GOODWILL_EQUITY_MAX）
OTHER_AR_ASSETS_MAX = 0.02       # 其他应收款/总资产 2%
CL_GROWTH_MIN = 0.20             # 合同负债同比 20%
CL_REV_MIN = 0.02                # 合同负债占营收 2%
EXPENSE_GROWTH_GAP = 0.10        # 期间费用增速 − 营收增速 10pct
QUICK_RATIO_WATCH = 0.70         # 速动 <0.7 记 1 分（手册口径，不单独否决）

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
    "cash_flow", "leverage", "goodwill", "nonrecurring", "cash_debt",
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
