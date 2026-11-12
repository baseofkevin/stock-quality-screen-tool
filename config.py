# -*- coding: utf-8 -*-
"""全局阈值与权重。

所有评分都显式写在这里，不把魔法数字散落在计算代码里。
修改权重/阈值不会改变数据口径，但会改变结论；版本号写入报告页脚。
"""
from __future__ import annotations

from pathlib import Path

VERSION = "0.9.10"

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = str(PROJECT_DIR / "html-report")
# 批量模式的产物只有两处：html-report/ 里的单股 HTML、同目录的导航页。
# 输入 CSV 本身只读：批量不写任何 CSV，输入表一个字节都不动。

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

# 五个维度的中文名。以前这几个名字写在 score._group() 调用里、又写了一遍在
# render 的说明文字里，改一处就出现「表里叫资本回报、正文叫回报能力」。
QUALITY_GROUP_LABELS = {
    "returns": "资本回报",
    "cash": "现金创造力",
    "balance": "资产负债表",
    "durability": "成长与稳定",
    "accounting": "会计质量",
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

# ---- 质量分子项的打分区间（0.9.8 起） -------------------------------------
# 每项 (下界, 上界, 方向)：方向 up = 越大越好（到上界满分），down = 越小越好（到下界满分）。
# 以前这 13 组区间硬编码在 score.py 的 _item(...) 里，改 config 的满分只改一半：
# 满分改了、区间没改，Q 会悄悄偏。比值型子项（ROIC 高于 WACC 的年数、FCF 为正年数）
# 没有区间，按「已知年数里占几成」算，所以不在下表里。
QUALITY_ITEM_RANGES = {
    "returns": {
        "spread": (0.0, 15.0, "up"),          # ROIC − WACC，pct
        "roe": (8.0, 20.0, "up"),             # ROE 中位数，%
    },
    "cash": {
        "fcf_ni": (0.0, 1.0, "up"),           # FCF / 净利润
        "cfo_ni": (0.7, 1.2, "up"),           # CFO / 净利润
        "fcf_margin": (0.0, 15.0, "up"),      # FCF / 营收，%
    },
    "balance": {
        "net_debt_ebit": (0.0, 3.0, "down"),  # 净有息负债 / EBIT
        "interest": (3.0, 10.0, "up"),        # 利息保障倍数
        "goodwill": (0.0, 20.0, "down"),      # 商誉 / 归母净资产，%
    },
    "durability": {
        "rev_cagr": (0.0, 15.0, "up"),        # 营收 CAGR，%
        "gm_stability": (0.0, 5.0, "down"),   # 毛利率标准差，pct（还要再乘水平系数）
        "roe_stability": (0.0, 8.0, "down"),  # ROE 标准差，pct
        "dilution": (0.0, 3.0, "down"),       # 股本 CAGR，%
    },
    "accounting": {
        "accrual": (0.0, 10.0, "down"),       # 应计利润 / 总资产，%
        "deducted": (70.0, 100.0, "up"),      # 扣非净利润占比，%
    },
}

# ---- 质量分档（报告里的「分档」说明读这张表） -----------------------------
# (下限含, 档名)：等级只是标签，不参与打分、不改变结论。
QUALITY_GRADES = (
    (85.0, "优秀"),
    (75.0, "良好"),
    (65.0, "中等偏上"),
    (55.0, "中等"),
    (45.0, "偏弱"),
    (0.0, "差"),
)

# 报告里分数条的配色（只影响观感，不参与判断）：≥65 绿、<45 红，中间保持中性。
# 65 是「中等偏上」的下限，45 必须与 QUALITY_HARD_FLOOR 相同（tests/test_quality.py 有断言守着）。
SCORE_BAR_GOOD = 65.0
SCORE_BAR_BAD = 45.0

# ---- 毛利率稳定性的「水平」门槛（0.9.0 起） ------------------------------
# σ 只说明“稳不稳”，不说明“高不高”：毛利率 5% 的公司 σ 再小也是稳定的低毛利，
# 不该在稳定性这一格拿满 4 分。以 15% 为下限、25% 为满分线，
# 上限 25 与护城河「定价权」用的是同一个门槛，两处口径可以互相解释。
QUALITY_GM_LEVEL_FLOOR = 15.0
QUALITY_GM_LEVEL_FULL = 25.0
QUALITY_ACCRUAL_YEARS = 3        # 应计利润取近 N 年中位数，避开单年一次性项目

# 上市不足 3 年（年报 <3 个）不处理：5 年口径的 Q、稳定性 σ、CAGR 在 2 年数据上没有意义。
# 这是硬门槛——不足者整只股票跳过（批量标「跳过：上市不足 3 年」，不算失败），
# 不出「数据不足」的半成品报告。见 screen/validate.py::SkipStock。
MIN_ANNUAL_YEARS = 3

# ---- 估值分权重（合计 100，机构口径） ------------------------------------
# V = 机构对企业的估值 60 + 预期未来净利增速 40
# 机构估值内部：目标价空间 40 + 预测 PE 相对当前 PE 20
VALUATION_WEIGHTS = {
    "target_upside": 40,
    "forecast_pe": 20,
    "profit_growth": 40,
}

# V 三个子项的名字：score 的构成表、render 的说明文字都读这里，避免「表里一套说法、
# 正文另一套说法」。改名字只改这一处。
VALUATION_WEIGHT_TEXT = {
    "target_upside": "机构目标价空间",
    "forecast_pe": "预测 PE 相对当前 PE",
    "profit_growth": "预期未来净利增速",
}

# 打分区间：原始值从低到高线性映射到 0~100
VALUATION_RANGES = {
    "target_upside": (-30.0, 30.0),   # 目标价空间，0% 得 50 分
    "forecast_pe": (-20.0, 20.0),     # 当前 PE / 预测 PE - 1，0% 得 50 分
    "profit_growth": (-15.0, 25.0),   # 未来 1~3 年净利增速均值，0% 得 37.5 分
}

# ---- 历史分位的七档（0.9.3 起，第三节「估值位置」那段话用） --------------
# 分位表只给数字，读者得自己判断「18% 算便宜吗」。这里把 0~100% 切成七档，
# 由 render._valuation_verdict() 读成一句话。切点的用意：
#   30 / 70 —— 沿用原来的「下/上三分之一」，口语对得上；
#   10 / 90 —— 「贴着历史上下沿」，PB 6% 这种说「偏便宜」太轻，必须单独一档；
#   45 / 55 —— 中间留一格「正中」，否则 49% 会被塞进「中偏低」，读着别扭。
# 每组：(下界含, 上界不含, 档名, 结论词)。结论词只有「便宜 ↔ 贵」一维。
VAL_BANDS = (
    (0.0, 10.0, "历史底部", "明显偏便宜"),
    (10.0, 30.0, "下三分之一", "偏便宜"),
    (30.0, 45.0, "中偏低", "略偏便宜"),
    (45.0, 55.0, "正中", "中性"),
    (55.0, 70.0, "中偏高", "略偏贵"),
    (70.0, 90.0, "上三分之一", "偏贵"),
    (90.0, 100.1, "历史顶部", "明显偏贵"),
)
# 三个口径的分位跨度（最高 − 最低）在 25pp 以内，当作同一位置，一句话下结论；
# 超过才补一句「谁比谁便宜」。门槛再低的话几乎每只股票都要读一句分歧，反而没信息量。
VAL_SPREAD_TOL = 25.0
VAL_SPREAD_STRONG = 45.0   # 跨度超过这个值，措辞从「比」升到「明显比」
# 分位样本不足 1 年（52 个周样本）时不给七档档位：
# 10 个周样本落在序列最高点，也会被读成「历史顶部，估值明显偏贵」，
# 这个结论只反映「这只股票上市没多久」，不反映估值位置。
VAL_MIN_SAMPLE_WEEKS = 52

# ---- 风险阈值 -------------------------------------------------------------
# 检查 1 的四档判定用下面的 CASH_NI_*；第五节跟踪表的阈值也用 CASH_NI_OK，
# 不再单独维护一个 0.8 的“跟踪线”（两处口径打架会让读者以为哪个算错了）。
FCF_NEGATIVE_YEARS = 3
NET_DEBT_EBIT_MAX = 3.0
INTEREST_COVER_MIN = 3.0
# 商誉/归母净资产三档。0.9.8 前叫 MAX(0.20) / WARN(0.30)，名字与数值反着，
# 谁读都会把分支写反：WATCH 才是警惕线，HIT 是高危线，FATAL 是一票否决线。
GOODWILL_EQUITY_WATCH = 0.20
GOODWILL_EQUITY_HIT = 0.30
GOODWILL_EQUITY_FATAL = 0.50

# 应收占营收不足该比例时，增长率没有意义（茅台应收只有 260 万元），该子项跳过
AR_BASE_RATIO_MIN = 0.005
NONRECURRING_RATIO_MIN = 0.70     # 扣非净利润 / 净利润 下限，低于该值视为利润靠非经常性损益

# ---- 一票否决线（score._fatal() 的四条，报告第二节末段按这些数字生成说明） --
INTEREST_COVER_FATAL = 1.0     # 利息保障 <1：经营利润不够付利息
FATAL_NET_DEBT_EBIT = 4.0      # 连续 N 年经营现金流为负 且 净负债/EBIT > 4

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
OTHER_AR_ASSETS_MAX = 0.02       # 其他应收款/总资产 2%
CL_GROWTH_MIN = 0.20             # 合同负债同比 20%
CL_REV_MIN = 0.02                # 合同负债占营收 2%
CL_RATIO_STRONG = 2.0            # 合同负债/营收 ≥2% 才算「预收型强势」（占款比低时的另一种强）
EXPENSE_GROWTH_GAP = 0.10        # 期间费用增速 − 营收增速 10pct
QUICK_RATIO_WATCH = 0.70         # 速动 <0.7 记 1 分（手册口径，不单独否决）

# ---- 质量调整后的买入门槛 ------------------------------------------------
# Q 越高，要求的 V 越低；Q<45 时无论 V 多高都禁止买入。
# 具体的「每个 Q 档要求多少 V」写在下面的 DECISION_MATRIX 里，不再单独维护一份
# BUY_MIN_V（0.9.8 删掉：它与矩阵是同一批数字，两份必然有一天对不上）。
QUALITY_HARD_FLOOR = 45.0
BUY_KEYS = ("buy", "buy_ok", "buy_small", "buy_trial")


# ---- 可买的数据前置条件 ---------------------------------------------------
# 可买不能只看 Q/V；数据不够时先降为“观察”，不输出可买。
BUY_MIN_INSTITUTION_COVERAGE = 3       # 机构覆盖少于 3 家，不给出可买
BUY_MIN_QUALITY_COVERAGE = 80.0        # Q 分数据覆盖低于 80%，不给出可买
BUY_CRITICAL_CHECKS = (                # 这些风险检查缺失时，不给出可买
    "cash_flow", "leverage", "goodwill", "nonrecurring", "cash_debt",
)

# ---- 决策矩阵 -------------------------------------------------------------
# 0.9.8 起矩阵只写在这里：score._decision() 按 (q_min, v_min) 取结果，
# render 的「决策规则」说明文字也从同一张表生成。
# 以前矩阵在 score.py、说明文字在 render.py，改一个门槛就变成「说一套、算一套」——
# 而且旧说明里 Q≥75 那档写的是「50~65 等价格」，代码其实是 50~65 之外还有 35~50，两边对不上。
#
# 每档：q_min 是 Q 的下限（含），rules 按 V 从高到低排，v_min=None 是兜底档。
#   text 只给说明文字用（一句话一行，越短越好）；label/reason 是结论本身，进 CSV 和报告。
DECISION_MATRIX = (
    {
        "q_min": 75.0,
        "rules": (
            {"v_min": 65.0, "key": "buy", "label": "推荐买入",
             "reason": "质量好且估值便宜", "text": "推荐买入"},
            {"v_min": 50.0, "key": "watch_price", "label": "好公司，等价格",
             "reason": "质量通过，估值尚未到舒服区间", "text": "等价格"},
            {"v_min": 35.0, "key": "expensive", "label": "好公司，但偏贵，等价格",
             "reason": "质量通过，估值偏贵", "text": "偏贵"},
            {"v_min": None, "key": "expensive", "label": "好公司，但太贵",
             "reason": "质量通过，估值明显偏贵", "text": "太贵"},
        ),
    },
    {
        "q_min": 65.0,
        "rules": (
            {"v_min": 80.0, "key": "buy", "label": "推荐买入",
             "reason": "质量中等偏上，估值明显低估", "text": "推荐买入"},
            {"v_min": 70.0, "key": "buy_ok", "label": "可买",
             "reason": "质量中等偏上，估值便宜", "text": "可买"},
            {"v_min": 50.0, "key": "watch", "label": "观察",
             "reason": "质量中等偏上，估值不够便宜", "text": "观察"},
            {"v_min": None, "key": "avoid", "label": "回避",
             "reason": "质量中等偏上，但估值不便宜", "text": "回避"},
        ),
    },
    {
        "q_min": 55.0,
        "rules": (
            {"v_min": 75.0, "key": "buy_small", "label": "小仓买入",
             "reason": "质量一般，估值足够便宜，仅小仓", "text": "小仓买入"},
            {"v_min": 50.0, "key": "watch", "label": "观察",
             "reason": "质量一般，估值不够便宜", "text": "观察"},
            {"v_min": None, "key": "avoid", "label": "回避",
             "reason": "质量一般且估值不便宜", "text": "回避"},
        ),
    },
    {
        # 下限就是 QUALITY_HARD_FLOOR：Q<45 在上面已经直接返回「回避」，到不了这一档
        "q_min": 45.0,
        "rules": (
            {"v_min": 80.0, "key": "buy_trial", "label": "小仓试错",
             "reason": "质量偏弱，只在明显低估时小仓", "text": "小仓试错"},
            {"v_min": 65.0, "key": "watch", "label": "观察",
             "reason": "质量偏弱，估值不够便宜", "text": "观察"},
            {"v_min": None, "key": "avoid", "label": "回避",
             "reason": "质量偏弱且估值不便宜", "text": "回避"},
        ),
    },
)
# 旧的 DECISION_RULES 在 0.9.8 删掉：它只是九个结论的清单，没有任何代码读，
# 而且里面 "expensive" 的名字（好公司，但太贵）与 _decision 实际会给出的
# 「好公司，但偏贵，等价格」已经不一致——留着只会误导。结论以 DECISION_MATRIX 为准。
#
# 矩阵之外还有四种结论，它们不由「Q×V」决定，所以不在上表：
#   数据不足，不下结论   Q 或 V 算不出来（V 缺机构覆盖/目标价，或金融股不适用）
#   观察，等待数据完整   矩阵给了买入类，但数据前置条件不满足（覆盖不足/检查缺失）
#   回避                出现致命项，或 Q < QUALITY_HARD_FLOOR
#   回避/观察            一致性闸门触发（第二节命中或提示够多）

