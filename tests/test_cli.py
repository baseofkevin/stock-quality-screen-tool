# -*- coding: utf-8 -*-
"""CLI：参数解析、退出码、单股/批量主流程。"""
import contextlib
import io
import os
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
from screen.batch import (EASTMONEY_COLUMN, LINK_COLUMN, SCORE_COLUMN,
                          SKIP_SCORE_TEXT)
from screen.fetch import DataError


def _trim_annual(years: int):
    """把 build_report_data 的年报窗口截到 N 年，用来构造「上市不足 3 年」。

    注意在 patch 生效前求值，拿到的仍是未打补丁的原函数。
    """
    real = stock_report.build_report_data

    def wrapped(calls, code):
        data = real(calls, code)
        data["financials"]["annual"] = data["financials"]["annual"][:years]
        return data

    return wrapped


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
        self.assertEqual(args.timeout, 90.0)
        self.assertEqual(args.workers, 4)
        self.assertEqual(args.retries, 2)
        self.assertEqual(args.retry_wait, 60.0)
        self.assertFalse(args.force)
        self.assertFalse(args.quiet)

    def test_no_xlsx_output_config(self):
        """0.9.10 起批量不再产出 Excel：配置项与模块都必须删掉，不能只停止调用。"""
        self.assertFalse(hasattr(config, "XLSX_OUT_DIR"))
        with self.assertRaises(ImportError):
            __import__("screen.xlsx")

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

    def test_help_promises_the_input_csv_is_read_only(self):
        """帮助里必须写明「输入只读、不产出 CSV/Excel」，否则没人敢指向原始选股表。"""
        # argparse 按终端宽度折行，可能把长句拆开，先去空白再断言
        text = "".join(stock_report.build_parser().format_help().split())
        self.assertIn("输入CSV只读", text)
        self.assertIn("也不会产出新的CSV", text)
        self.assertIn("--csv-input", text)
        self.assertNotIn("就地改写", text)
        self.assertNotIn("csv-output", text)
        # 不再承诺 Excel：产物只有 HTML 与导航页
        self.assertNotIn("xlsx-output", text)


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

    def test_missing_quality_keeps_dash_not_not_applicable(self):
        """Q 算不出来（非金融股）要打「—」，不能一律说「不适用」（P2-4）。"""
        line = stock_report._score_line({"quality": {"score": None},
                                         "valuation_score": {"score": None}})
        self.assertIn("质量分 Q —", line)
        self.assertNotIn("质量分 Q 不适用", line)
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

    def test_quiet_is_forwarded_to_fetch_layer(self):
        """--quiet 要同步到取数层，否则重试警告还会往 stderr 打（P2-8）。"""
        with tempfile.TemporaryDirectory() as td, \
                patch("stock_report.set_quiet") as quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                stock_report.main(["--stock-code", "600519", "--bundle", str(support.FIXTURE),
                                   "--out-dir", td, "--quiet"])
            quiet.assert_called_once_with(True)

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

    def test_too_few_annuals_skips_with_exit_0(self):
        """上市不足 3 年：跳过，不出报告，退出码 0（不是错误，也不是参数错）。"""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch("stock_report.build_report_data", side_effect=_trim_annual(2)), \
                    patch("stock_report.fetch_all", return_value=support.raw_bundle()), \
                    contextlib.redirect_stdout(io.StringIO()) as stdout:
                rc = stock_report.main(["--stock-code", "600519", "--out-dir", str(out)])
            self.assertEqual(rc, 0)
            self.assertEqual(list(out.iterdir()), [])          # 不落盘
            self.assertIn("跳过", stdout.getvalue())
            self.assertIn("上市不足 3 年", stdout.getvalue())


class BatchRunTest(unittest.TestCase):
    def _csv(self, td, rows):
        path = Path(td) / "rows.csv"
        support.write_csv(path, rows, ["代码", "名称"])
        return path

    def _nav(self, out_dir: Path, stem: str = "rows") -> str:
        """批量结果的可读出口是导航页（批量不再写 CSV / Excel）。"""
        return (out_dir / f"{stem}.html").read_text(encoding="utf-8")

    def _reports(self, out_dir: Path) -> list[Path]:
        return sorted(out_dir.glob("*-企业质量初筛-*.html"))

    def test_duplicate_codes_fetch_once_and_fill_both_rows(self):
        calls = {"n": 0}

        def fake_fetch(code, timeout=90.0, **kwargs):
            calls["n"] += 1
            return support.raw_bundle()

        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"},
                                      {"代码": "600519", "名称": "贵州茅台"}])
            out_dir = Path(td) / "reports"
            with patch("stock_report.fetch_all", side_effect=fake_fetch), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 0)
            self.assertEqual(calls["n"], 1)
            nav = self._nav(out_dir)
            self.assertEqual(nav.count('<td class="code">600519</td>'), 2)
            self.assertEqual(nav.count("https://quote.eastmoney.com/sh600519.html"), 2)
            self.assertEqual(len(self._reports(out_dir)), 1)

    def test_input_csv_is_never_modified_and_no_csv_is_written(self):
        """硬承诺：输入 CSV 只读，批量也不产出任何新 CSV。"""
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"}])
            before = csv_path.read_bytes()
            mtime = csv_path.stat().st_mtime_ns
            out_dir = Path(td) / "reports"
            with patch("stock_report.fetch_all", return_value=support.raw_bundle()), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 0)
            self.assertEqual(csv_path.read_bytes(), before)
            self.assertEqual(csv_path.stat().st_mtime_ns, mtime)
            self.assertNotIn(SCORE_COLUMN.encode(), before)      # 输入表没被加列
            self.assertEqual(list(Path(td).rglob("*.csv")), [csv_path])
            self.assertEqual(len(self._reports(out_dir)), 1)

    def test_read_only_input_csv_still_runs(self):
        """输入是 0444 也能跑：批量只读它，不写它。"""
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"}])
            os.chmod(csv_path, 0o444)
            out_dir = Path(td) / "reports"
            with patch("stock_report.fetch_all", return_value=support.raw_bundle()), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(self._reports(out_dir)), 1)

    def test_invalid_code_marks_row_and_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "abc", "名称": "无效"}])
            out_dir = Path(td) / "reports"
            with patch("stock_report.fetch_all", side_effect=AssertionError("不应取数")), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 1)
            nav = self._nav(out_dir)
            self.assertIn("代码无效", nav)
            self.assertIn("无报告", nav)
            self.assertEqual(self._reports(out_dir), [])

    def test_missing_code_row_is_marked(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "", "名称": "空"}])
            out_dir = Path(td) / "reports"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 1)
            self.assertIn("缺少股票代码", self._nav(out_dir))

    def test_too_few_annuals_marks_skip_and_exits_0(self):
        """批量：导航页写「跳过：上市不足 3 年」、不生成 HTML、不算失败（退出码 0）。"""
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"}])
            out_dir = Path(td) / "reports"
            with patch("stock_report.build_report_data", side_effect=_trim_annual(2)), \
                    patch("stock_report.fetch_all", return_value=support.raw_bundle()), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 0)                    # 跳过不算失败
            self.assertIn(SKIP_SCORE_TEXT, self._nav(out_dir))
            self.assertEqual(self._reports(out_dir), [])   # 只有导航页，没有报告

    def test_skip_and_failure_are_counted_separately(self):
        """跳过与真失败分开计数：跳过不影响退出码，失败才让退出码为 1。"""
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"},
                                      {"代码": "000001", "名称": "平安银行"}])

            def fake_fetch(code, timeout=90.0, **kwargs):
                if code == "sz000001":
                    raise DataError("关键数据 data_finance 获取失败")
                return support.raw_bundle()

            out_dir = Path(td) / "reports"
            with patch("stock_report.build_report_data", side_effect=_trim_annual(2)), \
                    patch("stock_report.fetch_all", side_effect=fake_fetch), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 1)                    # 有 1 行真失败
            nav = self._nav(out_dir)
            self.assertIn(SKIP_SCORE_TEXT, nav)
            self.assertIn("生成失败", nav)

    def test_batch_writes_report_and_nav_only(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"}])
            out_dir = Path(td) / "reports"
            with patch("stock_report.fetch_all", return_value=support.raw_bundle()), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = stock_report.main(["--csv-input", str(csv_path),
                                        "--out-dir", str(out_dir), "--quiet"])
            self.assertEqual(rc, 0)
            reports = self._reports(out_dir)
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].parent.resolve(), out_dir.resolve())
            self.assertRegex(reports[0].name,
                             r"^贵州茅台-sh600519-企业质量初筛-\d{8}-\d{6}\.html$")
            self.assertTrue((out_dir / "rows.html").is_file())   # 导航页跟 CSV 主名一致
            # 产物只有两处：报告目录里的 HTML + 同目录导航页；不再产生任何 Excel
            self.assertEqual(sorted(p.suffix for p in out_dir.iterdir()),
                             [".html", ".html"])
            self.assertFalse(list(Path(td).rglob("*.xlsx")))
            self.assertFalse(csv_path.with_suffix(".xlsx").exists())

    def test_second_run_resumes_without_refetching(self):
        """续跑只看输出目录里的报告（文件名带代码），不依赖任何 CSV。"""
        with tempfile.TemporaryDirectory() as td:
            csv_path = self._csv(td, [{"代码": "600519", "名称": "贵州茅台"}])
            out_dir = Path(td) / "reports"

            def must_not_fetch(code, timeout=90.0, **kwargs):
                raise AssertionError("已有报告时不应重新取数")

            with patch("stock_report.fetch_all", return_value=support.raw_bundle()), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(stock_report.main(["--csv-input", str(csv_path),
                                                    "--out-dir", str(out_dir),
                                                    "--quiet"]), 0)
            first = self._reports(out_dir)
            self.assertEqual(len(first), 1)
            with patch("stock_report.fetch_all", side_effect=must_not_fetch), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(stock_report.main(["--csv-input", str(csv_path),
                                                    "--out-dir", str(out_dir),
                                                    "--quiet"]), 0)
            self.assertEqual(self._reports(out_dir), first)      # 没有新增报告


if __name__ == "__main__":
    unittest.main()
