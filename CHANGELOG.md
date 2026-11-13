# 修改记录

> 本文件是项目的强制修改日志。以后每一次修改（代码、配置、数据源、评分口径、文档、依赖）都必须在最上方新增一条记录，写清修改时间和具体修改内容。

## 记录规则

1. 时间使用 ISO 8601，带时区，例如 `2026-11-07 09:58 +08:00`。
2. 每条记录按「新增 / 修改 / 删除 / 修复」分类，列出具体文件或功能。
3. 必须写“改了什么”，不能只写“优化”“更新”。
4. 涉及评分权重、阈值、数据源、输出结构的变化，要额外写影响。
5. 新记录放在最上面；历史记录不删除。

---

## 版本索引

只列**带版本号**的记录（0.7.10 起）。更早的 2026-11-07 ~ 11-10 12:58 之间的记录
是项目成型阶段的迭代，当时还没打版本号，按时间顺序排列在文末。

| 版本 | 日期 | 一句话 |
|---|---|---|
| 0.9.11 | 2026-11-13 14:35 | 「护城河」拆轴：盈利结构改名 + 垄断性标注（人工 YAML）+ 存续安全四档 |
| 0.9.10 | 2026-11-12 15:20 | 导航页增 5 列（原样取自输入 CSV）；彻底删除 Excel 产物 |
| 0.9.9 | 2026-11-11 14:38 | 批量模式输入 CSV 只读，且不再写任何 CSV（结果看导航页 / Excel） |
| 0.9.8 | 2026-11-11 14:04 | P3 八条结构清理（合并重复实现、删死代码、报告文字由 config 生成）+ P4 十二条文档同步 |
| 0.9.7 | 2026-11-11 13:31 | 导航页文件名改为跟随输入 CSV 主名（`index.html` → `<CSV 主名>.html`） |
| 0.9.6 | 2026-11-11 13:22 | P2 八条展示与健壮性：口径日期、样本量、市值倍数、`None%` 等 |
| 0.9.5 | 2026-11-11 12:55 | P1-1 应收基数保护与档位解耦 + P1-3 年报 <3 年整只跳过 |
| 0.9.4 | 2026-11-11 12:29 | P1-2 口径日 PE 为负不再回退到历史正值 |
| 0.9.3 | 2026-11-10 16:35 | 第三节加「估值位置」七档判断（16:45 又补了一轮边界与测试） |
| 0.9.2 | 2026-11-10 16:00 | `--csv-input` 帮助文案写明会就地改写 CSV |
| 0.9.1 | 2026-11-10 15:47 | 删掉重复判定句；`csv-input/` 改名 `xlsx-output/` |
| 0.9.0 | 2026-11-10 15:34 | Q 四处口径修正（毛利率水平门槛、3 年应计、FCF/营收、ROIC 达标年数）+ 决策矩阵一致性闸门 |
| 0.8.1 | 2026-11-10 15:20 | 毛利率环比改善从一句「未改善」改成六个数字 + 点名 |
| 0.8.0 | 2026-11-10 14:47 | 第一、二节指标改造（护城河三证据、14 项检查 4 组） |
| 0.7.11 | 2026-11-10 13:28 | 全篇估值口径统一为「口径日收盘」 |

---

## 2026-11-13 14:35 +08:00

### 背景（v0.9.10 → 0.9.11）

对 113 只自选股初筛结果交叉验证发现：`_moat()` 的「无明显护城河」与用户关心的
「垄断性 / 不会倒闭」严重错位——金钼股份（钼储量全国 25%+）、北方稀土（白云鄂博
独家开采权）、中盐化工（金属钠全球 30% 份额）这类垄断标的，因毛利率 σ 天然大，
三条财务规则结构性地判弱。根因是把「垄断性（事实层）」和「盈利结构稳定性（财务层）」
塞进了同一个标签。改造方案见《护城河与垄断性判定改造建议-20261113.md》。

### 修改

- `screen/score.py`：`_moat()` 改名 `_profit_structure()`；三档标签由
  「宽护城河/窄护城河/无明显护城河」改为「强/中/弱」。三条规则与阈值不变。
- `screen/score.py`：新增 `_solvency()` 存续安全四档（坚固/稳健/承压/危险），
  复用 `_fatal()` 四条致命项；新增 `_net_cash_ratio()` 从年度财务重算净现比
  （与风险检查 cash_flow 同源，不解析展示文案）。
- `screen/score.py`：新增 `load_resource_moat()` 读 `annotations/moat_annotations.yaml`；
  键兼容 6 位码与带交易所前缀两种写法；verified 超 12 个月标记 `stale`；
  文件缺失/解析失败一律退化为「无标注」，不抛出。
- `annotations/moat_annotations.yaml`（新增文件）：0.9.11 当日先录入 10 只人工核实
  条目（金钼股份、驰宏锌锗、西部矿业、易普力、北方稀土、中国稀土、盐湖股份、
  中盐化工、健民集团、钒钛股份）；随后由 agent 逐只搜索核实扩充至自选股池
  全部 113 只（新增 103 只：独家资源 13 / 配额牌照 10 / 技术壁垒 25 / 独家品种 3 /
  特许经营 2 / 网络 1 / 无标注 49，来源均为搜索结果真实 URL，抽查可访问）。
- `screen/render.py`：第一节「护城河规则结论」改为「生意属性」三段——
  垄断性标注（类型/依据/控股股东/来源+核实日期，无标注显示补录提示）、
  存续安全（四档+证据）、盈利结构（三条证据）；末尾固定澄清文案
  「盈利结构弱 ≠ 没有垄断」。
- `templates/report.html`：新增 `.badge.warn`（待复核徽标样式）。
- `config.py`：VERSION → 0.9.11；三处注释「护城河」改「盈利结构」。
- `METHODOLOGY.md`：8.2 节改名「盈利结构三证据」，新增「垄断性标注与存续安全」一节。
- `README.md`：三处「护城河」措辞同步。
- `tests/test_render.py`：旧断言更新 + 新增 4 条（三段结构、标注展示、过期徽标）。
- `tests/test_quality.py`：新增 ProfitStructureRenameTest / SolvencyTest /
  ResourceMoatAnnotationTest 共 13 条。

### 兼容性影响

- `data["moat"]` 键保留，指向 `data["profit_structure"]` 同一对象：历史 JSON 与
  外部脚本不破坏；历史 HTML 报告**不重渲染**（旧报告仍是「护城河规则结论」文案）。
- Q/V、14 项风险检查、结论矩阵、跟踪清单：一行未动。「危险」存续档与决策
  「回避」的映射仍由 `_fatal()` 单向决定，无双写。
- 垄断性标注**不打分、不进 Q/V、不参与结论矩阵**（垄断 ≠ 赚钱）。

### 测试

- `python3 -m unittest discover -s tests -q`：518 条全绿（原 503 + 新 15）。

---

## 2026-11-12 15:20 +08:00

### 新增（导航页新增 5 列，v0.9.9 → 0.9.10）

- `screen/index_html.py`：导航页表头由 5 列扩到 10 列，每只股票所在行新增
  `二级行业`、`毛利率改善`、`池内换手分位`、`分位星级`、`总市值（亿）`。
  列定义集中在模块级 `COLUMNS`，表头与空表 `colspan` 都由它推出来
  （原来 `colspan="5"` 是写死的，加列就会错位）。
- `screen/batch.py`：新增 5 个列名常量与 `SUMMARY_COLUMNS`，
  `ensure_result_columns()` 一并登记，重复运行时复用同名列；
  新增 `summary_cell()` 统一取值、`margin_flag()` 把毛利率压成一个字。
- `screen/index_html.py`：新增 `.num`（右对齐、等宽数字）、`.center`、`.na`（空值占位）、
  `.yes` / `.no`（毛利率）、`.stars` 样式；搜索框的 `data-search` 带上新增几列，
  可以按「白色家电」「是」过滤。

**口径（重要）**：这 5 列**只做原样透传**，值来自输入 CSV 的同名列，
批量模式不重新取数、不重算、不补空。

- 不重算的理由：上游选股表（`stock-kline-screen-tool`）已经把这 5 列算好了，
  再算一遍只会出现「导航页与 CSV 对不上」，读者不知道该信哪个。
- 唯一例外是格式：CSV 的 `毛利率改善` 是整句
  （`否：20.84→18.83（环比未改善）；营收环比 +3.0%；同比 -2.04pct（上年同季 20.87%）`），
  导航页只显示开头的 `是` / `否`，细节点进报告第二节看。开头不是「是/否」一律留空。
- 缺值一律显示 `—`：CSV 没有这一列、或该行为空时，不拿报告里另算的数顶替，
  也不补 0（实测 `选股_2026-11-10.csv` 的 `分位星级` 有 26 行为空，导航页照实留空）。

### 删除（彻底移除 Excel 产物）

- 删除 `screen/xlsx.py`（整份手写 OOXML 生成器，256 行）。
- 删除项目内的 `xlsx-output/` 目录（7 个历史 xlsx，`选股_2026-10-16` ~ `选股_2026-11-10`）。
  删除前已整体备份到 `.xlsx-output-backup-20261112-152827/`（112K，7 个文件），
  并在 `.gitignore` 加规则挡住备份目录，避免误入库。
- `stock_report.py`：删掉 `from screen.xlsx import write_report_xlsx`、`_xlsx_target()`，
  以及中断分支与正常结束处的两处调用；`--csv` 的帮助文案与模块 docstring
  不再提 `xlsx-output/`。
- `config.py`：删除 `XLSX_OUT_DIR`。批量产物只剩两处：`html-report/` 里的单股 HTML、
  同目录的导航页。
- `stock_report.py`：结束语从 `nav_paths` 循环简化为单个 `nav_path`
  （现在只会有一个产物，不必再按后缀判断是「导航页」还是「Excel」）。
- `.gitignore`：`/xlsx-output/` 规则保留（拦住旧目录意外回流），新增
  `/.xlsx-output-backup-*/` 挡住删除前的本地备份。

### 影响

- `html-report/<主名>.html` 的列数由 5 变 10：按列号解析导航页的外部脚本需要跟着改。
- 批量不再产生 `xlsx-output/` 目录，项目内已无任何 `.xlsx` 产物。
- 输入 CSV 仍然只读：新增的 5 列只在内存表里参与导航页渲染，不回写、不新建 CSV。
- 单股报告（`--stock-code`）完全不受影响：这 5 列只存在于批量导航页。

### 测试

- `tests/test_io.py`：删掉 `XlsxTest`，改为 `XlsxRemovedTest`（模块不可导入、
  `config` 无 `XLSX_OUT_DIR`、CLI 无 `_xlsx_target`）；新增
  `IndexHtmlExtraColumnsTest` 7 个用例——10 列表头、原样透传、毛利率只留是/否、
  毛利率未知显示占位、空值不补 0、CSV 缺列仍出 10 栏、空表 `colspan`。
- `tests/test_cli.py`：`test_defaults` 去掉 `XLSX_OUT_DIR` 断言；
  新增 `test_no_xlsx_output_config`（配置项与模块都必须消失）；
  帮助文案断言由「必须包含 xlsx-output」反过来改成「不得出现 xlsx-output」；
  批量用例 `test_batch_writes_report_nav_and_xlsx` 改名 `..._report_and_nav_only`，
  并断言输出目录里只有两个 `.html`、任何位置都没有 `.xlsx`。
- `tests/test_smoke.py`：删掉 `zipfile` 与 `write_report_xlsx` 导入、`setUp` 里的
  `XLSX_OUT_DIR` patch；`test_xlsx_and_index_contain_clickable_report_links`
  收窄为只测导航页，并断言不产生 Excel。

---

## 2026-11-11 14:38 +08:00

### 修改（批量模式输入 CSV 只读且不写任何 CSV，v0.9.8 → 0.9.9）

`--csv` 以前会把三列结果就地补进传入的 CSV。这条设计在评审 §6 就点过：
对「别的工具刚产出的选股表」「只读的原始表」都是高风险动作。现在改成
**输入只读、批量不写任何 CSV**：评分和链接只体现在导航页与结果 Excel 里。
评分口径与报告内容一个字没动。

> 本条 14:23 首次落地时是「结果另存 `csv-output/<主名>.csv`」；14:38 按你的要求
> 取消这个文件与目录，连带删掉为它新加的写入路径（见「删除」）。项目里不产生任何 CSV。

**新增**

- `screen/batch.py:CsvTable` 变成纯内存结构（`path` / `fieldnames` / `rows` / `code_column`），
  只承载「读出来的输入表」，不再持有编码、换行符、权限位这些回写才需要的东西。
- 测试 +6：`test_cli.BatchRunTest` 4 条（输入字节与 mtime 不变、`0444` 输入照跑、
  重复代码只取一次数、续跑不重取数）、`test_io.CsvReadTest.test_crlf_and_bom_are_read_transparently`、
  `test_smoke.CsvBatchTest.test_batch_cli_writes_report_and_nav_but_no_csv`。

**修改**

- `stock_report._run_batch()`：删掉写 CSV 的整条链路（`_save_csv`、每完成一只就落盘的
  `write_ok`、批前的空表预写、Ctrl-C 时的补写）；增量续跑改回只看
  `--out-dir` 里 `*-{代码}-企业质量初筛-*.html`，不再读任何 CSV。
- `stock_report`：`_existing_report()` / `_link_path()` 删除（它们的作用是「从 CSV 的链接列
  找回报告」，CSV 不再有链接列，只剩 `_find_existing_report()` 一条路）。
- 终端摘要去掉「结果 CSV」与「新增列」两行，只留输入 CSV（只读，未改动）、报告目录、
  导航页、Excel。
- `--csv` 帮助文案、`stock_report` 模块说明、`screen/batch.py` 模块说明同步改写。
- `README.md`：批量章节（产物只剩导航页 + Excel）、参数表、退出码 130、目录树、
  「重要边界」第 19 条。
- `METHODOLOGY.md` 版本行 → 0.9.9。

**删除**

- `config.CSV_OUT_DIR`、`screen/batch.py:result_csv_path()` / `read_prior_results()` /
  `write_csv_table()` / `RESULT_CSV_SUFFIX`、`CsvTable.out_path` / `.encoding` /
  `.lineterminator` / `.mode`。
- 对应测试：`tests/test_io.CsvWriteTest`（3 条）、`ResultCsvTest`（5 条）、
  `PriorResultsTest`（5 条）、`test_lineterminator_detected`、
  `test_smoke.CsvBatchTest.test_roundtrip_preserves_columns_bom_and_crlf`、
  `test_cli.BatchRunTest.test_result_path_never_overwrites_input_in_csv_output_dir`。
- `.gitignore` 里的 `/csv-output/`。
- `CODE-REVIEW-2026-11-11.md`：评审记录不进项目仓库（已移到工作区的
  `review-out/`，README 目录树里对应的一行一并去掉）。

**影响**

- **评分、V 分、结论、报告 HTML 全部不变**：只改文件的读写位置。
- 批量产物：`html-report/` 下的报告 + `<输入 CSV 主名>.html` 导航页 +
  `xlsx-output/<主名>.xlsx`。不再有结果 CSV，输入表也不会被加列。
- 因此可以安全地把 `--csv` 指向只读表、共享盘上的表、别的工具产出的表。
- 增量续跑行为不变（已有可解析报告的股票照旧跳过），只是判断依据只剩报告文件名里的代码。
- 代价：想拿「代码 → 结论」的表格数据时，看 `xlsx-output/` 里的 Excel（三列齐全、链接可点）。

---

## 2026-11-11 14:04 +08:00

### 修改（P3 八条结构清理 + P4 十二条文档同步，v0.9.7 → 0.9.8）

这一轮不动 Q/V/决策口径，只做「同一件事只写一遍」和「文档跟上代码」。
**结论层面唯一的可见变化是报告里的说明文字措辞**（见「影响」）。

**P3-1 魔法数字收进 config**

- `config.py`：新增 `QUALITY_ITEM_RANGES`（13 组「下界/上界/方向」）、`QUALITY_GRADES`
  （六档分界）、`SCORE_BAR_GOOD/BAD`（分数条配色）、`CL_RATIO_STRONG`（预收型强势线 2%）、
  `INTEREST_COVER_FATAL`（1.0）、`FATAL_NET_DEBT_EBIT`（4.0）。
- `screen/score.py`：新增 `_band()`，16 个子项的打分区间全部改读 config；
  质量分档改用 `grade_of()` + `QUALITY_GRADES`；致命项的 `<1`、`>4` 换常量。
- `screen/render.py`：`_score_class()` 读 `SCORE_BAR_*`，`_bargain_verdict()` 读
  `CL_RATIO_STRONG`，不再各写一遍 65/45/2.0。

**P3-2 格式化三套并存 → 一份**

- 新增 `screen/fmt.py`：`num` / `num_sep` / `pct` / `signed_pct` / `yi` / `yi_suffix`，
  统一 None → `—`、非数字原样转义。
- `score._p/_n/_yi/_delta_pct`、`render.n/pct/yi` 三套实现删除，改为从 fmt 导入别名
  （46 + 53 处调用点不动，输出逐字节一致）。
- 删除零调用的 `util.pct / yi / ratio / text`。

**P3-3 号段规则三处 → 一份**

- 新增 `screen/codes.py`：`split` / `market_of` / `normalize` / `six` / `secucode` / `eastmoney_url`。
- `fetch.normalize_code`、`batch.eastmoney_url`、`eastmoney.to_secucode` 改为转调。
- 顺带修掉一个潜在 bug：`to_secucode("600519.SH")` 以前 `replace('.','')` 后变成 8 位会抛错，
  现在正常返回 `600519.SH`。

**P3-4 报告里的权重/阈值文案由 config 生成**

- `render._matrix_text()`：决策矩阵说明由 `config.DECISION_MATRIX` 生成，V 区间由相邻
  门槛相减得来。
- `render._grade_text()`：分档说明由 `QUALITY_GRADES` 生成。
- `render._weight_text()` / `_v_formula_text()`：页脚方法说明与第四节 V 公式由
  `QUALITY_WEIGHTS` / `VALUATION_WEIGHTS` / `VALUATION_WEIGHT_TEXT` 生成。
- `render._fatal_rule_text()`：第二节末段四条致命项的数字由 config 生成。
- `score._decision()` 重写为遍历 `config.DECISION_MATRIX`；旧 `DECISION_RULES`、
  `BUY_MIN_V` 删除（前者零调用且文案已与代码不符，后者与矩阵是同一批数字）。

**P3-5 综合评分改成稳定标记**

- `render` 给三个数加 `data-metric="q|v|conclusion"`；
  `screen/summary.py` 优先认标记，认不到才回退按小标题文字找——
  回退这条路是给 0.9.7 及更早的报告留的（批量会复用老报告，不能一改就全「评分提取失败」）。

**P3-6 / P3-7 / P3-8**

- `screen/__init__.py`：`__version__` 改为 `from config import VERSION`（原来写死 0.1.0）。
- `render._template_text()` 加 `lru_cache`，批量 155 只股票不再读盘 155 次。
- `providers/eastmoney.py`：加跨线程节流（默认 400ms，`EASTMONEY_GLOBAL_INTERVAL_MS` 可调），
  每次 HTTP 请求前等间隔，翻页请求也计入。

**P4 文档十二条**

1. `README.md` 目录树：根目录名改为 `stock-quality-screen-tool/`，补 `index_html.py`、
   `xlsx.py`、`codes.py`、`fmt.py` 与新增测试文件。
2. `README.md` 新增「CLI 参数与退出码」：11 个参数一张表（含默认值、适用范围，
   标明 `--force` 仅批量、`--bundle/--name` 仅单股票），退出码 0/1/2/3/130 一张表。
3. `README.md` 代码列候选从 4 个补到实际的 10 个。
4. `README.md` / 短重试说明由「3 秒」改为「3~8 秒（3 秒 + 0~5 秒随机抖动）」，
   并补东财节流的说明。
5. `METHODOLOGY.md` §6 覆盖机构口径改正：代码是 `max(预测行 institutionCnt)`，
   全为 0 才回退 `forecastInstitutions`，原文写反了。
6. （已在 0.9.5 修完，本轮无需再改）
7. `METHODOLOGY.md` 闸门表「数据不足 ≥2 项 → 不入闸门」改为
   「`unknown` 不计入命中/提示，闸门只看这两项计数」。
8. `config.py` 商誉三档改名：`GOODWILL_EQUITY_MAX(0.20)` → `WATCH`、
   `GOODWILL_EQUITY_WARN(0.30)` → `HIT`，`FATAL(0.50)` 不变。
9. 旧注释「商誉 30% 高危机（20% 用 GOODWILL_EQUITY_MAX）」随改名删除。
10. `README.md` 环境一节写明「无第三方 Python 依赖，只用标准库，无需 pip」。
11. `CHANGELOG.md` 顶部加「版本索引」表（本表），后续新记录同步维护。
12. `.gitignore` 去掉全局 `*.html` + `!templates/report.html`，改为按产物目录排除
    （`/html-report/`、`/xlsx-output/`），避免 `tests/fixtures/*.html` 被静默忽略。
13. `examples/` 取舍：保留目录但只入库 `examples/README.md`，说明里面的报告是
    2026-11-07 旧版式样例、想看当前版式用夹具现场跑；`README.md` 重要边界补第 18 条。

**测试**

- 新增 `tests/test_codes.py`（7）、`tests/test_fmt.py`（9）、`tests/test_config_contract.py`（14）、
  `tests/test_eastmoney.py`（6）；`test_io.py` 增 4 条摘要标记位用例；
  `test_render.py` 增模板缓存与版本号用例。
- 删除 `test_fetch.CallMapTest`（`call_map` 已删）、`test_util.FormatTest`（改为 `test_fmt`）、
  `test_compute` 的 `negative_ranges` 相关断言（字段已删）。
- 全量 **497 条通过**（0.9.7 为 458 条）。

**影响**

- **算出来的数一个没变**：同一份 `mini_bundle` 夹具，Q 90.9 / V 62.7 / 「好公司，等价格」
  与 0.9.7 完全一致；真实样本 600519、300058 的 Q/V 也未变。
- **报告文字有四处措辞变化**（都是变得更自洽，不是改口径）：
  V 公式由「目标价空间 40% + 预测 PE 20% + 未来净利增速 40%」改为
  「机构目标价空间 40% + 预测 PE 相对当前 PE 20% + 预期未来净利增速 40%」（与构成表同名）；
  决策矩阵里「V≥80 推荐」改为「V≥80 推荐买入」；页脚「未来净利增速」改为「预期未来净利增速」；
  致命项说明合成一行（HTML 折行，视觉效果不变）。
- **批量变慢**：东财每个请求间隔 0.4 秒，一只股票 3~4 个请求约多 1.2~1.6 秒。
  这是拿时间换「不整段丢估值序列」，可用 `EASTMONEY_GLOBAL_INTERVAL_MS=0` 关掉。
- **删除的公开名字**：`config.DECISION_RULES`、`config.BUY_MIN_V`、`config.GOODWILL_EQUITY_MAX/WARN`、
  `fetch.call_map`、`util.pct/yi/ratio/text`、`compute` 返回的 `chart["negative_ranges"]`。
  仓库内已无引用；外部若有人 import 会报 `ImportError`，属于本次有意的清理。

---

## 2026-11-11 13:31 +08:00

### 修改（导航页文件名改为跟随输入 CSV 主名，v0.9.6 → 0.9.7）

批量模式生成的浏览器导航页以前固定叫 `index.html`，一个目录里跑过多份 CSV 时
互相覆盖，也看不出这份导航页对应哪份输入。现在改成跟输入 CSV 主名一致，
和结果 Excel（`xlsx-output/<主名>.xlsx`）使用同一套命名。

- `screen/index_html.py::write_index_html()`：目标文件从 `out / "index.html"`
  改为 `out / f"{Path(table.path).stem}.html"`，例如 `live-batch2/rows.csv`
  → `live-batch2/reports/rows.html`。函数签名和返回值不变，
  `stock_report._run_batch()` 记录的 `nav_paths` 和终端「导航页」一行自动跟着变。
- `tests/test_cli.py`：两处断言 `index.html` → `rows.html`（测试用 CSV 固定叫 `rows.csv`）。
- `tests/test_io.py`：新增 `IndexHtmlTest.test_nav_filename_follows_csv_stem`，
  用 `季度清单.csv` 验证输出 `季度清单.html`、落在 `--out-dir` 下、且不再生成 `index.html`。
- `README.md`：导航页产物从 `html-report/index.html` 改为 `html-report/<输入 CSV 主名>.html`。
- `config.py`：`VERSION` 0.9.6 → 0.9.7；`METHODOLOGY.md` 版本行同步。

**影响**：只改文件名，导航页内容、按钮、徽标、搜索逻辑不变；HTML 报告、
CSV 回写、XLSX 输出均不受影响。**注意**：老目录里遗留的 `index.html` 不会自动删除，
重新跑一次批量会在同目录新增 `<主名>.html`，旧文件可手工删掉。

## 2026-11-11 13:22 +08:00

### 修复（P2 八条展示与健壮性问题，v0.9.5 → 0.9.6）

八条都不改变 Q/V/决策，只修「读起来不对」和「调用方假设过强」的地方。逐条：

**P2-1 无估值序列时价格口径变成 `" 收盘"`**

- `screen/compute.py::_close_price()`：把口径说明拼装抽成内部函数 `_basis()`，
  `as_of` 为空时返回「上一交易日收盘」，不再拼出空前缀。
- `screen/render.py`：报告头 `估值口径 — 收盘` → `无估值序列（无口径日）`；
  第三节引言整段改短版（原「全篇估值口径统一为 — 收盘：下表…」在没有序列时是空话），
  并区分「接口没返回数据」与「取数失败（见上方取数缺口）」。

**P2-2 占款比趋势恒写「三年」，实际窗口是 5 年**

- `compute._structure()` 增 `bargain_trend_years`（= 首尾有数据年份的实际跨度）；
- `render._structure_line()` 文案改为「近 5 年 +0.001」。实测 600519/000725 都从「三年」变「近 5 年」。

**P2-3 只有 2 年历史也会报「连续 3 年经营现金流为负」致命项**

- `score._fatal()`：`_years(data)[-3:]` 在只有 2 年时切片非空，会把 2 年说成 3 年。
  改为先要求 `len(ocf_3y) >= 3` 且三年都有值且都为负；缺失年份会打断链条。
- 影响：2 年报的公司不再被这条打成「回避」。P1-3 落地后 2 年报本来就被跳过，这层是防回归。

**P2-4 CLI 把「Q 算不出来」显示成「不适用」**

- `stock_report._score_line()`：Q 与 V 用同一套写法——`not_applicable` 才是「不适用」，
  否则打「—」。

**P2-5 分位样本太少仍输出七档结论**

- 新增 `config.VAL_MIN_SAMPLE_WEEKS = 52`；
- `render._valuation_verdict()/_valuation_position()` 增 `sample` 参数：样本不足 1 年时
  只报分位、不贴档名，另写一句「分位样本仅 N 周，历史太短，分位仅供参考，不给档位结论」；
- 正常情况在结论句后补「（样本 454 周）」，读者能判断分位可靠性。

**P2-6 安全边际 −488% 读不懂**

- `compute._cash_valuation()` 每个 anchor 增 `cap_times = 总市值 ÷ 底线价值`；
- `render` 底线表同格补「（市值 5.9 倍）」（仅倍数 > 1 时显示），并加一句脚注说明
  分母是底线、所以会小于 −100%。口径不变，只是多一个能读懂的量纲。

**P2-7 `compute_scores()` 假设 data 一定有 `valuation` 键**

- `score.py` 两处 `data["valuation"]`、一处 `data["meta"]` 改成 `.get(...) or {}`。
  用 `support.with_annual()` 直接调用不再 `KeyError`，跟踪表 PE 分位打「—」。

**P2-8 `--quiet` 仍会打重试警告；`--workers` 对腾讯侧无加速**

- `screen/fetch.py`：新增模块级 `QUIET` 与 `set_quiet()`，重试警告按开关决定是否打印
  （失败仍记录到数据缺口）；
- `stock_report.main()` 解析完参数就 `set_quiet(args.quiet)`；
- `README`：说明 `--workers` 主要并行东财取数与渲染，腾讯侧受跨线程全局节流，
  不是线性加速，盲目调大更容易撞限频。

**测试**：441 → **457** 全绿。新增：`ClosingBasisTest`（空口径日）、`StructureTrendTest`（3）、
`CashValuationUnitTest`（倍数 2）、`FatalTest`（2 年报 / 缺年份）、`ScoreLineTest`（Q 打 —）、
`SectionValuationTest`（2：无序列不印空日期、倍数与脚注）、`ComputeScoresRobustnessTest`（2）、
`ClientRetryTest`（静音 2）、`ValuationVerdictTest`（2：短样本不给档位）、`SingleRunTest`（quiet 透传）。

**文档**：`METHODOLOGY.md` §5（口径日无序列、分位样本门槛、安全边际倍数）、
`README.md`（估值位置样本门槛、底线倍数、`--workers` / `--quiet` 说明）。

**真实样本回归**：600519 Q 90.9 / V 62.7 / 好公司等价格、000725 Q 40.7 / V 100.0 / 回避
——与 0.9.5 完全一致；报告里能看到「近 5 年 +0.001」「（样本 454 周）」「−488.1%（市值 5.9 倍）」。

---

## 2026-11-11 12:55 +08:00

### 修复 / 新增（P1-1 应收小基数保护解耦 + P1-3 上市不足 3 年整只跳过，v0.9.4 → 0.9.5）

#### 一、P1-1：连续两年 >15pct 不再绕过小基数保护

**背景**：档位判定写在基数判定外面——

```python
if latest_gap > config.AR_REV_GAP_ALERT:
    if both:                       # 连续两年 > 15pct → 直接命中
        status = "hit"
    else:
        if ar_ratio < config.AR_MATERIAL_RATIO:
            detail = "应收不足营收 2%，仅提示；" + detail
        status = "watch"
```

应收占营收 1.6%、两年增速差 +20.0pct / +33.3pct 时判 `hit`，与
`METHODOLOGY.md`「0.5%~2% 只提示」和 README「小基数保护」都相反。
而 `hit` 会进一致性闸门：命中 1 项 → 买入类降「观察」，命中 ≥2 项 → 降「回避」。
等于让一个只有几千万的科目改变了最终结论。

**修改**（`screen/score.py`）：先判基数再判档位。

```python
material = ar_ratio >= config.AR_MATERIAL_RATIO
if latest_gap is not None and latest_gap > config.AR_REV_GAP_ALERT:
    if both and material:
        status = "hit"
        detail = "连续两年 > 15pct；" + detail
    else:
        if not material:
            detail = ("连续两年 > 15pct，但应收不足营收 2%，仅提示；"
                      if both else "应收不足营收 2%，仅提示；") + detail
        status = "watch"
```

基数不足时**保留「连续两年 > 15pct」这个事实**（读者需要知道），只是不升级为命中。

**影响**：只影响「应收/营收 0.5%~2% 且连续两年增速差 >15pct」这一类公司，把它们从
`hit` 降为 `watch`；Q 分不读风险检查的状态，所以 **Q 不变**，变的只有一致性闸门是否触发。
四只样本（600519 / 000725 / 300058 / 600733）重跑 Q/V/结论**完全一致**。

#### 二、P1-3：年报 <3 个不处理（硬门槛，跳过而非失败）

**背景**：旧逻辑两端都不对——`_quality()` 门槛是 2 年，`validate()` 只在 Q 为 `None` 时抛一句
泛化的「质量分无法计算」：

- 只留 1 个年报 → `ScreenError: 质量分无法计算`，退出码 2，批量记「生成失败」（原因被吞掉）；
- 只留 2 个年报 → **照常出报告、照常打 Q 分**。2 个点的 σ、2 年 CAGR 用来定性，
  比失败更隐蔽。

**修改**：

- `config.py`：新增 `MIN_ANNUAL_YEARS = 3`。
- `screen/score.py:_quality()`：门槛 `len(ys) < 2` → `< config.MIN_ANNUAL_YEARS`。
- `screen/validate.py`：新增 `SkipStock(ScreenError)`；年报数判定放到最前面
  （早于 Q 判定，否则会被「质量分无法计算」抢先）；0 个年报仍属 `ScreenError`。
- `screen/batch.py`：`ReportResult.skipped`（不满足条件，不算失败）；新增
  `SKIP_SCORE_TEXT = "跳过：上市不足 3 年"`（由 `config.MIN_ANNUAL_YEARS` 拼出）。
- `stock_report.py`：
  - 单股票模式捕 `SkipStock` → 打印「跳过 600519：上市不足 3 年（仅 2 个年报），本工具不处理」，
    退出码 **0**（不是参数错误，不该用 2 冒充）；
  - 批量模式 `SkipStock` 单独成支 → CSV 写「跳过：上市不足 3 年」、报告链接留空、不写 HTML；
  - 统计把 `skipped` 与 `failed` 分开，多打一行「跳过 N 行」；只有真失败才让退出码为 1。
- `screen/index_html.py:_badge_class()`：「跳过」归灰色 `unknown` 徽标
  （此前会 fall through 到 `watch`，显示成观察类）。
- 文档：`METHODOLOGY.md` §1（年报门槛）、§4 小基数保护、§8 已知限制第 12 条、
  `README.md` 批量章节（四种非结论值对照表）、重要边界第 17 条、
  `config.DECISION_RULES` 的 `unknown` 注释收窄含义。

**影响**：

- 正常公司（年报 ≥3 个）**完全不变**：四只样本 Q/V/结论逐项一致。
- 年报 1~2 个：从「失败」或「照出报告」变成**跳过**，CSV 里能一眼看出原因。
- 金融股同样走这个门槛，不做例外。
- 实测发现：腾讯接口连**上市前的年报**一起返回，试了 301498 / 688581 / 920002 等新股的
  `annual` 都是 5 年，所以这个门槛在真实数据上**很少触发**；它防的是接口给不出 3 年
  （极新股、停牌断档、数据源异常）的场景。用真实数据截断成 2 个年报（600519 的
  2024/2025 两期）走 `--bundle` 验证：打印跳过、退出码 0、不生成任何 HTML。
- 3 年只是最低线：Q 里「5 年 ROIC 中位数」「5 年中 4 年高于 WACC」按可用年数算，
  不另加 `MOAT_MIN_YEARS`。

**测试**：424 → **440** 全绿。新增/调整：
`test_risk_decision.ArGapTest`（+2：两年超 15pct 但基数不足 → watch；2.0% 边界仍 hit）、
`test_quality`（`QualityMissingDataTest` +2、`AnnualYearsGateTest` +4）、
`test_cli`（+3：单股票跳过退出码 0、批量写跳过值且不产 HTML、跳过与失败分开计数）、
`test_io.IndexHtmlTest`（+1：跳过徽标为 unknown）；
`test_partial_group_still_produces_total` 的样本从 2 年改为 3 年（同值，结论不变）。

---

## 2026-11-11 12:29 +08:00

### 修复（P1-2：口径日 PE 为负时不再回退到历史正值，v0.9.3 → 0.9.4）

**背景**：`_valuation()` 取“当前值”时用的是 `current = 口径日那一行`，但一旦该值 ≤0，
旧代码 `cur = values[-1]` 会**退到序列里最后一个正值**，并且这个值同时用来：算分位、
填分位表“最新收盘”、经 `meta.pe` 进 V 的「预测 PE 相对当前 PE」。于是亏损股会拿到
一个**不属于口径日**的 PE。实测两个真实样本：

| 代码 | 口径日 | 口径日 PE(TTM) | 旧口径退回去的值 | 旧分位 |
|---|---|---|---:|---:|
| 600733 北汽蓝谷 | 2026-11-10 | −6.80 | 206.18（**2020-04-29**） | 29.1% |
| 002005 德豪润达 | 2026-11-10 | −54.89 | 98.45（2026-10-23） | 77.1% |

北汽蓝谷那一行尤其糟：报告写着“最新收盘 206.18 倍、历史分位 29.1%（不贵）”，
而这个数来自六年前，与图上最后一个点（PE 为负、断线）根本不是同一天。

**修改**：

- `screen/compute.py` `_valuation()`
  - 删掉 `cur = values[-1]` 回退分支。口径日该指标为负/缺失 → 本次判为「不可用」：
    `current=None`、`percentile=None`，`min/max/points` 照旧给（历史区间仍可见）；
  - docstring 补口径说明。
- `screen/score.py`
  - `_tracking()`：PE 分位行改成显式判 `None`。此前 `pe.get('percentile', '—')` 在
    `percentile` 存在但为 `None` 时会打成 **`None%`**（P1-2 实测踩出来的）；
  - `_valuation_score()`：当前 PE 为 `None` 且 `chart.pe_negative_latest` 为真时，
    原始值文案写「**口径日 PE 为负，不参与**」，不再笼统写“缺少当前 PE”——数据是有的，
    只是这个口径不能用。
- `screen/render.py`：分位表下方加一行脚注，说明 `—` 的含义（负/缺失，不计分位、
  不进 V、不退回历史正值），避免读者把 `—` 读成“数据没取到”。
- `config.py`：`VERSION` → `0.9.4`；`METHODOLOGY.md` 版本行同步。
- 文档：`METHODOLOGY.md` §5（分位节新增“不可用”一条；预测 PE 一节写明当前 PE 取口径日、
  为负则不参与；口径日收盘价一节写明负 PE 不做 PE×EPS 反推）、`README.md`
  （第三节说明加一段、已知限制新增第 16 条）。

**影响（已用真实样本对照重跑）**：

- 口径日 PE > 0 的股票**完全不变**：600519 V 62.7→62.7（PE 21.89 / 18.0%）、
  000725 100.0→100.0、300058 61.4→61.4，分位表逐字相同。
- 口径日 PE ≤ 0 的股票：分位表该行由「206.18 / 29.1%」变成「— / —」；
  V 的「预测 PE 相对当前 PE」该项退出，权重按剩余项归一。
  600733、002005 这两只的 V 本来就是“数据不足”（最近年报亏损 → 增速项缺失），
  所以 V 仍为空，**结论未变**；影响集中在“不再展示一个假的当前 PE”。
- 夹具里构造的“口径日 PE 为负但年报盈利”样本（V 可算）则从 62.7 → **64.7**：
  因为少了一个 0 分的 PE 项，只剩目标价空间与增速两项按 80 权重归一。
  方向上：PE 项原本得分越低，新口径 V 抬得越多；原本满分则略降（该项 100 时 Δ = −7.1）。
- 副作用一处：口径日 PE 为负时不能再 `PE×EPS` 反推收盘价，落到 `prev_close`
  或实时价（`_close_price` 已有该分支，无需改动）。

**测试**：`tests/test_compute.py` 新增 `NegativeLatestMetricTest`（4 例）：
负值标为不可用、其他指标不受影响、口径日缺失同样判不可用、
负 PE 时收盘价不再用陈旧 PE 反推。424 → **428 全绿**。

---

## 2026-11-10 16:45 +08:00

### 修复 / 新增（估值位置那句话的边界加固与测试补全，v0.9.3 内追加）

**背景**：0.9.3 落地后复查 `_val_band()` / `_val_items()`，发现两处越界会被读成错误结论：

1. `_val_band(-5)` 落到兜底分支 → 返回**「历史顶部」**，方向正好相反；
2. `percentile` 为 NaN / 120 时同样进兜底，且位置句里会印出 `120%` 这种不存在的分位。

**修改**：

- `screen/render.py`
  - `_val_band()`：先把入参夹到 `[0, 100]` 再查档，越界值归最近一端（-1 → 历史底部，
    101 → 历史顶部），不再两头都掉进顶部；
  - `_val_items()`：`percentile` 不在 `[0, 100]`（含 NaN）时按**缺失**跳过，不夹取——
    夹取会把 -5% 读成「历史底部」，比少说一个指标更误导。
- 说明文档同步：`METHODOLOGY.md` §5 增补「越界/NaN 按缺失处理」与档位兜底行为；
  `README.md` 同节增补一条；两处原先「规则只有三条」改为「规则三条 + 几条说明」，
  以免读者以为后面的档位理由也是规则。

**测试补全**（`tests/test_render.py` `ValuationVerdictTest`、`tests/test_smoke.py`）：

- 七档必须**首尾相接**：首档下界 = 0、末档上界 ≥ 100、相邻档 `prev.high == cur.low`，
  防以后加档/改切点时留缝或重叠；
- `_val_band(-5)` / `_val_band(120)` 归最近一端；
- `percentile` 越界（120 / -5）按缺失跳过，位置句不输出该指标；
- **0~100 步长 10 的三指标全组合（11³ = 1331 例）**都必须产出结论，且结论词只能是七档之一
  ——防出现「空结论」或拼错档名；
- 结论函数**不得改写传入的 metrics**（避免渲染阶段污染数据）；
- 端到端：`render_html()` 的产物必须含「估值位置」「中位落在」。

**回归验证**：同一批离线包重出 4 份报告，与 0.9.2 版的差异除新增那一段外**只有版本号一行**，
确认 Q 分、V 分、决策与之前的数字完全一致。

**测试**：419 → **424** 全绿。

---

## 2026-11-10 16:35 +08:00

### 新增（第三节加一句「估值位置」判断，v0.9.2 → 0.9.3）

**背景**：第三节分位表只给「最新收盘 / 历史分位 / 区间 / 样本点数」四列数字，
读者仍要自己判断「18% 算便宜吗」。走势图也只看得出形状，看不出结论。
补充方式经过四轮收敛，最终只加**一段话**，不加表、不加块、不加合理价：

```text
估值位置：PE 18%（下三分之一）、PB 6%（历史底部）、PS 17%（下三分之一）
　——　三个口径位置接近（跨度 12pp），中位落在下三分之一：估值偏便宜。
```

- `config.py`：新增 `VAL_BANDS`（七档，切点 10/30/45/55/70/90）、
  `VAL_SPREAD_TOL = 25.0`、`VAL_SPREAD_STRONG = 45.0`；`VERSION` → `0.9.3`。
- `screen/render.py`：新增 `_val_band()`、`_val_items()`、`_valuation_position()`、
  `_valuation_verdict()`；`_section_valuation()` 在 `{valuation_charts}` 后插入该段。
- 第三节引言文案改为「历史分位、走势图与下方那句位置判断都只展示，不进入 V 分」。

**口径**（写进 `METHODOLOGY.md` §5）：

1. 每个指标报档位；定档取三个分位的**中位数**，不用平均（平均会被极端值拽走）；
2. 跨度 ≤ 25pp 只给结论；> 25pp 点名两端，并按 PE→利润端、PB→净资产端、PS→收入端
   说明「哪一端更便宜」，不枚举组合；
3. 百分比复用分位表同一个 `percentile` 字段，不重算；不足两个指标整段不显示。

**影响**：不改 V 分、不改决策矩阵、不影响排序。四只样本输出：
600519 偏便宜（跨度 12pp）、000725 略偏便宜（24pp）、300058 偏贵（16pp）、
600036 略偏便宜但两端背离（30pp）。

**测试**：`tests/test_render.py` 新增 `ValuationVerdictTest` 14 条（七档边界 14 个取值、
中位数 vs 平均值、跨度 24/30/78、两指标、单指标、缺分位、段落位置、同源百分比、空态）。
全量 405 → **419** 全绿。

---

## 2026-11-10 16:00 +08:00

### 修改（`--csv-input` 的帮助文案名不副实，v0.9.1 → 0.9.2）

**背景**：`--help` 里原来写的是

```text
--csv-input CSV_INPUT   批量模式：CSV 路径，读取其中的股票代码，生成报告并回写 CSV
```

三处对不上：

1. **名字说“输入”，行为是“读写”**：这个参数会**就地改写**传入的 CSV（末尾补三列），
   上一版刚把产物从输入目录挪走（`csv-input/` → `xlsx-output/`），“输入文件被改写”就更该显式警告；
2. 回写**哪几列**没写，`HTML报告链接` 这类带超链接的列读者无从得知；
3. 结果 Excel 去哪没写（现在固定 `xlsx-output/`），容易被理解成“还在输入目录里”。

#### 修改

- `stock_report.py`：主参数名改为 `--csv`，`--csv-input` 保留为**同义旧名**（同一个
  action、同一个 `dest="csv_input"`，脚本不用改），帮助文本重写为：
  “读取 代码/股票代码/证券代码/code 列 → 逐只生成报告 → **就地改写**该 CSV、末尾补三列
  （综合评分 / HTML报告链接 / 东方财富网股票详情）→ 结果 Excel 另存到 `xlsx-output/`”。
- 两条批量模式错误提示同步改成“批量模式（--csv）…”，不再只提旧名。
- 模块 docstring 的用法示例改用 `--csv`，并补一句“原 CSV 就地补三列，其余列与行序不动”。
- `README.md`：批量示例改用 `--csv`（注明旧名）；“新增两列”更正为**三列**（原文列了三条，
  数字写错）；补一段醒目提示“这个参数会改写传入的 CSV，别直接指向只读的原始选股表”。

#### 测试

- `tests/test_cli.py` 新增 3 个用例：`--csv` 与 `--csv-input` 落到同一个 `dest`；
  两者都与 `--stock-code` 互斥；`format_help()` 必须含“就地改写 / HTML报告链接 / xlsx-output / --csv-input”
  （断言前去掉空白，因为 argparse 会按终端宽度把 `xlsx-output` 拆成两行）。
- `python3 -m unittest discover -s tests`：**405 个用例通过**（0.9.1 为 402）。

---

## 2026-11-10 15:47 +08:00

### 修改（删掉重复的判定句 + `csv-input/` 改名 `xlsx-output/`，v0.9.0 → 0.9.1）

**背景**：报告第一节里 `① 毛利率环比改善判定：未改善（C3 不成立）` 这句与标题右侧的
badge（`［毛利率环比走弱］`）说的是同一件事，正文再念一遍纯属冗余；另外项目里的
`csv-input/` 实际只装批量结果 Excel，名字和内容对不上。

#### 删除

- `screen/render.py`：`_margin_chart()` 不再输出 `<p>① 毛利率环比改善判定：<b>…</b></p>`，
  以及配套的 `head = cmp.get("label") or improve.get("detail")`。
  判定结论只保留在 badge 上，图表下方直接是「同比对照 → 环比对照 → 点名结论」三段。
  `compare["label"]` 仍保留（第二节表格的 detail 在用），只是不再进正文。

#### 修改

- `config.py`：新增 `XLSX_OUT_DIR = PROJECT_DIR / "xlsx-output"`；版本号 → 0.9.1。
- `stock_report.py`：新增 `_xlsx_target(table)`，批量结果 Excel 固定写
  `xlsx-output/<输入 CSV 主名>.xlsx`（两处调用点：正常结束、`Ctrl-C` 中断时）。
  以前是 `table.path.with_suffix(".xlsx")`，产物落在输入 CSV 旁边，输入目录被污染。
- 目录：`csv-input/` → **`xlsx-output/`**（5 个历史 `.xlsx` 原样迁移）。
- `.gitignore`：`/csv-input/` → `/xlsx-output/`，注释改成“HTML 报告 / 结果 Excel”。
- `README.md`：批量模式产物说明改为 `xlsx-output/选股_2026-11-06.xlsx`，并写明
  固定落在 `config.XLSX_OUT_DIR`、不写在输入 CSV 旁边。
- `METHODOLOGY.md`：① 呈现改为三层，注明正文不再重复判定句；版本行 → 0.9.1。

#### 测试

- `tests/test_render.py`：新增 `test_margin_chart_does_not_repeat_verdict_headline`
  （断言无“毛利率环比改善判定”、无“①”，badge 与三段文字仍在）、
  `test_margin_chart_without_compare_has_no_judge_block`。
- `tests/test_cli.py`：`BatchRunTest.setUp` 把 `config.XLSX_OUT_DIR` 指向临时目录，
  避免测试写进项目的 `xlsx-output/`；新增 `test_xlsx_target_keeps_csv_stem_under_xlsx_output`；
  `test_report_links_point_to_existing_files` 改为断言 Excel 落在 `xlsx-output/` 且
  **不再**出现在输入 CSV 旁边；`test_defaults` 增加默认目录断言。
- `tests/test_smoke.py`：`CsvBatchTest.setUp` 同样隔离 `XLSX_OUT_DIR`。
- `python3 -m unittest discover -s tests`：**402 个用例通过**（0.9.0 为 399），
  跑完 `xlsx-output/` 里仍是原来那 5 个文件，测试不污染产物目录。

---

## 2026-11-10 15:34 +08:00

### 修改（质量分 Q 四处口径修正 + 决策矩阵一致性闸门，v0.8.1 → 0.9.0）

**背景**：`质量分Q评分规则改造建议-第四节.md` 里逐个子项核账后确认 4 个口径漏洞，
并指出 Q 与第二节"各判一遍、结论却不联动"。本轮按建议的方案 A + B 落地，**权重表一个字没动**
（`QUALITY_WEIGHTS` 仍是 30/25/20/15/10）。

#### 新增

- `config.py`：`QUALITY_ITEM_MAX` 集中管理 16 个子项满分（每组合计 = 组权重，有测试断言守着）；
  `QUALITY_GM_LEVEL_FLOOR = 15.0`、`QUALITY_GM_LEVEL_FULL = 25.0`（毛利率水平门槛，上限与护城河定价权同口径）；
  `QUALITY_ACCRUAL_YEARS = 3`。
- `screen/score.py`：`_gate_level(risks)` —— 闸门会把买入类结论压到 `avoid` / `watch` / `None`；
  `_risk_gate(result, risks)` —— 实际降级并写明理由。
- `data["risks"]["gate_level"]`：供第四节一致性行使用，避免 render 再抄一遍阈值。
- 第四节 Q 卡片下一行一致性提示；`METHODOLOGY.md` §7 新增「一致性闸门」小节。

#### 修改（A1~A4）

- **A1 毛利率稳定性加水平门槛**：`inverse(σ, 0, 5, 4) × clamp((毛利率中位数 − 15) / 10, 0, 1)`。
  σ 只说明稳不稳，不说明高不高——300058 毛利率中位 3.4%、σ 1.60，旧口径给 2.72 分，现在 **0 分**。
- **A2 应计利润改近 3 年中位数**：单年预收/应付集中结算不再决定这一格；raw 同时给“单年 x%、3 年中位 y%”。
  600519 单年 6.8%、3 年中位 3.0% → 1.60 → **3.51 分**。
- **A3 现金组加 FCF/营收（0~15% → 0~4）**，FCF 为正年数由 10 分降到 6 分：
  比值不受规模干扰，且与护城河「现金创造」同口径。
- **A4 资本回报组加 `ROIC>WACC 年数`（比例 ×10）**，ROIC−WACC 20 → 14、ROE 10 → 6：
  中位数看不出持续性（000725 5 年里只有 1 年高于 WACC）。分母用“有 ROIC 的年份”，缺数据不算低于 WACC。
- `_decision(q, v, fatal, data_quality, risks=None)`：多收一个 `risks`，**没有**把命中数塞进
  `buy_blockers`（那是“没算出来”，闸门是“算出来不好”，混在一起读者分不清）。`risks` 省略时不加闸门，老调用方不受影响。
- 闸门规则：命中 ≥2 项或一票否决位（现金流质量/现金短债比）命中 → 买入类降**回避**；
  提示 ≥2 项或命中 1 项 → 买入类降**观察，第二节有信号**；只压买入方向，负面结论不动；
  **闸门先于数据完整性**（回避比观察重，不能被“机构覆盖不足”盖掉）。
- `_tracking()`：`CFO/净利润` 改用 TTM 口径、阈值取 `config.CASH_NI_OK`（0.7），删掉单独的 `CFO_NI_FLOOR = 0.8`
  ——原来跟踪线比判定线严 0.1，报告里两处数字看着像打架。
- `screen/render.py` 第四节：标题改「质量分构成（五个维度，第二节不参与打分）」；正文改成
  “Q 看 5 年长期水平、第二节看当期异常，判定方式不同，结论取更谨慎的一方”；
  分档表后补一句“分档只是标签，不改变结论矩阵”；决策规则块补两条闸门规则。
- `tests/test_quality.py`：`fcf_margin` 纳入完美公司夹具；缺数据用例补 `fcf_margin=None`；
  应计 raw、ROIC/ROE 满分、子项数 14 → 16 等断言按新口径重算。
- 文档：`METHODOLOGY.md` §3 重写（四处修正 + 分档说明）、§7 闸门；`README.md` 质量分表、结论矩阵、目录；版本号 → 0.9.0。

#### 效果（4 只样本，同一批数据；与建议书 §6 完全对上）

| 样本 | 旧 Q | 新 Q | 变化来源 |
|---|--:|--:|---|
| 600519 贵州茅台 | 89.0 | **90.9** | 应计改 3 年中位（1.60→3.51 分） |
| 000725 京东方A | 40.6 | **40.7** | 资本回报 0→2.0（ROIC>WACC 1/5）、现金组 −1.97（FCF/营收 7.6% 只给 2.04/4） |
| 300058 蓝色光标 | 56.5 | **50.1** | 毛利率稳定性 2.72→0（A1）、现金组 −3.7（FCF/营收 1.2% 给 0.31/4） |
| 600036 招商银行 | 不适用 | 不适用 | 金融股不进入 Q |

结论层三只都没变（好公司等价格 / 回避 / 回避）；300058 本就是回避，闸门不会再降。
Q 卡片下新增的一致性行：600519「命中 0 项、提示 1 项 → 未触发降级」，
300058「命中 1 项、提示 4 项 → 已达降级线（买入类会降为观察），但当前结论不是买入类，未再降级」。

#### 修复

- A1 落地时发现：只有 1 年披露毛利率时 `stdev()` 返回 `None`，`None × 水平修正` 会直接崩。
  改为“σ 或中位数任一为空就不给分”，并加用例 `test_single_year_margin_is_not_scored` 守着。

#### 测试

`python3 -m unittest discover -s tests`：**399 个用例通过**（0.8.1 为 359），新增
A1 边界 6、A2 中位数 3、A3 FCF/营收 5、A4 ROIC 年数 4、子项满分/权重 3、闸门 16、第四节 3、契约 1。

---

## 2026-11-10 15:20 +08:00

### 修改（① 毛利率环比改善：从一句"未改善"改成六个数字 + 点名，v0.8.0 → 0.8.1）

**背景**：报告里原来只有一句
`① 毛利率环比改善判定：未改善（缺 C3）；✅环比增✅营收环比不降❌高于上年同季｜26Q3 毛利率 89.64%（环比 +0.38pct）…`，
标题右侧的 badge 更是只有一个 `［未改善］`。读者看不出**是毛利率还是净利率还是营业收入、
是同比还是环比**没改善。000725 就是典型：旧文案只说"缺 C2"，实际当期**营收同比 −8.6%、
环比 −6.6%，净利率由 +2.54% 转成 −2.05%**，这些数字一个字都没露。

#### 新增

- `screen/score.py`：`_delta()`、`_change_level()`、`_rest_note()` 三个小工具；
  `_margin_improve()` 改为返回 `(状态, 表格说明, compare)`，`compare` 含：
  - `rows`：营业收入 / 毛利率 / 净利率 × 同比 / 环比 共 **6 个变化**（含数值、单位、等级）；
  - `yoy_line` / `qoq_line`：两行可直接渲染的对照文本（带上年同季 / 上一季的原始值）；
  - `verdict`：结论句，点名"未改善的是「指标+口径」（变化值）"，并交代其余项与缺数据项；
  - `badge`：标题右侧标签文本；`cond`：C1/C2/C3 三个布尔值。
- `config.py`：`MARGIN_IMPROVE_EPS` 继续作为比率型"持平"容差（0.05pct），营收用 ±0.1%。

#### 修改

- `screen/render.py`：`_margin_chart()` 的 badge 改用 `compare["badge"]`，
  判定区从一行变成四行——判定结论、同比对照、环比对照、点名结论。
- `screen/score.py`：`add()` 返回刚 append 的检查字典，便于挂 `compare`；
  金融股的 `margin_improve` 同步清空 `compare`（银行没有毛利率可比口径）。
- 文案：`未改善（缺 C3）` → `未改善（C3 不成立）`，并补 `改善（C1/C2/C3 成立）`、
  `走弱（C1/C3 不成立）` 两种标签。
- `tests/support.py`：`margin_data()` 支持第 4 个元素（单季净利率），夹具补齐净利率。
- 测试：`MarginImproveTest` 由 6 个用例扩到 10 个（同比/环比六个数字、badge、
  净利率独自走弱、净利率缺失、季报不连续时 `compare` 为空），总数 355 → **359**。

#### 效果（4 只样本，同一批数据）

| 样本 | 旧 badge | 新 badge | 新增可见的数字 |
|---|:--:|:--:|---|
| 600519 | ［未改善］ | ［毛利率同比走弱］ | 营收同比 +3.1%（旧文案没有）、净利率同比 +0.33pct |
| 000725 | ［未改善］ | ［营业收入同比、环比下滑；净利率同比、环比走弱］ | 营收 −8.6% / −6.6%、净利率 −4.59pct / −8.84pct（转负） |
| 300058 | ［未改善］ | ［毛利率环比走弱；营业收入同比下滑］ | 营收同比 −1.1%、净利率同比 −0.01pct（持平） |
| 600036 | ［不适用］ | ［不适用］ | 金融股不输出对照 |

#### 不变

- **判定口径不变**：仍是 C1/C2/C3 三条件，净利率不参与判定（只在结论句提示），
  所以 4 只样本的 `hit/watch/clear` 状态、Q/V 分、结论全部与 0.8.0 一致。

---

## 2026-11-10 14:47 +08:00

### 修改（报告第一、二节指标改造，v0.7.11 → 0.8.0）

**背景**：用 4 只真实样本（600519 / 000725 / 300058 / 600036）把第一、二节逐指标对照后，确认三类问题：

1. 护城河 5 项加权评分为茅台算出 **99.3 分**——"接近满分"既不提供信息也不可信；
2. 第二节 10 项检查有三个方向性漏洞：检查 6 要求"营收负增长"才会看应收，赊销冲量（营收 +30%/应收 +52%）直接判通过；流动比率看不出"短期借款 41 亿、现金 4.46 亿"这种明天就出事的结构；其他应收款、期间费用率两个排雷口完全空白；
3. 股本稀释（3 年 CAGR >2%）把"增发换来增长"误报为摊薄：300058 股本 +44.1% 命中，但同期每股营收 +29.9%。

按《指标对照与修改建议-报告第一二节》（已确认范围）落地。目标版本 `config.VERSION = "0.8.0"`。

#### 新增

- `config.py`：`RISK_CHECK_COUNT=14`、`RISK_GROUPS=("真伪","趋势","质量","安全")`、
  `RISK_HEADLINE_KEYS=("cash_flow","cash_debt")`、
  `FINANCIAL_INAPPLICABLE_CHECKS=(margin_improve, ar_gap, inventory_gap, construction, cash_debt)`。
- `config.py`：护城河三证据阈值 `MOAT_GROSS_MARGIN_MIN=25 / MOAT_GROSS_MARGIN_STD=3 /
  MOAT_ROIC_SPREAD_MIN=5 / MOAT_ROIC_ABOVE_YEARS=4 / MOAT_FCF_MARGIN_MIN=5`；
  `MARGIN_IMPROVE_EPS=0.05`、`PAYABLE_SLIP_WEAK=0.30`、`PAYABLE_SLIP_STRONG=1.00`。
- `config.py`：净现比四档 `CASH_NI_GOOD/OK/WEAK/TWO_YEAR`；现金短债比
  `CASH_DEBT_RATIO_MIN/FATAL/CALM`；`AR_REV_GAP_ALERT / AR_MATERIAL_RATIO /
  INV_REV_GAP_ALERT / INV_REV_GAP_HIGH / INV_MATERIAL_RATIO`；`OTHER_AR_ASSETS_MAX`；
  `CL_GROWTH_MIN / CL_REV_MIN`；`EXPENSE_GROWTH_GAP`；`QUICK_RATIO_WATCH`。
- `screen/compute.py`：`_period_record()` 增记 `ocf_ttm / icf / fcf_fin / working_capital /
  receivable_fin / payable / other_ar / other_ap / contract_liability / advance_payment /
  short_loan / ncl_1y / construction / fixed_asset / sell_expense / admin_expense /
  rnd_expense / np_ttm` 18 个字段；`_margin_trend()` 每个点补 `revenue`（供 ① 判定用）。
- `screen/compute.py`：新增 `_structure(annual, years=5)`，逐年输出
  `bargain / payable / ar_inv / contract_ratio / construction_ratio / debt`，并汇总
  `bargain_latest / bargain_trend / contract_latest / contract_yoy`；`build_financials()`
  返回值增加 `structure`。
- `screen/score.py`：新增 `_margin_improve()`（① 三条件：环比增、单季营收环比不降、高于上年同季，
  按 `year*4+quarter` 定位上一季与上年同季）、`_yi / _delta_pct / _growth / _ar_total /
  _contract_liab / _expense / _quarter_index` 等助手。
- `screen/score.py`：新增 `_CHECK_TAGS`（key+状态 → 赊销/现金弱/短债/加杠杆/库存/毛利走弱/
  失血/非经常/体外/摊薄）与 `_pattern_summary()` 的组合定性句。
- `screen/render.py`：新增 `_bargain_verdict()`、`_structure_line()`（货款占用 + 销售端一行）、
  `_margin_chart` 的 `［未改善］` 徽标与判定行、检查表的分组行/折叠行/组合定性框。
- `templates/report.html`：`.status.watch`、`.status.na`、`tr.group-row td`、`tr.fold-row td`。

#### 修改

- `screen/score.py`：`_risk_checks()` 由 10 项重写为 **14 项 / 4 组**，签名改为
  `add(key, group, name, status, detail, severity, tag)`；状态词汇由 `hit/clear/unknown`
  扩为 `hit/watch/clear/unknown/na`。
- `screen/score.py`：`_moat()` 由 5 项加权评分改为**三条证据**（定价权 / 资本回报 / 现金创造），
  返回 `{level, evidence[], reasons, met, total}`；3 条 → 宽、2 条 → 窄、≤1 条 → 无明显。
- `screen/score.py`：`BUY_CRITICAL_CHECKS` 由 `(cfo_ni, leverage, goodwill, nonrecurring, liquidity)`
  改为 `(cash_flow, leverage, goodwill, nonrecurring, cash_debt)`；`_fatal()` 四条不变。
- `screen/score.py`：`_data_quality()` 增加 `risk_na`，`risk_known` 不计 `na`；
  `data["risks"]` 增加 `watches / clears / headline / summary`。
- `screen/render.py`：第一节年报表由 8 列增至 10 列（有息负债、在建工程/固资），护城河块改为
  `三条证据 x/3` + ✅/❌ 列表并删掉量化评分；第二节改为按组渲染、通过项折叠。
- `screen/validate.py`：检查项数改为读 `config.RISK_CHECK_COUNT`。
- 测试：`tests/support.py` 夹具补全新字段与 `margin_data()`；`test_risk_decision.py` 按新契约重写；
  测试总数 303 → **355**（全部通过）。

#### 删除

- 「少数股东占比 >30%」检查（手册无此条，与净利润口径重复，4 只样本无一触发），
  同时删掉 METHODOLOGY §2 的少数股东占比公式。
- 护城河 0~100 量化评分及报告中的「量化评分」一行。
- 死常量 `SHARE_DILUTION_MAX / CURRENT_RATIO_MIN / QUICK_RATIO_MIN /
  REVENUE_GROWTH_NEGATIVE / AR_INV_GROWTH_ALERT`；`AR_INV_BASE_RATIO_MIN` 更名为
  `AR_BASE_RATIO_MIN`（0.8.0 起它只服务于应收，存货用 `INV_MATERIAL_RATIO=1%`）。

#### 修复

- **600519 应收增速差误报 +2580pct**：`_ar_total()` 把 `ReceivablesFin`（应收款项融资，
  票据结算）并进应收增速差；改为增速差只用 `BillAccReceivable`，占款比仍用两者之和。
- **300058 存货 "+113%" 噪音**：存货占营收仅 0.02%，加 1% 小基数门槛后判 `unknown`。
- **600036 把银行当工商企业算**：有息负债 88,814 亿、在建工程、现金短债比全部显示；
  新增 `FINANCIAL_INAPPLICABLE_CHECKS` 5 项标 `na`，年报表对应单元格显示"—"。
- **金融股杠杆数量级误导**：`leverage` 落在 `unknown` 时 detail 不再摆"有息负债 88,814 亿 →…"，
  改为"金融股不适用本口径（有息负债含同业负债，EBIT 不可比）"。
- **"FCF 0 年中 0 年为负"这种空话**：无可用 FCF 年度时改为"FCF 无可用年度（口径不适用）"。
- **第四节把 `na` 当已知**：`risk_known = 总数 − 数据不足` 把 5 项不适用也算成已知，招商银行显示
  "风险检查 11/14 已知"，与第二节的 "6/9" 打架；报告第四节与 CLI 摘要的分母都改为「适用项」
  （`总数 − na`）。
- **在建工程 detail 只说"同期有息负债未增"**：读者看不出结论，改为直接写
  "自有资金扩产（同期有息负债未增）" / "借钱扩产（同期有息负债增加）"，tag 仍用于组合定性。
- 毛利率环比按列表位置取 `[-2]/[-5]` 会拿错报告期（只保留 6 个季度时），改按季度索引定位。
- `_structure()` 里 `reversed(annual)[-years:]` 不可下标（`TypeError`）、`annual` 为空时
  `ys[-4]` 越界（`IndexError`）。

#### 影响（口径变化，必须知道）

- **第二节结论的构成变了**：一票否决位（现金流质量、现金短债比）命中只在组合定性句里点名，
  **不新增 `_fatal()` 条件**；致命项仍是净资产为负、利息保障 <1、商誉 >50%、
  连续 3 年 OCF 为负且净负债/EBIT >4 四条。
- **Q 分与 V 分权重未动**：护城河评分本来就不进 Q，删除后 Q 分不变（600519 Q=89.0）。
- **4 只样本的验收结果**（2025 年报口径，与《建议》§5 逐条对上）：

  | 样本 | 护城河 | 命中 / 提示 / 不足 / 不适用 | 结论 |
  |---|:--:|:--:|---|
  | 600519 | 3/3 宽 | 0 / 1 / 1 / 0 | 唯一提示是 ①"未改善（缺 C3）"（89.64% vs 上年同季 91.28%） |
  | 000725 | 1/3 无 | 1 / 3 / 0 / 0 | 杠杆 8.39 命中；在建"自有资金扩产"、存货增速差 +15.9pct 提示 |
  | 300058 | 0/3 无 | 1 / 4 / 2 / 0 | 每股口径命中（股本 +44.1%、每股 OCF −59.4%），存货未误报 |
  | 600036 | 不适用 | 0 / 0 / 3 / 5 | 5 项 `na`、3 项 `unknown`，结论"金融股不适用" |

- **② 合同负债的口径**是 `ContractLiability + AdvancePayment`（预收款项与合同负债同一经济含义，
  000725 的预收还有 8.11 亿），所以同比与只算合同负债的旧数不同（000725 +11.6% vs +6.7%）。
- 文档同步：`README.md`（输出结构、小基数保护、测试清单）、`METHODOLOGY.md`（§2 指标字典、
  新增护城河三证据、§4 改写为 14 项 4 组、§7 关键检查名单）、`config.py` 注释。

---

## 2026-11-10 13:28 +08:00

### 修改（估值口径统一为「口径日收盘」，v0.7.10 → 0.7.11）

**背景**：走势图上标「最新 2026-11-09：21.99」，上方分位表却显示「当前 21.95」——
表用行情实时 PE/PB，图用估值序列（周频收盘），读者对不上。按确认结论改为
**全篇估值只用收盘口径**，牺牲一点时效性换一致性。

- `screen/compute.py`：`_valuation()` 的当前值改为取**序列最后一点**
  （`ordered[-1]` 的 PE_TTM / PB_MRQ / PS_TTM），不再读 `quote["pe_ratio"] / pb_ratio`；
  最后一点缺失或为负时退到最后一个有效值。签名去掉已无用的 `quote` 参数。
- `screen/compute.py`：新增 `_close_price()`，取「口径日」（序列最后交易日）的收盘价：
  1. 行情日期 == 口径日 → 行情价（盘后运行，价即时收盘）；
  2. 否则用 `prev_close`（盘中运行时它就是上一交易日收盘）；
  3. 再否则 `PE(TTM) × EPS(TTM)` 反推（与图上那条线同源）；
  4. 兜底实时价。反推值与 `prev_close` 相差 >5% 时以反推值为准（除权/序列错位）。
  返回 (价格, 口径说明)，说明直接写进报告头。
- `screen/compute.py`：`market_cap_yi()` 增加 `price` 参数，传入时按该价重算市值；
  不传时保持原逻辑（单位校准 + 实时价）。
- `screen/compute.py`：`meta` 新增 `price_basis`（如「2026-11-09 收盘」）、
  `price_date`（口径日）、`live_price`（实时价，仅留档）；`meta.price` 改为收盘价；
  `meta.pe/pb/ps` 改为估值序列口径（与分位表一致），不再混用实时 PE/PB。
- `screen/render.py`：报告头改为「¥ 1,444.99 市值 18,063.55 亿元 · 2026-11-09 收盘」，
  下一行「估值口径 2026-11-09 收盘 · 数据快照 2026-11-10 · 最新报告期 2026-09-30」；
  分位表表头「当前」→「最新收盘」；第三节增加一句「全篇估值口径统一为 X 收盘」，
  说明表、图、目标价空间、现金底线市值用的是同一个价。

### 影响

- 目标价空间、预测 PE 相对当前 PE、现金底线的总市值/安全边际、V 分，都改为按收盘价计算：
  600519 实测收盘 1,444.99（实时 1,441.35，差 +0.25%），V 62.2 → 62.1，其余结论不变。
- 盘中运行时会比行情软件慢一个交易日，这是刻意取舍；报告头两行写明了口径日与快照日。
- 分位百分比会跟着当前值微调（21.95 → 21.99 时 PE 分位 17.8% → 18.2%）。

### 新增（回归测试）

- `tests/test_compute.py`：`ClosingBasisTest` 9 个用例——当前值忽略实时报价、
  分位按收盘算、`_close_price` 四条取价路径（同日/prev_close/反推/兜底）、
  反推与 prev_close 差 5% 时改信反推、`market_cap_yi` 按收盘价重算。
- `tests/test_render.py`：表头「最新收盘」与口径日说明 1 个用例；
  头部测试改为断言「收盘价 + 市值 + 口径日」而非写死的实时价。

### 修改（文档）

- `METHODOLOGY.md`：分位小节改为「当前值 = 序列最后一点」；新增
  「全篇统一的估值口径日」小节（口径日定义、取价优先级、报告头写法）；
  §8 限制第 11 条改写为「盘中运行比实时价滞后一个交易日，是刻意取舍」；版本号 0.7.11。
- `README.md`：重要边界新增第 15 条（收盘口径 + 代价 + 报告头写法）。
- 全部 303 个用例通过。

---

## 2026-11-10 12:58 +08:00

### 修复（核查第一轮：取数与口径，影响评级结论）

- `screen/compute.py`：**年度资本开支取错了行，FCF 系统性虚高**。
  东财 `RPT_F10_FINANCE_GCASHFLOW` 的 `CONSTRUCT_LONG_ASSET` 是「年初至今累计」，
  同一年 03-31 → 12-31 递增；原代码按年份做 `capex[year] = v` 覆盖写，
  而接口按日期**降序**返回，结果每年都停在 **Q1 累计值**上。
  修复：只认 `REPORT_DATE` 以 `-12-31` 结尾的年报行；该年没有年报行时 FCF 记为未知。
  - 实测（东财对照）：600519 2025 年 capex 应为 31.28 亿，原代码取 9.01 亿，
    FCF 从 583.95 亿虚报到 606.21 亿；五年累计虚报 80~140 亿。
  - 重资产股更严重：000725 2025 年 capex 400.9 亿被取成 90.5 亿，
    FCF 87.3 亿虚报为 397.8 亿（**4.5 倍**），2021~2024 年同样虚报 230~310 亿。
  - 影响：第一节「五年经营轨迹」FCF / FCF/营收、护城河结论里的
    「5 年 FCF/营收中位数」、Q 分「现金创造力」组、风险检查 2「FCF 持续性」。
    600519 的 Q 由 89.1 → 89.0（几乎不变），重资产股会明显下修。
- `screen/score.py`：风险检查 6「应收/存货背离」在应收与存货科目**都缺失**时
  （银行、保险）原判 `clear`（通过），改为 `unknown`。之前银行会被误判为“通过”。
- `screen/score.py`：机构预期增速的兜底 CAGR 起点取错年份。
  `financials.annual` 是**降序**（最新在前），原代码取 `annual[-1]`（最早一年），
  年限被拉长、基数换成了更小的旧值，成长股增速被**高估**
  （示例：2025 年 80 亿 → 2028 年 100 亿，正确 7.72%，原代码按 2023 年 60 亿算成 10.76%）；
  改为 `annual[0]`。同时「最近年报亏损」的判断也随之回到最新一年。
  仅影响「预测行没有 netProfitYoy」时的兜底路径，600519 这类有 yoy 的不受影响。

### 新增（第一轮回归测试）

- `tests/test_compute.py`：
  - `test_capex_takes_annual_row_not_q1_of_same_year`：同年 Q1/Q3 行不得覆盖 12-31 行。
  - `test_year_without_annual_capex_row_stays_none`：只有季报行时 FCF 必须是未知。
- `tests/test_risk_decision.py`：
  - `test_unknown_when_both_ar_and_inventory_missing`：科目缺失不得判通过。
  - `ForecastGrowthBaseTest` 两个用例：兜底 CAGR 从最近年报起算、
    最近年报亏损时不得用早年利润算增速。

### 修复（第二轮：口径与健壮性，按确认结论实施）

- `screen/score.py` + `config.py`：新增**金融股不打分**通道。行业名命中
  `config.FINANCIAL_INDUSTRY_KEYWORDS`（银行/保险/证券）时，Q 与 V 都置为
  `not_applicable`，等级显示「金融股不适用」，决策输出「金融股不适用，不做初筛」；
  `screen/validate.py` 相应允许 Q 为 `None`（原会直接抛「质量分无法计算」）。
  - 原因：银行没有毛利率、FCF、应收/存货、净有息负债这些科目，硬算只会得到一堆 0 分，
    再匹配出一条“回避”结论，等于用错误的尺子量。
  - 影响：银行/保险/券商不再输出 30~40 分的假 Q 分，也不进买入矩阵。
- `screen/score.py` + `config.py`：风险检查 6「应收/存货背离」加**小基数门槛**
  `AR_INV_BASE_RATIO_MIN = 0.005`。应收或存货占营业收入不足 0.5% 时不计增速
  （几百万的波动就能造出几百个百分点），两项都被跳过时判 `unknown`
  （“应收与存货无可比基数”）而不是 `clear`。
  - 影响：绝对额极小的公司不再被误报“背离”，但也不会因为跳过而白拿一个“通过”。
- `screen/compute.py`：新增 `_first_num()`，替换 5 处 `num(a) or num(b)` 写法
  （营业收入、归母净利、经营现金流、EBIT、ROE）。`or` 会把合法的 0 当成缺失，
  例如归母净利恰为 0 时会错误回退到 TTM 口径，ROE 为 0 时会回退到摊薄值。
- `screen/compute.py`：删除 `meta.latest_revenue / latest_net_profit / latest_ocf /
  latest_fcf` 四个从未被渲染的字段，以及只用于给它们赋值的局部变量。
- `screen/render.py`：第三节分位文案改为按**序列真实起始年份**表述
  （「上表为 2018 年以来周频分位」），无样本时回退「全部可用历史（周频）」。
  原先写死“全部可用历史”，对 2021 年上市的新股会和读者理解不一致；
  而写死 2018 又会冤枉新股，所以取 `valuation.sample.start` 的年份。
- `screen/render.py`：第四节补金融股空态。Q/V 为 `None` 时原来会渲染出两张**空表格**
  和一句“Q 数据覆盖 0.0% / 可买还需满足 Q 覆盖≥80%”，与“不做初筛”自相矛盾。
  现在两张表各出一行 `colspan=3` 的说明（“金融股不适用：……不套用五维口径”），
  数据完整度一行只保留风险检查与机构覆盖，决策规则矩阵整块换成一句“不进入买入门槛矩阵”。
  同时删掉 `_section_score` 里从未使用的 `key` 局部变量。
- `stock_report.py`：单股模式的控制台摘要 `f"{data['quality']['score']:.1f}"` 在金融股上
  直接抛 `TypeError: unsupported format string passed to NoneType.__format__`（退出码 3，
  但 HTML 已落盘）。抽出 `_score_line()`，`None` 时显示「不适用」（V 缺失但非金融股仍显示「—」），
  并在输出里去掉多余的 `/ 100`。

### 新增（第二轮回归测试）

- `tests/test_quality.py`：`FinancialStockTest` 4 个用例——Q/V 均不适用、
  决策文案为“不做初筛”、`validate` 不抛错、非金融行业不受影响。
- `tests/test_risk_decision.py`：小基数 3 个用例（单项极小时忽略、两项都极小时 unknown、
  科目都缺失时 unknown）+ `ForecastGrowthBaseTest` 2 个用例。
- `tests/test_render.py`：分位起始年份 2 个用例（有样本用真实年份、无样本回退全历史）；
  金融股空态 1 个用例（两张表各一行 `colspan=3`、不出现“可买还需满足/Q 数据覆盖”）。
- `tests/test_cli.py`：`ScoreLineTest` 3 个用例（正常分数、金融股不适用、V 缺失显示 —）。

### 修改（文档）

- `METHODOLOGY.md`：
  - 单位一节补充「东财资本支出是年初至今累计，只取 12-31 行」；指标表 FCF 公式标注两个输入都取 12-31。
  - §3 质量分 Q 增加「金融股不做 Q/V 打分」的说明（含触发关键词与决策文案）。
  - §4 风险检查表补充第 6 项的小基数保护（<0.5% 营收不计增速，双项跳过判 unknown）。
  - §7 结论规则补充「金融股不进入决策矩阵」；§8 限制第 4 条改为“识别到金融行业直接标不适用”。
  - 版本号同步 `0.7.10`。
- `README.md`：
  - 8 类数据表第 8 行、重要边界第 6 条补充资本支出口径说明。
  - 评分口径一节 Q 表下增加「金融股不打分」提示框；重要边界第 4 条改写，
    新增第 14 条写小基数保护。

### 影响（本轮合计）

- FCF 及其派生指标回到与年报一致的量级；重资产、高扩张行业的 Q 分与护城河等级会明显下修，
  消费/轻资产公司变化很小。
- 风险检查的“已知项数”会因银行股多 1 项 unknown 而下降（10/10 → 9/10 之类），
  从而更不容易给出“可买”。
- 金融股从“给低分 + 回避”改成“不适用、不下结论”，避免用工业/消费的尺子量银行；
  报告第四节不再出现空表格和“Q 覆盖 0.0%”这类自相矛盾的提示。
- 全部 293 个用例通过。

---

## 2026-11-10 12:34 +08:00

### 修改

- `config.py`：`TREND_QUARTERS = 15` 改为
  `TREND_YEARS = 5` + `TREND_QUARTERS = TREND_YEARS * 4`（= 20），
  利润率曲线的窗口从「15 个季度」变成「5 年（20 个季度）」。
- `screen/render.py`：第一节的利润率标题由「近 15 个季度利润率趋势」改为
  「近 5 年季度毛利率/净利率趋势」（标题、空态标题、`aria-label` 三处统一用
  `config.TREND_YEARS` 拼接，不再写死数字）。
  图下注释在季度不足时的措辞由「少于 15 个季度」改为
  「不足 5 年（需 20 个季度，已展示全部可用季度）」。
- `README.md`：输出结构第一节、8 类数据表第 3 行、重要边界第 7 条同步为「近 5 年 / 20 个季度」。
- `METHODOLOGY.md`：§1 小节标题与说明改为「近 5 年季度毛利率/净利率曲线」，
  写明取 `data_finance(num=20)` 的 20 个报告期、不足 20 个时展示全部；§8 限制第 7 条同步。

  > 数据侧不改：`data_finance` 本来就取 20 个报告期，正好等于 5 年 × 4 个季度，
  > 所以这次只是把「只看 15 个」的截断去掉，没有增加请求。

### 新增

- `tests/test_compute.py::MarginTrendTest`：窗口改为 20 个季度（8 年数据只留最近 20 个），
  新增「历史不足 20 个季度时全量展示」用例。
- `tests/test_render.py`：新增 4 个用例 —— 空态带新标题、满 20 个季度不写「不足」、
  6 个季度时写「不足 5 年」、`aria-label` 用 `TREND_YEARS`。
- `tests/test_smoke.py`：`test_margin_chart_labels_all_quarters_in_five_years`
  改为 20 个季度、20 个刻度标签。

### 影响

- 第一节的利润率曲线从 15 个季度（≈3.75 年）扩到 20 个季度（5 年）。
  600519 实测由「23Q1–26Q3，共 15 个季度」变为「21Q4–26Q3，共 20 个季度」，
  时间轴 20 个刻度全部标出（10px 字号，620px 绘图区，间距 32.6px 不重叠）。
- 新股 / 停牌股只有几个季度时，图照常画，但会注明「不足 5 年（需 20 个季度）」。
- 曲线仍只作展示：不进入 Q/V、风险检查或决策矩阵，Q/V 与结论不受影响。
- 全部 276 个用例通过。

---

## 2026-11-10 12:24 +08:00

### 修改

- `config.py`：新增 `VALUATION_YEARS = 10`；`TREND_QUARTERS = 15` 的注释改为只描述利润率曲线，
  两个窗口从此各管一段，不再共用一个起点。
- `screen/compute.py`：
  - 新增 `_years_before(iso, years)`：把 ISO 日期往前推 N 年，2 月 29 日回退到 2 月 28 日，
    空值/非法日期返回空串（等价于不截断）。
  - `_valuation()` 的 `chart_start` 参数改为 `years`（默认 `config.VALUATION_YEARS`），
    窗口从**最后一条可用数据**往前推 10 年，而不是从「最近 15 个报告季度的起点」切。
  - `_valuation_chart()` 新增 `years` 参数与 `years / span_years / limited` 三个返回值：
    `span_years` 为窗口内实际覆盖年数，`limited` 表示可用历史不足目标年数。
  - `build_report_data()` 不再从 `margin_trend.start` 取起点传给估值图。
- `screen/render.py`：
  - 第三节说明文字由「下图为近 15 个季度周频走势」改为
    「下图为近 10 年周频走势（可用历史不足 10 年时按全部可用历史）」。
  - 三张图的 `aria-label` 改为「近 10 年 PE(TTM)/PB(MRQ)/PS(TTM) 周频走势」。
  - 图下注释改为「数据范围：起 至 止（近 10 年周频，共 N 个周度点）」；
    历史不足 10 年时显示「可用历史约 N 年，已全部展示」（不足 1 年单独措辞）。
  - 空态文字由「暂无近 15 个季度估值数据」改为「暂无估值序列数据」。

### 新增

- `tests/test_compute.py::ValuationChartWindowTest`：6 个用例，覆盖
  10 年窗口起点（含截止日当天）、分位与样本仍用全历史、历史不足 10 年
  （`limited=True`）、`years=0` 关闭窗口、`_years_before` 的闰日/空值/非法输入、
  空序列的窗口元数据。
- `tests/test_render.py`：新增第三节文案断言、图下注释两种措辞断言、`aria-label` 断言。

### 修改（测试）

- `tests/test_compute.py`：`test_chart_window_and_negative_band` 改为
  `test_chart_keeps_all_weeks_when_window_off`（`years=0`），不再依赖 `chart_start`。
- `tests/test_smoke.py`：端到端断言由「不得出现近 15 个季度估值走势」升级为
  正面校验「下图为近 10 年周频走势」，并保留旧文案的排除断言。
- `tests/test_render.py`：空态断言同步新文案。

### 影响

- 估值走势图从约 15 个季度（≈196 个周度点）扩展为近 10 年
  （600519 实测 2018-01-05～2026-11-09，454 个周度点）。
- 东财 `RPT_VALUEANALYSIS_DET` 一般只回溯到 2018 年，所以多数个股实际是
  「8~9 年」；报告会明确写出「可用历史约 8.8 年，已全部展示」，不会假装有 10 年。
- 分位表、V 分、决策矩阵不变：分位仍按全部可用历史计算，走势图仍只是展示。
- 行情/估值取数不变（本来就拉全量再压缩周频），无额外请求、无额外耗时。
- 全部 272 个用例通过。

---

## 2026-11-10 12:09 +08:00

### 删除

- `screen/compute.py`：整段删除 `_dcf()`（39 行）及 `build_report_data()` 返回值里的
  `"dcf"` 键；同时删除只服务于 DCF 脚注的 `fcf_yield` 计算与
  `meta["fcf_yield"]` 字段。
- `screen/render.py`：第三节删除 `<h3>对企业进行 DCF 估值</h3>` 整块，包括
  「FCF0 / g1 / 折现率 / 合理价 / 相对现价」五行表格和
  「FCF 收益率 / 要求收益率」脚注；页脚 `method`、`limits` 两段同步去掉 DCF 措辞
  （`FCF/DCF` → `FCF`）。
- `screen/score.py`：第五节跟踪表删除「DCF 折价」一行，跟踪项由 8 行降为 7 行。
- `config.py`：删除 `DCF_G`、`DCF_YEARS`、`REQUIRED_FCF_YIELD` 三个参数。
  `WACC` 保留，仍用于 ROIC−WACC 与护城河判断。
- `METHODOLOGY.md`：删除「#### FCF 收益率」「#### DCF」两节口径推导，
  §8 已知限制第 1 条改为只说明 WACC 用途。

### 新增

- `tests/`：为整个工具补充测试，覆盖 262 个用例。
  - `tests/support.py`：共用夹具（`raw_bundle` / `report_data` / `scored_data`、
    `annual_rows`、CSV 读写助手）。
  - `tests/test_util.py`、`test_fetch.py`、`test_compute.py`、`test_quality.py`、
    `test_risk_decision.py`、`test_render.py`、`test_io.py`、`test_cli.py`：
    分别覆盖数值清洗、取数与重试、报表整理与分位、Q 分 5 组 14 项、10 项风险
    与决策矩阵、五节渲染与图表断线、CSV/XLSX/导航页、参数与退出码。
- `tests/test_compute.py::DcfRemovedTest`：DCF 下线的回归守卫，断言
  `_dcf` 不存在、`build_report_data` 无 `"dcf"` 键、`meta` 无 `fcf_yield`、
  `config` 无 `DCF_*` / `REQUIRED_FCF_YIELD`、源码内不出现 `dcf`。
- `tests/test_render.py::test_dcf_section_removed`：即使传入残留 `dcf` 数据也不渲染。

### 修改

- `config.py`：`VERSION` 由 `0.7.6` 升至 `0.7.7`。
- `METHODOLOGY.md`：版本号同步为 `0.7.7`；§1「质量、风险、FCF、DCF 都使用年报」
  改为「质量、风险、FCF 都使用年报」；§5 引言补一句 DCF 已整体下线。
- `README.md`：输出结构第三节去掉「对企业进行 DCF 估值」；目录表两行去掉 DCF；
  重要边界第 3、4 条去掉 DCF；测试目录补齐 8 个测试文件与 `support.py`。
- `tests/test_render.py`：页脚断言改用 `config.VERSION`，不再硬编码版本号。
- `screen/compute.py`：`from screen.util import cagr, num, year_of` 去掉 `cagr`，
  DCF 是它唯一的使用者。
- `screen/score.py`：删除未被使用的 `import math`。

### 影响

- 生成的 HTML 少一节、少 5 行表格与 1 行跟踪项；第三展现为
  「历史分位 → 机构预期 → 现金扣除与底线估值」三段。
- 估值分 V 不受影响（DCF 早已不进入 V），Q 分、风险检查、决策矩阵不变。
- 报告体积略降；`fcf_yield` 字段不再出现在数据里，外部脚本若读取需改。
- 全部 262 个用例通过；夹具实跑确认 HTML 中 `DCF`、`FCF 收益率` 出现次数均为 0。

---

## 2026-11-09 10:10 +08:00

### 修复

- `screen/fetch.py`：可选数据（`data_profile` / `data_consensus` / `data_rating`）
  改为独立客户端，只做 1 次 3 秒短重试；失败后记录为数据缺口。
  之前它们和关键数据共用 `--retries 2`、`--retry-wait 60`，限频时每只股票会
  多等约两分钟，批量看起来像卡住。
- `providers/westock_client.js`：MCP 返回空 content 时明确报
  「工具返回空内容（可能限频，或服务端没有该股票数据）」，不再输出空错误信息。
- `README.md`：补充可选数据短重试说明。

### 修改

- `config.py`：`VERSION` 由 `0.7.5` 升至 `0.7.6`。
- `METHODOLOGY.md`：版本号同步为 `0.7.6`。

### 影响

- `data_consensus` 限频时不会再阻塞整批 60~120 秒；报告会标注该数据缺口。
- 关键数据（财务、行情）仍按 `--retries` / `--retry-wait` 重试。

---

## 2026-11-09 10:05 +08:00

### 修复

- `screen/fetch.py`：重试等待前打印 `[warn] ... 秒后重试（1/2）`，
  避免批量时看起来“卡住不动”。之前默认重试 2 次、每次等待 60 秒，
  期间终端没有任何输出，容易被误认为进程死掉。
- `README.md`：补充重试提示说明。

### 修改

- `config.py`：`VERSION` 由 `0.7.4` 升至 `0.7.5`。
- `METHODOLOGY.md`：版本号同步为 `0.7.5`。

### 影响

- 批量遇到限频 / 超时 / 非 JSON 时，会明确显示还要等多久，不再静默。
- 实际重试节奏和默认等待时间不变。

---

## 2026-11-09 09:55 +08:00

### 新增

- 批量 CSV 新增 `东方财富网股票详情` 列：
  - 沪深股票：`https://quote.eastmoney.com/{sh|sz}{代码}.html#fullScreenChart`；
  - 北交所股票：`https://quote.eastmoney.com/bj/{代码}.html#fullScreenChart`；
  - CSV 单元格使用 `=HYPERLINK("...","东方财富网股票详情")`。
- `screen/xlsx.py`：XLSX 新增同名超链接列，显示为「东方财富网股票详情」按钮。
- `screen/index_html.py`：导航页新增「东方财富网股票详情」按钮。
- `screen/batch.py`：新增 `eastmoney_url()`、`eastmoney_link_cell()`。
- `tests/test_smoke.py`：新增沪深 / 北交所 URL 映射、CSV/XLSX/导航页链接测试。

### 修改

- `config.py`：`VERSION` 由 `0.7.3` 升至 `0.7.4`。
- `METHODOLOGY.md`：版本号同步为 `0.7.4`。
- `README.md`：补充东方财富网详情列说明。

### 影响

- 现有 CSV 重新运行批量后会多出 `东方财富网股票详情` 列；旧报告全部复用，不重新抓数。
- XLSX 和 `index.html` 同步增加东方财富网链接。

---

## 2026-11-09 09:50 +08:00

### 新增

- `screen/xlsx.py`：批量结束后生成与 CSV 同名的 `.xlsx`，保留全部列；
  `HTML报告链接` 列显示为「报告链接」按钮，使用真正的单元格超链接，
  点击直接打开对应 HTML。无需安装 openpyxl，直接写 OOXML。
- `screen/index_html.py`：在 `--out-dir` 生成 `index.html` 报告导航页，
  每只股票一个「报告链接」按钮，支持按代码 / 名称 / 结论搜索。
- `stock_report.py`：批量结束和中断时自动生成 XLSX 与导航页，并打印路径。
- `tests/test_smoke.py`：新增 XLSX 超链接和 index.html 按钮测试。

### 修改

- `config.py`：`VERSION` 由 `0.7.2` 升至 `0.7.3`。
- `METHODOLOGY.md`：版本号同步为 `0.7.3`。
- `README.md`：说明 CSV 无法保存超链接属性，推荐使用同名 XLSX 或 `index.html`。

### 影响

- CSV 仍保留公式链接；是否可点取决于表格软件是否计算公式。
- 同名 XLSX 和 `index.html` 不依赖公式，链接是真正可点击的。
- 单股票模式不生成 XLSX / 导航页。

---

## 2026-11-09 09:45 +08:00

### 修复

- `screen/batch.py`：CSV 的 `HTML报告链接` 由普通 `file:///...` 文本改为
  `=HYPERLINK("file:///...","打开报告")` 公式。CSV 导入时普通 URL 文本不会自动
  变成超链接，公式才能让 Excel / LibreOffice / WPS 显示为可点击的「打开报告」。
- `screen/batch.py`：新增 `report_link_cell()` 和 `link_target()`；
  `link_target()` 可从 HYPERLINK 公式或旧版普通 URL 中还原真实链接。
- `stock_report.py`：批量回写链接改用 `report_link_cell()`；增量续跑扫描已有报告时，
  改用 `link_target()` 解析 CSV 中的链接，兼容旧版 CSV。
- `tests/test_smoke.py`：断言链接为 HYPERLINK 公式，并验证公式中的 URL 可还原。
- `README.md`：更新链接列说明。

### 修改

- `config.py`：`VERSION` 由 `0.7.1` 升至 `0.7.2`。
- `METHODOLOGY.md`：版本号同步为 `0.7.2`。

### 影响

- 重新运行批量命令会把现有 CSV 的链接列更新为可点击公式；HTML 报告和综合评分不变。
- 旧版普通 `file:///...` 链接仍可被续跑逻辑识别，不会重复生成报告。

---

## 2026-11-09 08:31 +08:00

### 新增

- `stock_report.py`：批量模式支持**增量续跑**：
  - 启动时扫描 `--out-dir` 中 `*-{代码}-企业质量初筛-*.html`，已有报告直接复用并回填 CSV；
  - 只对缺失报告或无法提取结论的股票重新取数；
  - 新增 `--force`，忽略已有报告强制全部重跑；
  - 每完成一只股票就原子回写一次 CSV，`Ctrl-C` 时保存当前进度并退出；
  - 新增 `--retries`（默认 2）和 `--retry-wait`（默认 60 秒），对限频 / 非 JSON / 超时错误自动退避重试。
- `screen/fetch.py`：新增跨线程全局节流（默认 1600ms，环境变量 `WESTOCK_GLOBAL_INTERVAL_MS`），
  避免多线程同时请求触发腾讯自选股限频；`WestockClient` 支持按错误类型重试。
- `tests/test_smoke.py`：新增“已有报告不重新取数”和 `--force` 强制重跑的测试。

### 修改

- `config.py`：`VERSION` 由 `0.7.0` 升至 `0.7.1`。
- `METHODOLOGY.md`：版本号同步为 `0.7.1`。
- `README.md`：补充增量续跑、进度保存、限频保护和重试参数说明。

### 影响

- 重跑同一批 CSV 时，已生成且可解析的 HTML 不会重复抓数，只补缺失股票。
- 批量过程中按 `Ctrl-C` 会保留已完成部分的 CSV 结果；再次运行自动续跑。
- 单股票模式的输出不变，但默认在限频 / 超时情况下会先重试 2 次。

---

## 2026-11-09 08:18 +08:00

### 新增

- `stock_report.py`：新增 `--csv-input` 批量模式，与原有 `--stock-code` 单股票模式二选一；
  - 使用 `ThreadPoolExecutor` 多线程生成 HTML，新增 `--workers`，默认 4；
  - 读取 CSV 的 `代码 / 股票代码 / 证券代码 / code` 列，支持 `600519`、`sh600519`、`600519.SH`；
  - 批量报告写入 `--out-dir`（默认 `html-report/`），文件名带股票代码，避免同名公司互相覆盖；
  - 在原 CSV 末尾新增 `综合评分`、`HTML报告链接` 两列；
  - `综合评分` 只写 HTML 综合评分区的最终结论（如 `可买`）；
  - `HTML报告链接` 写绝对 `file:///...` 链接；
  - 保留原 CSV 的列顺序、UTF-8 BOM、CRLF 换行和文件权限；重复运行更新已有结果列；
  - 单只股票失败不中断批量，失败行写 `生成失败`，最终退出码为 1。
- `screen/batch.py`：CSV 读取/原子回写、结果列、`ReportResult`、`file:///` 链接。
- `screen/summary.py`：从生成的 HTML「四、综合评分」区提取 Q 分、V 分和最终结论。
- `tests/test_smoke.py`：新增 HTML 结论提取、CSV 往返、批量成功与单只失败继续等测试。

### 修改

- `config.py`：`VERSION` 由 `0.6.3` 升至 `0.7.0`。
- `METHODOLOGY.md`：版本号同步为 `0.7.0`。
- `README.md`：新增 CSV 批量模式说明、目录结构说明。
- `stock_report.py`：抽取单股票生成逻辑为 `_generate_report`，单股票输出格式和行为保持不变；
  `_write_atomic` 临时文件名增加 UUID，避免多线程同名冲突。

### 影响

- 单股票用法、HTML 内容、文件名规则不变。
- 批量模式会用 CSV 中的代码覆盖对应行的 `综合评分` 和 `HTML报告链接`；原有业务列不修改。
- 批量模式暂不支持 `--bundle` 和 `--name`，会直接报错退出。

---

## 2026-11-08 21:35 +08:00

### 修改

- `screen/render.py`：删除页面顶部“生成 YYYY-MM-DD HH:MM”字段，只保留行情日期和最新报告期。
- `screen/render.py`：删除不再使用的 `datetime` 导入。
- `tests/test_smoke.py`：新增断言，确保报告不再出现“· 生成”字段。
- `config.py`：`VERSION` 由 `0.6.2` 升至 `0.6.3`。
- `METHODOLOGY.md`：版本号同步。

### 影响

- 报告顶部不再显示生成时间；生成时间只保留在文件名中。
- 不改变报告内容、评分、结论或文件名规则。

---

## 2026-11-08 21:33 +08:00

### 修复

- `stock_report.py`：生成文件名由 `YYYYMMDD` 改为 `YYYYMMDD-HHMMSS`，精确到秒：
  - 旧：`利尔化学-企业质量初筛-20261108.html`
  - 新：`利尔化学-企业质量初筛-20261108-213008.html`
- `screen/render.py`：撤回上一版对 HTML `<title>` 和页面生成时间的秒级改动，恢复为原来的标题。
- `tests/test_smoke.py`：标题断言改为文件名“分秒”格式断言。
- `README.md`：更新输出文件示例，并说明文件名包含生成日期和时分秒。
- `config.py`：`VERSION` 由 `0.6.1` 升至 `0.6.2`。
- `METHODOLOGY.md`：版本号同步。

### 影响

- 同一只股票同一天多次生成报告不会互相覆盖，文件名会保留每次生成的分秒。
- HTML 浏览器标签标题不再附加时间，时间只体现在文件名中。
- 不改变报告内容、评分、结论或取数逻辑。

---

## 2026-11-08 21:29 +08:00

### 修改

- `screen/render.py`：
  - HTML `<title>` 增加生成时间，精确到秒；
  - 页面顶部“生成”时间同步改为 `YYYY-MM-DD HH:MM:SS`；
  - `<title>` 和页面顶部使用同一个 `generated_at`，避免时间不一致。
- `tests/test_smoke.py`：新增标题和页面生成时间的“分秒”格式断言。
- `config.py`：`VERSION` 由 `0.6.0` 升至 `0.6.1`。
- `METHODOLOGY.md`：版本号同步。

### 影响

- 浏览器标签页标题现在显示到秒，例如：
  `贵州茅台（sh600519）企业质量初筛 · 2026-11-08 21:29:43`
- 页面顶部“生成”时间同样显示到秒。
- 不改变文件名、评分、结论或数据口径。

---

## 2026-11-08 21:26 +08:00

### 修改

- `config.py`：
  - `VERSION` 由 `0.5.1` 升至 `0.6.0`；
  - 新增 `QUALITY_HARD_FLOOR = 45.0`；
  - 新增 `BUY_MIN_V`：高质量 65、中等偏上 70、一般 75、偏弱 80；
  - 新增 `BUY_KEYS` 标识所有买入类结论。
- `screen/score.py`：重写 `_decision()` 为“质量调整后的估值门槛”：
  - Q≥75：V≥65 推荐买入，50~65 等价格，35~50 偏贵，<35 太贵；
  - Q65~75：V≥80 推荐，70~80 可买，50~70 观察，<50 回避；
  - Q55~65：V≥75 小仓买入，50~75 观察，<50 回避；
  - Q45~55：V≥80 小仓试错，65~80 观察，<65 回避；
  - Q<45：无论 V 多高都回避；
  - 数据不完整时，买入类结论降为“观察，等待数据完整”。
- `templates/report.html`：新增 `buy_ok`、`buy_small`、`buy_trial` 徽标样式。
- `screen/render.py`：
  - Q 卡片增加“风险检查 X/10 已知”；
  - 质量分构成标题改为“（风险检查不计入 Q）”，并展示命中/数据不足数量；
  - 决策规则文字改为质量调整矩阵。
- `tests/test_smoke.py`：新增高质量、中等偏上、一般、偏弱、Q<45 的边界测试；买入阻断改为降级到“观察”。
- `README.md`、`METHODOLOGY.md`：更新质量调整矩阵、硬性门槛和数据完整度规则。

### 影响

- 取消原来的 `Q<55 → 全部回避`。
- 质量一般但估值明显便宜的公司可以进入“小仓买入/小仓试错”，不再被一刀切。
- Q<45 为硬性禁止买入线，V 再高也不改变。
- 买入类结论仍受数据完整度约束；机构覆盖不足、Q 覆盖不足或关键风险缺失时降为观察。
- 002258：Q50.2、V80.1，质量偏弱但估值明显低估；因机构覆盖仅 1 家，结论降为“观察，等待数据完整”，不再直接“回避”。
- 测试数量由 25 个增至 27 个。
- 不新增取数接口、不新增依赖，输出仍是单个 HTML。

---

## 2026-11-08 21:14 +08:00

### 修复

- `screen/compute.py`：把预测覆盖与评级覆盖拆开：
  - `coverage` 只表示盈利预测覆盖机构数；
  - 新增 `rating_coverage` 表示评级接口覆盖机构数；
  - 仅有评级记录、没有盈利预测时，`coverage=0`，不再显示“机构覆盖 1 家”造成误解；
  - 预测行没有机构数字段时，才用评级接口机构数兜底。
- `screen/render.py`：新增“取数缺口”提示，直接展示 `data_consensus` 等接口失败原因；没有预测但存在评级时，显示“暂无盈利预测；评级记录 X 条、覆盖机构 Y 家”。
- `stock_report.py`：把 `raw["errors"]` 写入报告数据，使 HTML 内也能看到取数缺口。
- `config.py`：`VERSION` 由 `0.5.0` 升至 `0.5.1`。
- `METHODOLOGY.md`：版本号同步。

### 影响

- `data_consensus` 超时导致没有预测时，V 仍为“—”，但报告会明确写出“取数缺口：data_consensus 请求超时”，不再只显示笼统的“无机构覆盖”。
- 仅有评级、没有盈利预测的股票，不再把评级机构数当成预测覆盖数。
- 002258 重跑后 `data_consensus` 正常返回，V=80.1，Q=50.2，结论“回避（质量分低于 55）”。

---

## 2026-11-08 21:09 +08:00

### 修改

- `config.py`：`VERSION` 由 `0.4.0` 升至 `0.5.0`。
- `config.py`：新增可买数据前置条件：
  - `BUY_MIN_INSTITUTION_COVERAGE = 3`；
  - `BUY_MIN_QUALITY_COVERAGE = 80.0`；
  - `BUY_CRITICAL_CHECKS = ("cfo_ni", "leverage", "goodwill", "nonrecurring", "liquidity")`。
- `screen/score.py`：
  - 删除 `_confidence()` 和 0~100 置信度；
  - 新增 `_data_quality()`，记录风险检查已知/未知项、关键风险缺失、机构覆盖、Q 数据覆盖和可买阻断原因；
  - 重写 `_decision()`：按 Q/V 分档矩阵逐条判断，数据完整度只影响“可买”；
  - Q 分等级改为 6 档：优秀、良好、中等偏上、中等、偏弱、差；
  - V 分等级改为 5 档：明显低估、低估、合理、偏高、明显高估。
- `screen/render.py`：
  - 删除“置信度”卡片；
  - 第二节风险检查改为显示“已知 X / 10”；
  - 第四节新增数据完整度说明：风险检查已知数、机构覆盖、Q 覆盖率、可买前置条件；
  - 决策规则文字改为新的 Q/V 矩阵。
- `stock_report.py`：命令行摘要删除置信度，改为显示风险检查和机构覆盖。
- `screen/validate.py`：删除置信度校验，新增 `data_quality` 校验。
- `tests/test_smoke.py`：删除置信度断言；新增数据完整度、可买阻断、Q/V 分档边界、缺失/致命项测试。
- `README.md`、`METHODOLOGY.md`：更新 Q/V 分档、数据完整度、可买条件和结论矩阵。

### 影响

- 报告不再显示置信度，也不会因置信度 <60 把明确结论改成“数据不足”。
- “可买”新增数据门槛：机构覆盖 ≥3 家、Q 覆盖 ≥80%、关键风险检查无缺失；不满足时降为“好公司，等价格”并写明原因。
- Q/V 等级标签更细，结论矩阵的边界由 75/55、65/45 调整为 75/65/55/50/35。
- 原有“回避/太贵”等负面结论不再被数据完整度覆盖。
- 测试数量由 19 个增至 25 个。
- 不新增取数接口、不新增依赖，输出仍是单个 HTML。

---

## 2026-11-08 20:40 +08:00

### 修改

- `config.py`：`VERSION` 由 `0.3.0` 升至 `0.4.0`。
- `config.py`：删除旧的 V 权重 `multiples / fcf_yield / dcf`，新增：
  - `VALUATION_WEIGHTS = {"target_upside": 40, "forecast_pe": 20, "profit_growth": 40}`；
  - `VALUATION_RANGES`：目标价空间 -30%~30%、预测 PE 变化 -20%~20%、净利增速 -15%~25%。
- `screen/score.py`：重写 `_valuation_score()`，V 分改为机构口径：
  - 机构目标价空间 40；
  - 预测 PE 相对当前 PE 20；
  - 预期未来净利增速 40。
  - 历史分位、FCF 收益率、DCF 折价不再进入 V。
  - 新增 `_forecast_metrics()`，统一提取目标价空间、预测 PE 变化和未来 1~3 年净利增速；
  - 未来增速优先用 `net_profit_yoy` 均值，缺失时用复合增速兜底；最近年报亏损时不计算增速。
- `screen/score.py`：V 必须同时具备至少一个机构估值指标和一个净利增速指标才计算；无机构覆盖时 V 为空，Q 分仍正常计算。
- `screen/score.py`：`_confidence()` 改为按机构预测字段扣分，不再因历史估值样本或 DCF 不适用扣分。
- `screen/render.py`：
  - “历史估值分位”和“近 15 个季度估值走势（周频）”合并为“PE/PB/PS 历史分位及走势图”，删除后者标题；
  - “机构未来盈利预期”改为“机构对企业未来盈利的预期”；
  - “预期差提示”移动到机构预期块内部，位于目标价/评级之后、DCF 之前；
  - “本报告的估值”改为“对企业进行 DCF 估值”；
  - “现金扣除与底线估值（参考）”改为“用现金扣除与底线估值方式对企业进行估值”；
  - 第四节“估值分构成”改为“估值分构成（机构口径）”，展示新的三项 V 分构成；
  - 页脚方法说明、置信度说明同步更新。
- `tests/test_smoke.py`：更新标题断言，新增 V 分加权、目标价缺失归一、无机构覆盖、亏损基数、预期差位置等测试。
- `README.md`、`METHODOLOGY.md`：更新 V 分公式、机构预期口径、置信度和展示边界。

### 影响

- V 分结果会变化，并可能改变“可买 / 等价格 / 太贵”的结论；决策阈值暂时保持 65 / 45 不变，需用样本继续校准。
- 无机构覆盖的股票 V 为空，报告仍展示 Q 分，但结论为“数据不足，不下结论”。
- 历史分位、FCF、DCF、现金扣除与底线估值仍展示，但都不进入 V。
- 测试数量由 12 个增至 19 个。
- 不新增取数接口、不新增依赖，输出仍是单个 HTML。

---

## 2026-11-08 19:59 +08:00

### 新增

- `config.py`：新增 `CASH_ANCHOR_YEARS = (3, 5, 10, 15, 20)`，用于“现金扣除与底线估值”的情景年限。
- `screen/compute.py`：新增 `_cash_valuation()`，在 `build_report_data()` 中写入 `cash_valuation`。
  - 现金底仓直接用最新报告期货币资金，**不扣有息负债**；有息负债只展示。
  - 净利润总额使用最近年报的 `net_profit_total`，不做 5 年中位数；该值是
    `营业收入 × NetProfitRatio ÷ 100` 的近似值。
  - 输出扣现金市值、货币资金/市值、扣现金 PE、盈利收益率，以及 3/5/10/15/20 年五档底线价值、
    每股底线和安全边际。
  - 金融股（银行/保险/证券）返回“金融股不适用”；净利润总额缺失或为负时不计算底线。
- `screen/render.py`：第三节 DCF 之后新增“现金扣除与底线估值（参考）”展示块，包含基础指标表和
  五档年限表；页脚口径说明同步补充。
- `tests/test_smoke.py`：新增 4 个 `CashValuationTest` 测试，并补充报告 HTML 与 compute 契约断言。
- `README.md`、`METHODOLOGY.md`：补充现金扣除块的口径、边界与“不进入 V 分”的说明。

### 修改

- `config.py`：`VERSION` 由 `0.2.0` 升至 `0.3.0`。
- 测试数量由 8 个增至 12 个。

### 影响

- 报告第三节新增一个展示块，不改变 Q/V、10 条风险检查、决策矩阵、置信度和跟踪清单。
- 不新增取数接口、不新增依赖、不生成 JSON/Markdown，输出仍是单个 HTML。
- 现金扣除块采用用户指定口径：不扣有息负债、净利润总额为近似值、年限 N 为情景假设；
  金融股不适用。

---

## 2026-11-08 14:45 +08:00

### 修复

- `screen/render.py`：利润率图的 x 轴原来只显示 8 个刻度（隔一个季度），容易被误读为季度数据不足；改为显示全部 15 个季度标签，并加大数据点。
- `screen/render.py`：利润率图下方新增“覆盖 23Q1–26Q3，共 15 个季度”的明确说明；不足 15 个季度时注明实际数量。
- `tests/test_smoke.py`：新增 15 个季度标签全部输出的断言。

### 影响

- 仅影响利润率图的可读性和说明文字，不改变数据窗口、计算公式、Q/V 或估值分位口径。

---

## 2026-11-08 14:40 +08:00

### 新增

- `screen/compute.py`：新增 `_margin_trend()`，用 `OperatingRevenue_Q`、`OperatingCost_Q`、`NPParentCompanyOwners_Q` 计算最近 15 个报告期的单季毛利率和归母净利率；`build_financials()` 新增 `margin_trend`。
- `screen/compute.py`：`_valuation()` 新增 `chart`，复用现有 `RPT_VALUEANALYSIS_DET` 周频序列，截取最近 15 个报告季度起点之后的数据，生成 PE/PB/PS 曲线点、最新点和 PE 负值区间。
- `screen/render.py`：新增通用 SVG 折线图 `_line_chart()`、利润率图 `_margin_chart()`、估值三面板 `_valuation_charts()`；第一节插入近 15 季度利润率曲线，第三节插入 PE/PB/PS 三个独立面板。
- `templates/report.html`：新增图表、图例、最新点、PE 负值灰带相关 CSS。

### 修改

- `config.py`：`VERSION` 由 `0.1.0` 升至 `0.2.0`；新增 `TREND_QUARTERS = 15`。
- `tests/test_smoke.py`：增加图表存在性、SVG 数量、最新点、PE 为负断线等断言。
- `README.md`、`METHODOLOGY.md`：补充 15 季度利润率、15 季度估值曲线、周频口径、PE 为负处理和“分位仍按全历史”的说明。

### 影响

- 报告新增 4 张 SVG 图：1 张利润率双曲线、3 张估值独立面板；不新增取数接口、不新增依赖、不生成额外文件。
- Q/V、风险检查、决策矩阵、估值分位口径均未改变；图表只作展示。
- 季度利润率取单季口径，未年化；PE/PB/PS 曲线只覆盖最近 15 个报告季度，分位仍按全部可用历史。
- 老 bundle 缺少足够季度或估值数据时，图显示可用点数或“暂无数据”，不会导致报告生成失败。

---

## 2026-11-07 10:25 +08:00

### 修改

- `config.py`：默认输出目录由 `~/企业质量初筛` 改为项目目录下的 `html-report/`，使用 `Path(__file__).resolve().parent` 解析，避免受运行目录影响。
- `stock_report.py`：更新用法说明，默认输出到项目内 `html-report/`。
- `README.md`：同步默认输出路径和指定目录示例。
- `.gitignore`：新增 `/html-report/`，排除本地生成的 HTML 报告目录。
- `tests/test_smoke.py`：新增默认输出目录断言，确认未传 `--out-dir` 时指向项目内 `html-report/`。

### 影响

- 不指定 `--out-dir` 时，报告写入本项目 `html-report/`，不再写入用户主目录。
- `--out-dir` 仍可覆盖默认目录。
- 生成的 HTML 不进入 Git，不影响评分和数据取数逻辑。

---

## 2026-11-07 09:58 +08:00

### 新增

- 新增 `.gitignore`：排除 Python 缓存、虚拟环境、测试/类型检查缓存、构建产物、Node 依赖、操作系统与编辑器文件、生成的 HTML 报告、示例报告、输出目录、日志和本地原始数据。
- 新增 `CHANGELOG.md`（本文件）：建立强制修改记录规范。

### 修改

- 修改 `README.md`：增加“修改记录”章节，指向本文件，并要求以后每次修改同步登记。
- 调整 `.gitignore` 中示例报告的规则：`examples/` 属于本地生成物，不再上传；`templates/report.html` 作为模板保留。

### 影响

- 不影响程序运行和报告计算结果。
- 从本次开始，后续所有修改都必须先更新本文件，再提交代码。
