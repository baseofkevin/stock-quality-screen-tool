# -*- coding: utf-8 -*-
"""CLI：参数解析、退出码、单股/批量主流程。"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stock_report
import config
import support
from screen.batch import (EASTMONEY_COLUMN, LINK_COLUMN, SCORE_COLUMN, link_target,
                          read_csv_table)
from screen.fetch import DataError


class ParserTest(unittest.TestCase):
    def test_requires_exactly_one_source(self):
        parser = stock_report.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args([])
            with self.assertRaises(SystemExit):
                parser.parse_args(["--stock-code", "600519", "--csv-input", "a.csv"])

    def test_defaults(self):
        args = stock_report.build_parser().parse_args(["--stock-code", "600519"])
        self.assertEqual(Path(args.out_dir), support.ROOT / "html-report")
        # 批量结果 Excel 的默认落盘目录：项目内 xlsx-output/，与 html-report/ 同级
        self.assertEqual(Path(config.XLSX_OUT_DIR), support.ROOT / "xlsx-output")
        self.assertEqual(args.timeout, 90.0)
        self.assertEqual(args.workers, 4)
        self.assertEqual(args.retries, 2)
        self.assertEqual(args.retry_wait, 60.0)
        self.assertFalse(args.force)
        self.assertFalse(args.quiet)

    def test_flags(self):
        args = stock_report.build_parser().parse_args([
            "--csv-input", "a.csv", "--workers", "8", "--retries", "0",
            "--retry-wait", "5", "--force", "--quiet", "--out-dir", "/tmp/x",
        ])
        self.assertEqual(args.workers, 8)
        self.assertEqual(args.retries, 0)
        self.assertEqual(args.retry_wait, 5.0)
        self.assertTrue(args.force)
        self.assertTrue(args.quiet)
        self.assertEqual(args.out_dir, "/tmp/x")

    def test_csv_alias_matches_old_name(self):
        """--csv 是新名，--csv-input 作为旧名必须仍然可用且落到同一个 dest。"""
        for flag in ("--csv", "--csv-input"):
            args = stock_report.build_parser().parse_args([flag, "a.csv"])
            self.assertEqual(args.csv_input, "a.csv", flag)

    def test_csv_and_stock_code_are_mutually_exclusive(self):
        parser = stock_report.build_parser()
        for flag in ("--csv", "--csv-input"):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args(["--stock-code", "600519", flag, "a.csv"])

    def test_help_says_it_rewrites_the_csv_in_place(self):
        """这个参数名里带 csv，实际会改写传入的文件——帮助里必须写明，别让人拿只读表去跑。"""
        # argparse 按终端宽度折行，可能把 xlsx-output 拆成「xlsx- / output」，先去空白再断言
        text = "".join(stock_report.build_parser().format_help().split())
        self.assertIn("就地改写", text)
        self.assertIn("HTML报告链接", text)
        self.assertIn("xlsx-output", text)
        self.assertIn("--csv-input", text)


class ArgumentValidationTest(unittest.TestCase):
    def _rc(self, argv):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return stock_report.main(argv)

    def test_negative_retries(self):
        self.assertEqual(self._rc(["--stock-code", "600519", "--retries", "-1"]), 2)

    def test_negative_retry_wait(self):
        self.assertEqual(self._rc(["--stock-code", "600519", "--retry-wait", "-1"]), 2)

    def test_batch_rejects_bundle(self):
        self.assertEqual(self._rc(["--csv-input", "a.csv", "--bundle", "b.json"]), 2)

    def test_batch_rejects_name(self):
        self.assertEqual(self._rc(["--csv-input", "a.csv", "--name", "x"]), 2)

    def test_batch_rejects_zero_workers(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "rows.csv"
            support.write_csv(csv_path, [{"代码": "600519"}], ["代码"])
            self.assertEqual(self._rc(["--csv-input", str(csv_path), "--workers", "0"]), 2)


class ScoreLineTest(unittest.TestCase):
    """CLI 摘要的 Q/V 行：金融股的 None 不能直接格式化。"""

    def test_normal_scores(self):
        line = stock_report._score_line({"quality": {"score": 89.04},
                                         "valuation_score": {"score": 62.25}})
        self.assertIn("质量分 Q 89.0 / 100", line)
        self.assertIn("估值分 V 62.2 / 100", line)

    def test_not_applicable_scores(self):
        line = stock_report._score_line({
            "quality": {"score": None, "not_applicable": True},
            "valuation_score": {"score": None, "not_applicable": True},
        })
        self.assertIn("质量分 Q 不适用", line)
        self.assertIn("估值分 V 不适用", line)
        self.assertNotIn("/ 100", line)

    def test_missing_valuation_keeps_dash(self):
        line = stock_report._score_line({"quality": {"score": 70.0},
                                         "valuation_score": {"score": None}})
        self.assertIn("估值分 V —", line)


class SingleRunTest(unittest.TestCase):
    def test_bundle_run_writes_one_html(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                rc = stock_report.main(["--stock-code", "600519",
                                        "--bundle", str(support.FIXTURE), "--out-dir", str(out)])
            self.assertEqual(rc, 0)
            files = list(out.iterdir())
            self.assertEqual(len(files), 1)
            self.assertRegex(files[0].name, r"^贵州茅台-企业质量初筛-\d{8}-\d{6}\.html$")
            text = stdout.getvalue()
            self.assertIn("质量分 Q", text)
            self.assertIn("结论", text)

    def test_name_override_changes_filename_only(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--stock-code", "600519", "--bundle", str(support.FIXTURE),
                                        "--out-dir", str(out), "--name", "自定义/名称"])
            self.assertEqual(rc, 0)
            name = next(out.iterdir()).name
            self.assertTrue(name.startswith("自定义_名称-企业质量初筛-"))
            self.assertIn("贵州茅台", (out / name).read_text(encoding="utf-8"))

    def test_quiet_suppresses_stdout(self):
        with tempfile.TemporaryDirectory() as td:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                rc = stock_report.main(["--stock-code", "600519", "--bundle", str(support.FIXTURE),
                                        "--out-dir", td, "--quiet"])
            self.assertEqual(rc, 0)
            self.assertEqual(stdout.getvalue(), "")

    def test_missing_bundle_returns_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc = stock_report.main(["--stock-code", "600519",
                                    "--bundle", str(Path(tempfile.gettempdir()) / "no.json"),
                                    "--out-dir", tempfile.gettempdir()])
        self.assertEqual(rc, 2)

    def test_invalid_code_returns_2(self):
        with patch("stock_report.fetch_all", side_effect=ValueError("股票代码应为 600519")):
            with contextlib.redirect_stderr(io.StringIO()):
                rc = stock_report.main(["--stock-code", "abc", "--out-dir", tempfile.gettempdir()])
        self.assertEqual(rc, 2)

    def test_data_error_returns_2(self):
        with patch("stock_report.fetch_all", side_effect=DataError("关键数据 data_finance 获取失败")):
            with contextlib.redirect_stderr(io.StringIO()):
                rc = stock_report.main(["--stock-code", "600519", "--out-dir", tempfile.gettempdir()])
        self.assertEqual(rc, 2)

    def test_unexpected_error_returns_3(self):
        with patch("stock_report.fetch_all", side_effect=RuntimeError("boom")):
            with contextlib.redirect_stderr(io.StringIO()):
                rc = stock_report.main(["--stock-code", "600519", "--out-dir", tempfile.gettempdir()])
        self.assertEqual(rc, 3)


class BatchRunTest(unittest.TestCase):
    def setUp(self):
        # 结果 Excel 固定写到 config.XLSX_OUT_DIR；测试要落到临时目录，别污染项目的 xlsx-output/
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.xlsx_dir = Path(tmp.name) / "xlsx-output"
        patcher = patch.object(config, "XLSX_OUT_DIR", str(self.xlsx_dir))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _csv(self, td, rows):
        path = Path(td) / "rows.csv"
        support.write_csv(path, rows, ["代码", "名称"])
        return path

    def test_xlsx_target_keeps_csv_stem_under_xlsx_output(self):
        """目标路径 = xlsx-output/<输入 CSV 主名>.xlsx，与输入 CSV 所在目录无关。"""
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"}])
            table = read_csv_table(csv_path)
            target = stock_report._xlsx_target(table)
            self.assertEqual(target, self.xlsx_dir / "rows.xlsx")
            self.assertNotEqual(target.parent, Path(td))     # 不再写在输入 CSV 旁边

    def test_duplicate_codes_fetch_once_and_fill_both_rows(self):
        calls = {"n": 0}

        def fake_fetch(code, timeout=90.0, **kwargs):
            calls["n"] += 1
            return support.raw_bundle()

        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"},
                                      {"代码": "600519", "名称": "贵州茅台"}])
            with patch("stock_report.fetch_all", side_effect=fake_fetch), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(Path(td) / "reports"), "--quiet"])
            self.assertEqual(rc, 0)
            self.assertEqual(calls["n"], 1)
            rows = support.read_csv_rows(csv_path)
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertTrue(row[SCORE_COLUMN])
                self.assertTrue(row[LINK_COLUMN].startswith('=HYPERLINK("file:///'))
                self.assertIn("东方财富网股票详情", row[EASTMONEY_COLUMN])

    def test_invalid_code_marks_row_and_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "abc", "名称": "无效"}])
            with patch("stock_report.fetch_all", side_effect=AssertionError("不应取数")), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(Path(td) / "reports"), "--quiet"])
            self.assertEqual(rc, 1)
            row = support.read_csv_rows(csv_path)[0]
            self.assertEqual(row[SCORE_COLUMN], "代码无效")
            self.assertEqual(row[LINK_COLUMN], "")
            self.assertEqual(row[EASTMONEY_COLUMN], "")

    def test_missing_code_row_is_marked(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "", "名称": "空"}])
            with contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(Path(td) / "reports"), "--quiet"])
            self.assertEqual(rc, 1)
            self.assertEqual(support.read_csv_rows(csv_path)[0][SCORE_COLUMN], "缺少股票代码")

    def test_report_links_point_to_existing_files(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"}])
            out_dir = Path(td) / "reports"
            with patch("stock_report.fetch_all", return_value=support.raw_bundle()), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 0)
            link = support.read_csv_rows(csv_path)[0][LINK_COLUMN]
            report = Path(unquote(urlparse(link_target(link)).path))
            self.assertTrue(report.is_file())
            self.assertEqual(report.parent.resolve(), out_dir.resolve())
            self.assertRegex(report.name, r"^贵州茅台-sh600519-企业质量初筛-\d{8}-\d{6}\.html$")
            self.assertTrue((out_dir / "index.html").is_file())
            # 结果 Excel 落在 config.XLSX_OUT_DIR，不再写到输入 CSV 旁边
            xlsx = self.xlsx_dir / "rows.xlsx"
            self.assertTrue(xlsx.is_file())
            self.assertFalse(csv_path.with_suffix(".xlsx").exists())


if __name__ == "__main__":
    unittest.main()
