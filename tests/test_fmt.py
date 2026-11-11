# -*- coding: utf-8 -*-
"""格式化：唯一实现 + 三个调用方必须真的在用它（screen/fmt.py）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import support  # noqa: F401  (把项目根加入 sys.path)
from screen import fmt, render, score  # noqa: E402


class NumTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(fmt.num(None), "—")
        self.assertEqual(fmt.num(1.234), "1.23")
        self.assertEqual(fmt.num(1.2, 1), "1.2")

    def test_separator(self):
        self.assertEqual(fmt.num_sep(1234.5), "1,234.50")
        self.assertEqual(fmt.num(1234.5), "1234.50")   # 比率不加千分位


class PctTest(unittest.TestCase):
    def test_pct(self):
        self.assertEqual(fmt.pct(None), "—")
        self.assertEqual(fmt.pct(12.34), "12.3%")
        self.assertEqual(fmt.pct(12.345, 2), "12.35%")
        self.assertEqual(fmt.pct(12.34, 0), "12%")

    def test_signed(self):
        self.assertEqual(fmt.signed_pct(None), "—")
        self.assertEqual(fmt.signed_pct(0.1234), "+12.3%")
        self.assertEqual(fmt.signed_pct(-0.05), "-5.0%")


class YiTest(unittest.TestCase):
    def test_with_and_without_suffix(self):
        self.assertEqual(fmt.yi(None), "—")
        self.assertEqual(fmt.yi(1e8), "1.00")
        self.assertEqual(fmt.yi(1.234e10, 1), "123.4")
        self.assertEqual(fmt.yi_suffix(1e8), "1.00 亿")
        self.assertEqual(fmt.yi_suffix(2.5e8, 1), "2.5 亿")


class NonNumericTest(unittest.TestCase):
    """接口偶尔直接给中文（例如「不适用」），原样转义输出，不能让整份报告挂掉。"""

    def test_passthrough_is_escaped(self):
        for fn in (fmt.num, fmt.num_sep, fmt.pct, fmt.signed_pct, fmt.yi, fmt.yi_suffix):
            self.assertEqual(fn("不适用"), "不适用", msg=fn.__name__)
            self.assertEqual(fn("<b>"), "&lt;b&gt;", msg=fn.__name__)


class SingleImplementationTest(unittest.TestCase):
    """三套实现合并后，score / render 用的必须就是 fmt 里的函数本身。"""

    def test_score_aliases(self):
        self.assertIs(score._p, fmt.pct)
        self.assertIs(score._n, fmt.num)
        self.assertIs(score._yi, fmt.yi_suffix)
        self.assertIs(score._delta_pct, fmt.signed_pct)

    def test_render_aliases(self):
        self.assertIs(render.pct, fmt.pct)
        self.assertIs(render.yi, fmt.yi)
        self.assertIs(render.n, fmt.num_sep)

    def test_util_no_longer_owns_formatting(self):
        from screen import util
        for name in ("pct", "yi", "ratio", "text"):
            self.assertFalse(hasattr(util, name), name)


if __name__ == "__main__":
    unittest.main()
