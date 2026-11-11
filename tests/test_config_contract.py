# -*- coding: utf-8 -*-
"""config 是唯一事实：改了 config，代码与报告文字必须跟着变（不是只改了一半）。

这些测试专门守「说一套、算一套」这类回归：
  - 子项区间 / 决策矩阵 / 分档表 / 权重说明彼此不重复，且都被真正读到；
  - 商誉三个常量、分数条配色与硬门槛不会各走各的。
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import support  # noqa: F401  (把项目根加入 sys.path)
import config
from screen import render, score


class ItemRangeTest(unittest.TestCase):
    def test_ratio_items_are_the_only_ones_without_range(self):
        """只有「已知年数里占几成」的两个子项没有区间，其余都必须有。"""
        ratio_by_group = {"returns": {"above_wacc"}, "cash": {"fcf_years"}}
        for group, items in config.QUALITY_ITEM_MAX.items():
            with self.subTest(group=group):
                expected = ratio_by_group.get(group, set())
                self.assertEqual(set(items) - set(config.QUALITY_ITEM_RANGES[group]), expected)
                self.assertEqual(set(config.QUALITY_ITEM_RANGES[group]) - set(items), set())

    def test_ranges_are_well_formed(self):
        for group, items in config.QUALITY_ITEM_RANGES.items():
            for item, (low, high, direction) in items.items():
                with self.subTest(item=item):
                    self.assertLess(low, high)
                    self.assertIn(direction, ("up", "down"))

    def test_band_reads_config(self):
        """把区间改成 (0, 10)，ROE 5% 就该拿一半分——证明区间真的从 config 读。"""
        m = {"returns": {"roe": 6}}
        self.assertAlmostEqual(score._band("returns", "roe", 20.0, m), 6.0)
        patched = {"returns": {"roe": (0.0, 10.0, "up")}}
        with patch.dict(config.QUALITY_ITEM_RANGES, patched, clear=False):
            self.assertAlmostEqual(score._band("returns", "roe", 5.0, m), 3.0)


class GradeTest(unittest.TestCase):
    def test_boundaries_follow_config(self):
        self.assertEqual(score.grade_of(None), "数据不足")
        for cut, label in config.QUALITY_GRADES:
            self.assertEqual(score.grade_of(cut), label, cut)
            if cut > 0:
                self.assertNotEqual(score.grade_of(cut - 0.1), label, cut)

    def test_grade_text_matches_table(self):
        text = render._grade_text()
        self.assertIn("优秀 ≥85", text)
        self.assertIn("良好 75~85", text)
        self.assertIn("差 &lt;45", text)

    def test_score_bar_thresholds_do_not_drift(self):
        """分数条的红色门槛必须等于买入硬门槛，绿色门槛必须等于「中等偏上」下限。"""
        self.assertEqual(config.SCORE_BAR_BAD, config.QUALITY_HARD_FLOOR)
        self.assertEqual(config.SCORE_BAR_GOOD, 65.0)
        self.assertIn((config.SCORE_BAR_GOOD, "中等偏上"), config.QUALITY_GRADES)
        self.assertEqual(render._score_class(64.9), "")
        self.assertEqual(render._score_class(65), "good")
        self.assertEqual(render._score_class(44.9), "bad")
        self.assertEqual(render._score_class(None), "")


class DecisionMatrixTest(unittest.TestCase):
    def test_shape(self):
        tiers = config.DECISION_MATRIX
        q_mins = [t["q_min"] for t in tiers]
        self.assertEqual(q_mins, sorted(q_mins, reverse=True))     # 从高到低
        self.assertLessEqual(q_mins[-1], config.QUALITY_HARD_FLOOR)  # 最低档覆盖到硬门槛
        for tier in tiers:
            self.assertIsNone(tier["rules"][-1]["v_min"], tier["q_min"])   # 末条必须兜底
            v_mins = [r["v_min"] for r in tier["rules"][:-1]]
            self.assertEqual(v_mins, sorted(v_mins, reverse=True), tier["q_min"])
            for rule in tier["rules"]:
                for field in ("key", "label", "reason", "text"):
                    self.assertTrue(rule[field], (tier["q_min"], field))

    def test_every_cell_is_reachable(self):
        """每个档位 × 每条规则都要能被 _decision() 真的选中，且落在该格上。"""
        for tier in config.DECISION_MATRIX:
            for rule in tier["rules"]:
                v = rule["v_min"] if rule["v_min"] is not None else 0.0
                if rule["v_min"] is not None:
                    # 恰好等于门槛 → 该格；再低 0.1 → 下一格
                    got = score._decision({"score": tier["q_min"]}, {"score": v}, [], {})
                    self.assertEqual(got["label"], rule["label"], (tier["q_min"], v))
                    nxt = tier["rules"][tier["rules"].index(rule) + 1]
                    below = score._decision({"score": tier["q_min"]}, {"score": v - 0.1}, [], {})
                    self.assertEqual(below["label"], nxt["label"], (tier["q_min"], v - 0.1))
                else:
                    got = score._decision({"score": tier["q_min"]}, {"score": v}, [], {})
                    self.assertEqual(got["label"], rule["label"], (tier["q_min"], v))

    def test_below_floor_is_avoid(self):
        got = score._decision({"score": 44.9}, {"score": 100}, [], {})
        self.assertEqual(got["key"], "avoid")
        self.assertIn("44.9", got["reason"])

    def test_matrix_text_is_generated_from_config(self):
        text = render._matrix_text()
        self.assertIn("Q≥75：V≥65 推荐买入，50~65 等价格，35~50 偏贵，&lt;35 太贵；", text)
        self.assertIn("Q65~75：V≥80 推荐买入，70~80 可买，50~70 观察，&lt;50 回避；", text)
        self.assertIn(f"Q&lt;{config.QUALITY_HARD_FLOOR:g}：回避，禁止买入", text)
        # 换一个门槛，文字必须跟着换（旧写法是手写的，改 config 不会动）
        tiers = [dict(t, rules=tuple(t["rules"])) for t in config.DECISION_MATRIX]
        tiers[0] = dict(tiers[0], rules=(
            dict(tiers[0]["rules"][0], v_min=72.0),) + tiers[0]["rules"][1:])
        with patch.object(config, "DECISION_MATRIX", tuple(tiers)):
            self.assertIn("V≥72 推荐买入", render._matrix_text())


class FatalTextTest(unittest.TestCase):
    def test_uses_config_numbers(self):
        text = render._fatal_rule_text()
        self.assertIn(f"利息保障 &lt;{config.INTEREST_COVER_FATAL:g}", text)
        self.assertIn(f"商誉 &gt;{config.GOODWILL_EQUITY_FATAL * 100:.0f}%", text)
        self.assertIn(f"连续 {config.FCF_NEGATIVE_YEARS} 年", text)
        with patch.object(config, "GOODWILL_EQUITY_FATAL", 0.6):
            self.assertIn("商誉 &gt;60%", render._fatal_rule_text())

    def test_goodwill_thresholds_are_ordered(self):
        """WATCH < HIT < FATAL，且风险检查的分支用的就是这两个名字。"""
        self.assertLess(config.GOODWILL_EQUITY_WATCH, config.GOODWILL_EQUITY_HIT)
        self.assertLess(config.GOODWILL_EQUITY_HIT, config.GOODWILL_EQUITY_FATAL)
        for name in ("GOODWILL_EQUITY_MAX", "GOODWILL_EQUITY_WARN"):
            self.assertFalse(hasattr(config, name), name)   # 旧名字必须彻底消失


class WeightTextTest(unittest.TestCase):
    def test_footer_and_formula_are_generated(self):
        q_text = render._weight_text(config.QUALITY_WEIGHTS, config.QUALITY_GROUP_LABELS)
        self.assertEqual(q_text, "资本回报 30、现金创造力 25、资产负债表 20、成长与稳定 15、会计质量 10")
        v_text = render._weight_text(config.VALUATION_WEIGHTS, config.VALUATION_WEIGHT_TEXT)
        self.assertEqual(v_text, "机构目标价空间 40、预测 PE 相对当前 PE 20、预期未来净利增速 40")
        self.assertEqual(render._v_formula_text(),
                         "机构目标价空间 40% + 预测 PE 相对当前 PE 20% + 预期未来净利增速 40%")

    def test_group_labels_cover_all_weights(self):
        self.assertEqual(set(config.QUALITY_GROUP_LABELS), set(config.QUALITY_WEIGHTS))
        self.assertEqual(set(config.VALUATION_WEIGHT_TEXT), set(config.VALUATION_WEIGHTS))


if __name__ == "__main__":
    unittest.main()
