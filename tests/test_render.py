# -*- coding: utf-8 -*-
"""HTML 渲染：五节结构、转义、空态、图表。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import support
from screen.render import (_bar, _line_chart, _margin_chart, _score_class, n,
                           _section_business, _section_risks,
                           _section_score, _section_tracking,
                           _section_valuation, _val_band, _valuation_charts,
                           _valuation_position, _valuation_verdict, esc,
                           render_html)


class EscapeTest(unittest.TestCase):
    def test_esc_handles_quotes_and_tags(self):
        self.assertEqual(esc('<b>"x"&\'y\'</b>'),
                         "&lt;b&gt;&quot;x&quot;&amp;&#x27;y&#x27;&lt;/b&gt;")
        self.assertEqual(esc(None), "")

    def test_company_name_is_escaped(self):
        data = support.scored_data()
        data["meta"]["name"] = "<script>alert(1)</script>"
        html = render_html(data)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_business_text_cannot_inject_markup(self):
        data = support.scored_data()
        data["meta"]["business"] = "<iframe src=//evil></iframe>"
        html = render_html(data)
        self.assertNotIn("<iframe", html)
        self.assertIn("&lt;iframe", html)


class RenderStructureTest(unittest.TestCase):
    def setUp(self):
        self.html = render_html(support.scored_data())

    def test_has_five_sections_in_order(self):
        headings = ["一、生意本身", "二、经营质量与风险", "三、企业估值与机构预期",
                    "四、综合评分", "五、后续跟踪"]
        positions = [self.html.index(h) for h in headings]
        self.assertEqual(positions, sorted(positions))

    def test_title_and_hero(self):
        """头部显示的是「估值口径日收盘价」，不是实时价。"""
        data = support.scored_data()
        meta = data["meta"]
        self.assertIn("<title>贵州茅台（sh600519）企业质量初筛</title>", self.html)
        self.assertIn('class="hero"', self.html)
        self.assertIn("食品饮料", self.html)
        self.assertIn(f"¥ {n(meta['price'])}", self.html)
        self.assertIn(f"市值 {n(meta['market_cap_yi'])} 亿元", self.html)
        self.assertIn(f"估值口径 {meta['price_date']} 收盘", self.html)
        self.assertTrue(str(meta["price_basis"]).endswith("收盘"))

    def test_footer_carries_method_sources_limits_version(self):
        for token in ("方法说明", "数据来源", "口径与边界", "不构成投资建议", config.VERSION):
            self.assertIn(token, self.html)
        self.assertIn("资本回报 30", self.html)
        self.assertIn("RPT_VALUEANALYSIS_DET", self.html)

    def test_footer_no_longer_mentions_dcf(self):
        self.assertNotIn("DCF", self.html)

    def test_no_external_resources_or_js(self):
        self.assertNotIn("<script", self.html)
        self.assertNotIn("<link", self.html)
        self.assertNotIn("http://", self.html)
        self.assertNotIn("https://", self.html)

    def test_svg_count_and_charts(self):
        self.assertEqual(self.html.count("<svg"), 4)      # 季度利润率 1 + 估值 3
        self.assertIn('class="latest"', self.html)
        self.assertIn(f"近 {config.TREND_YEARS} 年季度毛利率/净利率趋势", self.html)
        self.assertIn("PE(TTM)", self.html)
        self.assertIn("PB(MRQ)", self.html)
        self.assertIn("PS(TTM)", self.html)

    def test_quality_and_valuation_tables(self):
        self.assertIn("质量分构成（五个维度，第二节不参与打分）", self.html)
        self.assertIn("<td>资本回报</td>", self.html)
        self.assertIn("估值分构成（机构口径）", self.html)
        self.assertIn("机构目标价空间", self.html)
        self.assertIn("预测 PE 相对当前 PE", self.html)
        self.assertIn("预期未来净利增速", self.html)

    def test_risk_table_groups_and_folds_clear_rows(self):
        data = support.scored_data()
        section = _section_risks(data)
        self.assertIn(f"{config.RISK_CHECK_COUNT} 项高信号检查", section)
        self.assertEqual(section.count('class="group-row"'), len(config.RISK_GROUPS))
        groups_with_clear = {
            c["group"] for c in data["risks"]["checks"] if c["status"] == "clear"
        }
        self.assertEqual(section.count('class="fold-row"'), len(groups_with_clear))
        for c in data["risks"]["checks"]:          # 14 项都要出现在表里
            self.assertIn(c["name"], section)
        self.assertIn('class="status clear"', section)

    def test_hit_and_watch_rows_render_with_status_class(self):
        data = support.scored_data()
        checks = data["risks"]["checks"]
        checks[0]["status"] = "hit"
        checks[0]["detail"] = "测试用命中证据"
        checks[1]["status"] = "watch"
        checks[1]["detail"] = "测试用提示证据"
        section = _section_risks(data)
        self.assertIn('class="status hit"', section)
        self.assertIn('class="status watch"', section)
        self.assertIn("有命中", section)
        self.assertIn("测试用命中证据", section)

    def test_na_rows_show_not_applicable(self):
        data = support.scored_data()
        data["risks"]["checks"][0]["status"] = "na"
        data["risks"]["checks"][0]["detail"] = "金融股口径不适用"
        section = _section_risks(data)
        self.assertIn('class="status na"', section)
        self.assertIn("不适用 1 项", section)
        self.assertIn("金融股口径不适用", section)

    def test_hit_items_are_not_folded(self):
        data = support.scored_data()
        hit = data["risks"]["checks"][0]
        hit["status"] = "hit"
        hit["detail"] = "连续两年增速差 >15pct"
        section = _section_risks(data)
        row = section[section.find(hit["name"]):]
        self.assertIn("命中", row[:400])
        self.assertIn("连续两年增速差 &gt;15pct", row[:400])


class SectionBusinessTest(unittest.TestCase):
    def test_empty_mainop_falls_back(self):
        data = support.scored_data()
        data["mainop"] = {"available": False, "period": "", "products": []}
        section = _section_business(data)
        self.assertIn("产品/业务分部：暂无披露。", section)

    def test_moat_reasons_are_listed(self):
        section = _section_business(support.scored_data())
        self.assertIn("盈利结构（三条证据）", section)
        self.assertIn("资本回报", section)
        self.assertIn("三条证据", section)
        self.assertNotIn("量化评分", section)      # 0.8.0 起不再显示 0~100 分
        self.assertNotIn("护城河", section)        # 2.13.0 起「护城河」一词退出报告

    def test_business_section_has_moat_and_solvency_lines(self):
        """2.13.0 生意属性三段：无标注提示 + 存续安全 + 盈利结构 + 澄清文案。"""
        section = _section_business(support.scored_data())
        self.assertIn("垄断性标注：无标注", section)
        self.assertIn("存续安全</div><div><b>坚固</b>", section)
        self.assertIn("盈利结构弱 ≠ 没有垄断", section)
        self.assertIn("不从财务数据反推垄断性", section)

    def test_annotated_stock_shows_moat_with_sources(self):
        """有标注的公司：显示类型/依据/控股股东/来源与核实日期。"""
        data = support.scored_data()
        data["resource_moat"] = {
            "annotated": True, "moat_type": "独家资源",
            "evidence": "金堆城钼矿资源量占全国 25% 以上",
            "controller": "陕西有色金属控股集团",
            "sources": ["https://example.com/a.pdf"],
            "verified": "2026-11-13", "stale": False,
        }
        section = _section_business(data)
        self.assertIn("垄断性标注", section)
        self.assertIn("独家资源", section)
        self.assertIn("陕西有色金属控股集团", section)
        self.assertIn("https://example.com/a.pdf", section)
        self.assertIn("核实 2026-11-13", section)
        self.assertNotIn("待复核", section)

    def test_stale_annotation_shows_review_badge(self):
        data = support.scored_data()
        data["resource_moat"] = {"annotated": True, "moat_type": "配额牌照",
                                 "evidence": "x", "controller": "y",
                                 "sources": [], "verified": "2024-01-01", "stale": True}
        section = _section_business(data)
        self.assertIn("待复核", section)

    def test_annual_table_limited_to_five_rows(self):
        section = _section_business(support.scored_data())
        self.assertIn("五年经营轨迹", section)
        self.assertEqual(section.count("<td>2025</td>"), 1)


class SectionValuationTest(unittest.TestCase):
    def test_data_gaps_box(self):
        data = support.scored_data()
        data["data_gaps"] = [{"tool": "data_rating", "error": "服务限频"}]
        section = _section_valuation(data)
        self.assertIn("取数缺口", section)
        self.assertIn("服务限频", section)
        self.assertLess(section.index("取数缺口"), section.index("PE/PB/PS 历史分位及走势图"))

    def test_forecast_cards_and_flags(self):
        data = support.scored_data()
        data["flags"] = ["测试预期差提示"]
        section = _section_valuation(data)
        self.assertIn("机构目标价", section)
        self.assertIn("评级分布", section)
        self.assertIn("测试预期差提示", section)
        self.assertIn("（不是机构数）", section)

    def test_dcf_section_removed(self):
        """DCF 已下线：即使传入残留的 dcf 数据也不渲染。"""
        data = support.scored_data()
        data["dcf"] = {"applicable": True, "fair_value": 99.9, "margin_pct": 12.3}
        section = _section_valuation(data)
        self.assertNotIn("DCF", section)
        self.assertNotIn("99.9", section)
        self.assertNotIn("FCF 收益率", section)

    def test_cash_block_empty_state(self):
        data = support.scored_data()
        data["cash_valuation"] = {"applicable": False, "reason": "金融股不适用", "anchors": []}
        section = _section_valuation(data)
        self.assertIn("不适用：金融股不适用", section)
        self.assertEqual(section.count("<td colspan=\"4\">"), 1)

    def test_anchor_shows_market_cap_multiple(self):
        """安全边际 −488% 读不懂：同格补「市值 N 倍」（P2-6）。"""
        data = support.scored_data()
        section = _section_valuation(data)
        anchor = data["cash_valuation"]["anchors"][0]
        self.assertIsNotNone(anchor["cap_times"])
        self.assertIn(f"（市值 {anchor['cap_times']:.1f} 倍）", section)
        self.assertIn("分母是底线，所以会小于 −100%", section)

    def test_valuation_charts_empty_state(self):
        self.assertIn("暂无估值序列数据", _valuation_charts({}))

    def test_no_series_never_prints_empty_asof(self):
        """没有估值序列时不能印「全篇估值口径统一为 — 收盘」（P2-1）。"""
        data = support.scored_data()
        data["valuation"] = {"metrics": {}, "sample": {}, "available": False,
                             "chart": {"points": [], "latest": {}}}
        data["meta"]["price_date"] = ""
        data["meta"]["price_basis"] = "上一交易日收盘"
        section = _section_valuation(data)
        self.assertNotIn("— 收盘", section)
        self.assertNotIn(" 收盘</b>", section)
        self.assertIn("无估值序列（无口径日）", section)
        self.assertIn("上一交易日收盘", section)

    def test_section_text_says_ten_year_window(self):
        section = _section_valuation(support.scored_data())
        self.assertIn(f"下图为近 {config.VALUATION_YEARS} 年周频走势", section)
        self.assertIn(f"可用历史不足 {config.VALUATION_YEARS} 年时按全部可用历史", section)
        self.assertIn("PE 为负时断线", section)
        self.assertNotIn("近 15 个季度周频走势", section)

    def test_percentile_text_uses_actual_start_year(self):
        """分位文案要用序列真实起始年份，不能写死 2018（新股没有 2018 的数据）。"""
        data = support.scored_data()
        data["valuation"]["sample"] = {"start": "2018-08-31", "end": "2026-11-07",
                                       "points": 428}
        section = _section_valuation(data)
        self.assertIn("上表为 2018 年以来周频分位", section)
        self.assertNotIn("全部可用历史（周频）分位", section)

    def test_percentile_text_falls_back_when_no_sample(self):
        data = support.scored_data()
        data["valuation"]["sample"] = {}
        section = _section_valuation(data)
        self.assertIn("全部可用历史（周频）分位", section)

    def test_percentile_table_header_says_close(self):
        """表头写“最新收盘”，并注明全篇估值口径日，避免与实时价混淆。"""
        data = support.scored_data()
        section = _section_valuation(data)
        self.assertIn("<th>最新收盘</th>", section)
        self.assertIn("全篇估值口径统一为", section)
        self.assertIn(f"{data['meta']['price_date']} 收盘", section)

    def test_chart_note_reports_window_or_short_history(self):
        points = [{"date": f"{2020 + i}-06-30", "label": f"{2020 + i}-06",
                   "pe": 20.0 + i, "pb": 3.0, "ps": 2.0, "pe_negative": False}
                  for i in range(11)]
        full = _valuation_charts({"points": points, "count": 11, "start": "2020-06-30",
                                  "end": "2030-06-30", "years": 10,
                                  "span_years": 10.0, "limited": False, "latest": {}})
        self.assertIn("近 10 年周频", full)
        self.assertIn("11 个周度点", full)
        short = _valuation_charts({"points": points, "count": 11, "start": "2020-06-30",
                                   "end": "2025-06-30", "years": 10,
                                   "span_years": 5.0, "limited": True, "latest": {}})
        self.assertIn("可用历史约 5.0 年，已全部展示", short)

    def test_chart_note_handles_under_one_year(self):
        points = [{"date": "2024-01-05", "label": "2024-01", "pe": 20.0,
                   "pb": 3.0, "ps": 2.0, "pe_negative": False}]
        charts = _valuation_charts({"points": points, "count": 1, "start": "2024-01-05",
                                    "end": "2024-01-05", "years": 10,
                                    "span_years": 0.2, "limited": True, "latest": {}})
        self.assertIn("可用历史不足 1 年，已全部展示", charts)

    def test_chart_aria_label_uses_years(self):
        points = [{"date": "2024-01-05", "label": "2024-01", "pe": 20.0,
                   "pb": 3.0, "ps": 2.0, "pe_negative": False}]
        charts = _valuation_charts({"points": points, "count": 1, "start": "2024-01-05",
                                    "end": "2024-01-05", "years": 10,
                                    "span_years": 0.0, "limited": False, "latest": {}})
        self.assertIn(f"近 {config.VALUATION_YEARS} 年 PE(TTM) 周频走势", charts)


class ValuationVerdictTest(unittest.TestCase):
    """第三节「估值位置」那段话：七档边界、中位数定档、跨度分歧。"""

    def _metrics(self, pe, pb, ps):
        return {"pe": {"percentile": pe}, "pb": {"percentile": pb}, "ps": {"percentile": ps}}

    def test_band_boundaries_do_not_overlap(self):
        """切点两侧不能串档：这是七档方案唯一的硬规则。"""
        cases = [(0.0, "历史底部"), (9.9, "历史底部"), (10.0, "下三分之一"),
                 (29.9, "下三分之一"), (30.0, "中偏低"), (44.9, "中偏低"),
                 (45.0, "正中"), (54.9, "正中"), (55.0, "中偏高"), (69.9, "中偏高"),
                 (70.0, "上三分之一"), (89.9, "上三分之一"), (90.0, "历史顶部"),
                 (100.0, "历史顶部")]
        for value, band in cases:
            with self.subTest(value=value):
                self.assertEqual(_val_band(value)[0], band)

    def test_seven_bands_and_monotonic_verdicts(self):
        self.assertEqual(len(config.VAL_BANDS), 7)
        self.assertEqual([v for *_, v in config.VAL_BANDS],
                         ["明显偏便宜", "偏便宜", "略偏便宜", "中性",
                          "略偏贵", "偏贵", "明显偏贵"])

    def test_bands_tile_the_whole_range(self):
        """七档必须首尾相接、不留缝不重叠，否则某个分位会找不到档（落到兜底）。"""
        self.assertEqual(config.VAL_BANDS[0][0], 0.0)
        self.assertGreaterEqual(config.VAL_BANDS[-1][1], 100.0)
        for prev, cur in zip(config.VAL_BANDS, config.VAL_BANDS[1:]):
            with self.subTest(cut=cur[0]):
                self.assertEqual(prev[1], cur[0])

    def test_band_clamps_out_of_range_ends(self):
        """越界值要落在最近的一端，不能两头都掉进「历史顶部」。"""
        self.assertEqual(_val_band(-5.0)[0], "历史底部")
        self.assertEqual(_val_band(120.0)[0], "历史顶部")

    def test_all_in_bottom_third(self):
        text = _valuation_verdict(self._metrics(18.2, 5.8, 17.1))
        self.assertIn("位置接近（跨度 12pp）", text)
        self.assertIn("中位落在下三分之一", text)
        self.assertIn("估值偏便宜", text)

    def test_median_not_mean(self):
        """76 / 92 / 83：平均值会顶到「明显偏贵」，中位数仍是 83 的「偏贵」。"""
        text = _valuation_verdict(self._metrics(76.4, 92.0, 82.7))
        self.assertIn("中位落在上三分之一", text)
        self.assertIn("估值偏贵", text)
        self.assertNotIn("明显偏贵", text)

    def test_close_positions_do_not_mention_divergence(self):
        text = _valuation_verdict(self._metrics(25.8, 43.9, 50.2))    # 跨度 24.4pp
        self.assertIn("位置接近", text)
        self.assertNotIn("拉得比较开", text)
        self.assertIn("估值略偏便宜", text)

    def test_wide_spread_names_both_ends(self):
        text = _valuation_verdict(self._metrics(39.1, 19.7, 49.4))    # 跨度 29.7pp
        self.assertIn("拉得比较开", text)
        self.assertIn("PB 20% 在下三分之一", text)
        self.assertIn("PS 49% 在正中", text)
        self.assertIn("净资产端比收入端便宜", text)
        self.assertNotIn("明显比", text)                              # 未到强措辞门槛
        self.assertIn("估值略偏便宜", text)

    def test_very_wide_spread_uses_stronger_wording(self):
        text = _valuation_verdict(self._metrics(10.0, 50.0, 88.0))    # 跨度 78pp
        self.assertIn("利润端明显比收入端便宜", text)

    def test_two_metrics_says_two(self):
        text = _valuation_verdict({"pe": {"percentile": 20.0},
                                   "ps": {"percentile": 60.0}})
        self.assertIn("两个口径", text)
        self.assertNotIn("三个口径", text)

    def test_single_metric_has_no_verdict(self):
        self.assertEqual(_valuation_verdict({"pe": {"percentile": 20.0}}), "")
        self.assertEqual(_valuation_verdict({}), "")

    def test_missing_percentile_is_skipped(self):
        text = _valuation_verdict({"pe": {"percentile": None},
                                   "pb": {"percentile": 20.0},
                                   "ps": {"percentile": 70.0}})
        self.assertIn("两个口径", text)
        self.assertNotIn("PE", text)

    def test_out_of_range_percentile_is_skipped(self):
        """-5% / 120% 是上游数据错误，当缺失处理，不夹取成「历史底部」误导读者。"""
        text = _valuation_verdict({"pe": {"percentile": 120.0},
                                   "pb": {"percentile": 20.0},
                                   "ps": {"percentile": 30.0}})
        self.assertIn("两个口径", text)
        self.assertNotIn("PE", text)
        self.assertEqual(_valuation_position({"pe": {"percentile": -5.0}}), "")

    def test_verdict_never_leaves_a_gap(self):
        """0~100 步长 10 的全组合都要有结论，且结论词只能是那七个之一。"""
        allowed = [v for *_, v in config.VAL_BANDS]
        for pe in range(0, 101, 10):
            for pb in range(0, 101, 10):
                for ps in range(0, 101, 10):
                    text = _valuation_verdict(self._metrics(pe, pb, ps))
                    with self.subTest(pe=pe, pb=pb, ps=ps):
                        self.assertTrue(text)
                        self.assertTrue(any(w in text for w in allowed), text)

    def test_verdict_does_not_mutate_metrics(self):
        metrics = self._metrics(18.2, 5.8, 17.1)
        snapshot = {k: dict(v) for k, v in metrics.items()}
        _valuation_verdict(metrics)
        _valuation_position(metrics)
        self.assertEqual(metrics, snapshot)

    def test_position_line_shows_band_per_metric(self):
        pos = _valuation_position(self._metrics(18.2, 5.8, 17.1))
        self.assertIn("PE <b>18%</b>（下三分之一）", pos)
        self.assertIn("PB <b>6%</b>（历史底部）", pos)
        self.assertIn("PS <b>17%</b>（下三分之一）", pos)

    def test_section_prints_verdict_after_charts(self):
        section = _section_valuation(support.scored_data())
        self.assertIn("估值位置</b>：", section)
        self.assertLess(section.index("数据范围："), section.index("估值位置</b>："))

    def test_section_verdict_reuses_table_percentile(self):
        """那句话里的百分比必须与分位表同源，不能出现两套数字。"""
        data = support.scored_data()
        data["valuation"]["metrics"]["pe"]["percentile"] = 18.2
        data["valuation"]["metrics"]["pb"]["percentile"] = 5.8
        data["valuation"]["metrics"]["ps"]["percentile"] = 17.1
        # 夹具只有 10 个周样本，够不上档位门槛；这里把样本量抬到 1 年以上，
        # 让本节验证的是「同源」而不是「样本太少」。
        data["valuation"]["sample"]["points"] = config.VAL_MIN_SAMPLE_WEEKS * 5
        section = _section_valuation(data)
        self.assertIn("<td>18.2%</td>", section)
        self.assertIn("PE <b>18%</b>（下三分之一）", section)

    def test_section_skips_band_when_sample_too_short(self):
        """样本不足 1 年：只报分位，不给「历史顶部/底部」这种档位结论。"""
        data = support.scored_data()
        for key, value in (("pe", 91.0), ("pb", 93.0), ("ps", 95.0)):
            data["valuation"]["metrics"][key]["percentile"] = value
        data["valuation"]["sample"]["points"] = 10
        section = _section_valuation(data)
        self.assertIn("分位样本仅 10 周", section)
        self.assertNotIn("历史顶部", section)
        self.assertNotIn("中位落在", section)
        self.assertIn("PE <b>91%</b>", section)           # 数字照常展示
        self.assertNotIn("（历史顶部）", section)          # 但不再贴档名

    def test_section_omits_verdict_without_metrics(self):
        data = support.scored_data()
        for key in ("pe", "pb", "ps"):
            data["valuation"]["metrics"].pop(key, None)
        self.assertNotIn("估值位置", _section_valuation(data))


class SectionScoreTest(unittest.TestCase):
    def test_missing_valuation_shows_dash_and_reason(self):
        data = support.scored_data()
        data["valuation_score"] = {"score": None, "grade": "数据不足", "parts": [], "coverage": 0}
        data["decision"] = {"key": "unknown", "label": "数据不足，不下结论",
                            "reason": "质量分或估值分无法计算"}
        section = _section_score(data)
        self.assertIn("数据不足，不下结论", section)
        self.assertIn(">—</div>", section)

    def test_financial_stock_renders_not_applicable_states(self):
        """金融股：Q/V 为 None，表格要给空态，且不展示买入门槛矩阵。"""
        data = support.scored_data()
        data["quality"] = {"score": None, "grade": "金融股不适用", "groups": [],
                           "coverage": 0.0, "not_applicable": True}
        data["valuation_score"] = {"score": None, "grade": "金融股不适用", "parts": [],
                                   "coverage": 0.0, "not_applicable": True}
        data["decision"] = {"key": "unknown", "label": "金融股不适用，不做初筛",
                            "reason": "银行/保险/证券口径不可比"}
        section = _section_score(data)
        self.assertEqual(section.count('colspan="3"'), 2)      # 两张表各一行空态
        self.assertIn("不进入“质量调整后的买入门槛”矩阵", section)
        self.assertNotIn("可买还需满足", section)
        self.assertNotIn("Q 数据覆盖", section)

    def test_na_checks_are_excluded_from_known_denominator(self):
        """金融股 5 项不适用：分母要变成「适用项」，不能出现 11/14 这种把 na 当已知的假数。"""
        data = support.scored_data()
        for c in data["risks"]["checks"][:5]:
            c["status"] = "na"
        section = _section_score(data)
        na = 5
        unknown = sum(1 for c in data["risks"]["checks"] if c["status"] == "unknown")
        known = config.RISK_CHECK_COUNT - na - unknown
        self.assertIn(f"风险检查 {known}/{config.RISK_CHECK_COUNT - na} 已知", section)

    def test_consistency_line_reports_second_section_counts(self):
        """Q 卡片下要有一致性行：第二节命中/提示几项、有没有触发降级。"""
        data = support.scored_data()
        data["decision"] = {"key": "watch_price", "label": "好公司，等价格",
                            "reason": "质量通过，估值尚未到舒服区间"}
        for c in data["risks"]["checks"]:
            c["status"] = "clear"
        data["risks"]["checks"][1]["status"] = "watch"
        data["risks"]["gate_level"] = None
        section = _section_score(data)
        self.assertIn("第二节：命中 0 项、提示 1 项 → 未触发降级", section)

    def test_consistency_line_explains_threshold_met_but_not_buy(self):
        """命中/提示过了降级线、但结论本来就不是买入类 → 要说明“未再降级”。"""
        data = support.scored_data()
        data["decision"] = {"key": "avoid", "label": "回避", "reason": "质量偏弱且估值不便宜"}
        for c in data["risks"]["checks"]:
            c["status"] = "clear"
        for c in data["risks"]["checks"][:2]:
            c["status"] = "watch"
        data["risks"]["gate_level"] = "watch"
        section = _section_score(data)
        self.assertIn("已达降级线", section)
        self.assertIn("降为观察", section)

    def test_consistency_line_reports_degradation(self):
        data = support.scored_data()
        data["decision"] = {
            "key": "watch", "label": "观察，第二节有信号",
            "reason": "第二节命中 1 项（每股口径），按质量与估值本可「推荐买入」",
            "note": "第二节：命中 1 项（每股口径） → 买入类结论降级为观察",
        }
        section = _section_score(data)
        self.assertIn("买入类结论降级为观察", section)

    def test_grade_note_says_label_only(self):
        """分档只是标签，不能改变结论矩阵——报告里要说清楚。"""
        section = _section_score(support.scored_data())
        self.assertIn("只是标签", section)
        self.assertIn("不改变", section)

    def test_score_bar_classes(self):
        self.assertEqual(_score_class(70), "good")
        self.assertEqual(_score_class(50), "")
        self.assertEqual(_score_class(40), "bad")
        self.assertEqual(_score_class(None), "")
        self.assertIn("width:0.0%", _bar(None))
        self.assertIn("width:100.0%", _bar(150))
        self.assertIn("scorebar good", _bar(80, _score_class(80)))

    def test_tracking_rows(self):
        section = _section_tracking(support.scored_data())
        self.assertIn("ROIC−WACC", section)
        self.assertIn("PE 分位", section)
        self.assertNotIn("DCF", section)
        self.assertEqual(section.count("<tr>"), 8)          # 表头 + 7 行


class LineChartTest(unittest.TestCase):
    def test_empty_points(self):
        self.assertIn("暂无图表数据", _line_chart([], [{"key": "a", "color": "#000", "label": "A"}]))

    def test_all_values_missing(self):
        points = [{"label": "1", "a": None}]
        self.assertIn("暂无可绘制的数值",
                      _line_chart(points, [{"key": "a", "color": "#000", "label": "A"}]))

    def test_gap_breaks_the_line(self):
        points = [{"label": "1", "a": 1.0}, {"label": "2", "a": None}, {"label": "3", "a": 3.0}]
        svg = _line_chart(points, [{"key": "a", "color": "#123456", "label": "A"}])
        path = svg.split('<path d="', 1)[1].split('"', 1)[0]
        self.assertEqual(path.count("M"), 2)                # 中间断开，两条子路径
        self.assertIn('stroke="#123456"', svg)

    def test_bands_and_latest_marker(self):
        points = [{"label": f"Q{i}", "a": 10.0 + i} for i in range(4)]
        svg = _line_chart(points, [{"key": "a", "color": "#000", "label": "A"}],
                          bands=[(1, 2)], value_fmt=lambda v: f"{v:.1f}")
        self.assertIn('class="band"', svg)
        self.assertIn('class="latest"', svg)
        self.assertIn("13.0", svg)

    def test_margin_chart_empty(self):
        html = _margin_chart({})
        self.assertIn("暂无季度利润表数据", html)
        self.assertIn(f"近 {config.TREND_YEARS} 年季度毛利率/净利率趋势", html)

    def test_margin_chart_does_not_repeat_verdict_headline(self):
        """结论已写在 badge 上，正文不再重复“① 毛利率环比改善判定：…”这一句。"""
        improve = {
            "status": "watch",
            "detail": "未改善（C3 不成立）",
            "compare": {
                "label": "未改善（C3 不成立）",
                "badge": "毛利率环比走弱",
                "yoy_line": "同比（26Q3 vs 25Q3）：毛利率 89.64%（-1.64pct）",
                "qoq_line": "环比（26Q3 vs 26Q2）：毛利率 89.64%（+0.38pct）",
                "verdict": "未改善的是「毛利率同比」（-1.64pct）；其余 5 项改善或持平。",
            },
        }
        points = self._margin_points(6)
        html = _margin_chart({"points": points, "count": 6,
                              "start": points[0]["date"], "end": points[-1]["date"]}, improve)
        self.assertNotIn("毛利率环比改善判定", html)
        self.assertNotIn("①", html)
        self.assertIn("［毛利率环比走弱］", html)               # 结论仍在 badge 上
        self.assertIn("同比（26Q3 vs 25Q3）", html)
        self.assertIn("环比（26Q3 vs 26Q2）", html)
        self.assertIn("未改善的是", html)
        self.assertEqual(html.count('<p class="small">同比'), 1)

    def test_margin_chart_without_compare_has_no_judge_block(self):
        """compare 为空（季报不连续）时正文不加任何判定段落。"""
        points = self._margin_points(6)
        html = _margin_chart({"points": points, "count": 6,
                              "start": points[0]["date"], "end": points[-1]["date"]},
                             {"status": "unknown", "detail": "季报不连续", "compare": {}})
        self.assertNotIn("毛利率环比改善判定", html)
        self.assertNotIn("未改善的是", html)
        self.assertIn("［数据不足］", html)

    def _margin_points(self, count: int) -> list[dict]:
        points = []
        for i in range(count):
            year, quarter = 2022 + i // 4, i % 4 + 1
            points.append({"date": f"{year}-{quarter * 3:02d}-28",
                           "label": f"{year % 100:02d}Q{quarter}",
                           "gross": 60.0 + i, "net": 20.0 + i})
        return points

    def test_margin_chart_full_five_years_has_no_short_note(self):
        points = self._margin_points(20)
        html = _margin_chart({"points": points, "count": 20,
                              "start": points[0]["date"], "end": points[-1]["date"]})
        self.assertIn("共 20 个季度", html)
        self.assertIn("覆盖 22Q1–26Q4", html)
        self.assertNotIn("不足", html)
        self.assertEqual(html.count('text-anchor="middle"'), 20)   # 20 个季度全标刻度

    def test_margin_chart_short_history_notes_shortfall(self):
        points = self._margin_points(6)
        html = _margin_chart({"points": points, "count": 6,
                              "start": points[0]["date"], "end": points[-1]["date"]})
        self.assertIn("共 6 个季度", html)
        self.assertIn(f"不足 {config.TREND_YEARS} 年", html)
        self.assertIn(f"需 {config.TREND_QUARTERS} 个季度", html)
        self.assertEqual(html.count('text-anchor="middle"'), 6)

    def test_margin_chart_aria_label_uses_years(self):
        points = self._margin_points(4)
        html = _margin_chart({"points": points, "count": 4,
                              "start": points[0]["date"], "end": points[-1]["date"]})
        self.assertIn(f"近 {config.TREND_YEARS} 年季度毛利率和净利率趋势", html)


class TemplateCacheTest(unittest.TestCase):
    """模板只读一次盘：批量 155 只股票时这是 155 次多余 IO。"""

    def test_template_is_read_once(self):
        from screen import render
        render._template_text.cache_clear()
        first = render._template_text()
        second = render._template_text()
        self.assertIs(first, second)
        info = render._template_text.cache_info()
        self.assertEqual((info.misses, info.hits), (1, 1))

    def test_render_html_reuses_cache(self):
        from screen import render
        render._template_text.cache_clear()
        render_html(support.scored_data())
        render_html(support.scored_data())
        self.assertEqual(render._template_text.cache_info().misses, 1)


class VersionTest(unittest.TestCase):
    def test_package_version_follows_config(self):
        """screen.__version__ 曾经写死 0.1.0，和报告页脚对不上。"""
        import screen
        self.assertEqual(screen.__version__, config.VERSION)

    def test_footer_prints_same_version(self):
        self.assertIn(f"程序版本 {config.VERSION}", render_html(support.scored_data()))


if __name__ == "__main__":
    unittest.main()
