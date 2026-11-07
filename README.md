# stock-quality-screen

独立的企业质量初筛工具：输入股票代码，输出**一个 HTML**。

它只回答两个问题：

1. 这家企业质量怎么样？
2. 当前价格能不能买？

不做行业故事、管理层评价、上下游分析，也不替代后续深度研究。全程规则计算，不调用大模型，不生成 JSON / Markdown。

---

## 快速开始

环境：

- Python 3.10+
- Node.js 18+
- 本机 WorkBuddy 已授权「腾讯自选股」连接器（`~/.workbuddy`）

```bash
python3 stock_report.py --stock-code 600519
```

输出：

```text
html-report/贵州茅台-企业质量初筛-20261107.html
```

默认输出到本项目目录下的 `html-report/`；该目录属于本地生成物，已在 `.gitignore` 中排除。

指定目录：

```bash
python3 stock_report.py --stock-code 301101 --out-dir /tmp/初筛
```

离线重放旧采集包（仍然是 HTML 输出，不生成 JSON）：

```bash
python3 stock_report.py --stock-code 600519 \
  --bundle tests/fixtures/mini_bundle.json \
  --out-dir /tmp/sq-test
```

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

---

## 输出结构

HTML 固定五节：

1. **一、生意本身**：行业、主营、产品/业务收入占比与毛利率、五年经营轨迹、护城河规则结论。
2. **二、经营质量与风险**：10 项高信号检查，状态为 `命中 / 通过 / 数据不足`。
3. **三、企业估值与机构预期**：PE/PB/PS 历史分位、机构未来三年盈利预测、目标价、评级、DCF。
4. **四、综合评分**：质量分 Q、估值分 V、置信度、决策矩阵。
5. **五、后续跟踪**：阈值化 watchlist。

不生成：

- `.json`
- `.md`
- 中间数据文件

计算都在内存里完成。`--bundle` 只是输入，不是输出。

---

## 只取 8 类数据

| # | 数据 | 来源 | 用途 |
|---|---|---|---|
| 1 | 名称、行业、主营 | `data_profile` | 第一节 |
| 2 | 现价、市值、PE/PB | `data_quote` | 估值 |
| 3 | 5~6 年年报 + 最新报告期 | `data_finance(fields=all,num=20)` | 质量、风险、估值 |
| 4 | 机构一致预期 | `data_consensus` | 未来盈利、目标价 |
| 5 | 机构评级 | `data_rating` | 覆盖机构、评级分布 |
| 6 | 产品/业务分部 | 东方财富 `RPT_F10_FN_MAINOP` | 收入占比、分产品毛利率 |
| 7 | PE/PB/PS 历史序列 | 东方财富 `RPT_VALUEANALYSIS_DET` | 分位 |
| 8 | 资本支出 | 东方财富 `RPT_F10_FINANCE_GCASHFLOW` | FCF |

默认不取：

- 同业公司；
- 新闻、公告、研报全文；
- 25 条旧排雷；
- 管理层、行业空间等定性数据；
- 一致预期之外的卖方预测。

---

## 评分口径

### 质量分 Q（0~100）

| 维度 | 权重 | 指标 |
|---|---:|---|
| 资本回报 | 30 | 5 年 ROIC 中位数 − WACC、ROE 中位数 |
| 现金创造力 | 25 | FCF 为正年数、FCF/净利润、CFO/净利润 |
| 资产负债表 | 20 | 净有息负债/EBIT、利息保障、商誉/净资产 |
| 成长与稳定 | 15 | 营收 CAGR、毛利率标准差、ROE 标准差、股本稀释 |
| 会计质量 | 10 | 应计利润、扣非/归母 |

### 估值分 V（0~100）

| 维度 | 权重 | 指标 |
|---|---:|---|
| 历史分位 | 50 | PE/PB/PS 分位均值，越低分越高 |
| FCF 收益率 | 30 | 最近年报 FCF / 当前市值，对照 5% 要求收益率 |
| DCF 折价 | 20 | (合理价 − 现价) / 合理价 |

DCF 不适用时，按可用项重新归一，不硬编一个合理价。

### 决策矩阵

| 质量 Q | 估值 V | 结论 |
|---|---|---|
| ≥75 | ≥65 | 可买（初筛通过） |
| ≥75 | 45~65 | 好公司，等价格 |
| ≥75 | <45 | 好公司，但太贵 |
| 55~75 | 任意 | 观察，不建议现在买 |
| <55 | 任意 | 回避 |
| 有致命项 | 任意 | 回避 |
| 置信度 <60 | 任意 | 数据不足，不下结论 |

机构预期**不直接加减 Q/V**，只出现在“预期差提示”里。

---

## 目录

```text
stock-quality-screen/
  stock_report.py              CLI
  config.py                    权重、阈值、DCF 参数
  screen/
    fetch.py                   腾讯 + 东财取数，支持 --bundle
    compute.py                 报表整理、FCF、分位、机构预期、DCF
    score.py                   Q/V、风险、决策、跟踪
    render.py                  五节 HTML
    validate.py                轻量校验
    util.py                    数值与统计工具
  providers/
    westock_client.js          腾讯自选股 MCP 客户端（独立副本）
    eastmoney.py               东财估值序列 + F10 主营构成 + 资本支出
  templates/report.html        单文件 HTML 模板
  tests/
    test_smoke.py
    fixtures/mini_bundle.json
  METHODOLOGY.md
  CHANGELOG.md                  强制修改记录
  .gitignore                    不上传文件的排除规则
```

项目**不 import 旧 skill 的脚本**，旧 `stock-research-report-skill` 保持不动，继续用于深度研究。

---

## 修改记录（强制）

以后每次修改代码、配置、数据源、评分口径或文档，都必须在 [CHANGELOG.md](CHANGELOG.md) 最上方新增一条记录，写明：

- 修改时间（ISO 8601，带时区）；
- 修改了哪些文件/功能；
- 改了什么，以及必要的影响说明。

没有修改记录的提交视为不完整。

---

## 重要边界

1. **机构预期不是事实**。目标价、预测净利只作参考，不直接决定买卖。
2. **覆盖机构少于 3 家**时，预测只作提示。
3. **WACC 固定 9%**，不是逐公司精确计算；DCF 只作估值参考，不是目标价。
4. **金融股、强周期股**不适合直接套用 FCF/DCF；遇到时应人工复核。
5. **商誉字段缺失按 0 处理**，报告会标注“接口未返回，建议核对年报”。
6. 若最新报告期是季报，FCF 仍使用最近年报，避免“单季 OCF − 全年 capex”的错配。

---

## 免责声明

本项目只做规则化初筛，不构成投资建议。所有结论都应回到年报、公告和行业研究中复核。
