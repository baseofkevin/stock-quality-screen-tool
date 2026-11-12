# -*- coding: utf-8 -*-
"""批量产物：CSV 读取、结论反解、导航页。"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import stock_report
import support
from screen.batch import (CODE_COLUMN_CANDIDATES, EASTMONEY_COLUMN,
                          LINK_COLUMN, SCORE_COLUMN, CsvTable, CsvError,
                          eastmoney_link_cell, eastmoney_url,
                          ensure_result_columns, link_target, read_csv_table,
                          report_link_cell, report_uri)
from screen.index_html import write_index_html
from screen.render import render_html
from screen.summary import SummaryError, extract_score_summary


class CsvReadTest(unittest.TestCase):
    def _csv(self, td, text: str, encoding: str = "utf-8") -> Path:
        path = Path(td) / "rows.csv"
        path.write_bytes(text.encode(encoding))
        return path

    def test_recognizes_code_column_variants(self):
        with tempfile.TemporaryDirectory() as td:
            for header in ("代码", "股票代码", "证券代码", "code", "Symbol", "ts_code"):
                path = self._csv(td, f"{header},名称\n600519,贵州茅台\n")
                self.assertEqual(read_csv_table(path).code_column, header)

    def test_ignores_case_space_and_bom_in_header(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.csv"
            path.write_bytes("\ufeffCode,名称\r\n600519,贵州茅台\r\n".encode())
            table = read_csv_table(path)
            self.assertEqual(table.code_column, "Code")
            self.assertEqual(table.rows[0]["名称"], "贵州茅台")

    def test_missing_code_column_reports_headers(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._csv(td, "编号,名称\n1,贵州茅台\n")
            with self.assertRaises(CsvError) as ctx:
                read_csv_table(path)
            self.assertIn("找不到股票代码列", str(ctx.exception))
            self.assertIn("编号", str(ctx.exception))

    def test_empty_file_and_empty_rows(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._csv(td, "")
            with self.assertRaises(CsvError):
                read_csv_table(path)
            path = self._csv(td, "代码,名称\n")
            with self.assertRaises(CsvError) as ctx:
                read_csv_table(path)
            self.assertIn("没有数据行", str(ctx.exception))

    def test_gb18030_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._csv(td, "代码,名称\n600519,贵州茅台\n", encoding="gb18030")
            table = read_csv_table(path)
            self.assertEqual(table.rows[0]["名称"], "贵州茅台")

    def test_crlf_and_bom_are_read_transparently(self):
        """读入只关心代码列，BOM / CRLF 不该影响解析（也不再需要回写保留它们）。"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.csv"
            path.write_bytes("\ufeff代码,名称\r\n600519,贵州茅台\r\n000001,平安银行\r\n".encode())
            table = read_csv_table(path)
            self.assertEqual(table.code_column, "代码")
            self.assertEqual([r["名称"] for r in table.rows], ["贵州茅台", "平安银行"])

    def test_missing_file(self):
        with self.assertRaises(CsvError):
            read_csv_table(Path(tempfile.gettempdir()) / "不存在.csv")


class ResultColumnsTest(unittest.TestCase):
    """结果列只加在内存表里：批量模式不写 CSV，导航页和 Excel 用它展示。"""

    def test_ensure_result_columns_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.csv"
            path.write_bytes("代码,名称\n600519,贵州茅台\n".encode())
            table = read_csv_table(path)
            ensure_result_columns(table)
            first = list(table.fieldnames)
            ensure_result_columns(table)
            self.assertEqual(table.fieldnames, first)
            for name in (SCORE_COLUMN, LINK_COLUMN, EASTMONEY_COLUMN):
                self.assertEqual(table.fieldnames.count(name), 1)



class LinkHelperTest(unittest.TestCase):
    def test_report_uri_is_file_url(self):
        uri = report_uri(Path(tempfile.gettempdir()) / "报告.html")
        self.assertTrue(uri.startswith("file:///"))
        self.assertIn("%E6%8A%A5%E5%91%8A", uri)    # 中文被编码

    def test_link_target_parses_formula_and_plain_text(self):
        self.assertEqual(link_target('=HYPERLINK("file:///a.html","打开报告")'), "file:///a.html")
        self.assertEqual(link_target("file:///a.html"), "file:///a.html")
        self.assertEqual(link_target(""), "")

    def test_eastmoney_url(self):
        self.assertEqual(eastmoney_url("600519"),
                         "https://quote.eastmoney.com/sh600519.html#fullScreenChart")
        self.assertEqual(eastmoney_url("sz300059"),
                         "https://quote.eastmoney.com/sz300059.html#fullScreenChart")
        self.assertEqual(eastmoney_url("920001"),
                         "https://quote.eastmoney.com/bj/920001.html#fullScreenChart")
        self.assertEqual(eastmoney_url("bad"), "")

    def test_eastmoney_link_cell(self):
        cell = eastmoney_link_cell("600519")
        self.assertTrue(cell.startswith('=HYPERLINK("https://quote.eastmoney.com/sh600519.html'))
        self.assertIn("东方财富网股票详情", cell)


class XlsxRemovedTest(unittest.TestCase):
    """0.9.10 起彻底移除 Excel 产物：模块、配置项、调用链都要消失。"""

    def test_module_is_gone(self):
        with self.assertRaises(ImportError):
            __import__("screen.xlsx")

    def test_config_has_no_xlsx_dir(self):
        self.assertFalse(hasattr(config, "XLSX_OUT_DIR"))

    def test_cli_has_no_xlsx_helper(self):
        self.assertFalse(hasattr(stock_report, "_xlsx_target"))
        self.assertFalse(hasattr(stock_report, "write_report_xlsx"))


class IndexHtmlTest(unittest.TestCase):
    def _table(self, td):
        out = Path(td) / "reports"
        out.mkdir()
        report = out / "报告.html"
        report.write_text("<html>ok</html>", encoding="utf-8")
        csv_path = Path(td) / "rows.csv"
        csv_path.write_bytes("\ufeff代码,名称\r\n600519,贵州茅台\r\n000001,平安银行\r\n".encode())
        table = read_csv_table(csv_path)
        ensure_result_columns(table)
        table.rows[0][SCORE_COLUMN] = "推荐买入"
        table.rows[0][LINK_COLUMN] = report_link_cell(report)
        table.rows[1][SCORE_COLUMN] = "回避"
        table.rows[1][LINK_COLUMN] = ""
        return table, out

    def test_buttons_and_badges(self):
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td)
            index = write_index_html(table, out)
            text = index.read_text(encoding="utf-8")
            self.assertIn("<title>报告导航 - rows</title>", text)
            self.assertIn('class="btn"', text)
            self.assertIn("无报告", text)
            self.assertIn('class="badge buy"', text)
            self.assertIn('class="badge avoid"', text)
            self.assertIn("买入类 1", text)
            self.assertIn("回避 1", text)
            self.assertIn("https://quote.eastmoney.com/sh600519.html", text)
            self.assertIn("贵州茅台", text)

    def test_skip_is_grey_unknown_badge(self):
        """「跳过：上市不足 3 年」没有结论，归灰色 unknown 徽标，不能显示成观察类。"""
        from screen.batch import SKIP_SCORE_TEXT
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td)
            table.rows[1][SCORE_COLUMN] = SKIP_SCORE_TEXT
            index = write_index_html(table, out)
            text = index.read_text(encoding="utf-8")
            self.assertIn(f'class="badge unknown">{SKIP_SCORE_TEXT}<', text)
            self.assertNotIn(f'class="badge watch">{SKIP_SCORE_TEXT}<', text)

    def test_nav_filename_follows_csv_stem(self):
        """导航页文件名 = 输入 CSV 主名（`季度清单.csv` → `季度清单.html`）。"""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "reports"
            out.mkdir()
            csv_path = Path(td) / "季度清单.csv"
            csv_path.write_bytes("\ufeff代码,名称\r\n600519,贵州茅台\r\n".encode())
            table = read_csv_table(csv_path)
            ensure_result_columns(table)
            table.rows[0][SCORE_COLUMN] = "观察"
            nav = write_index_html(table, out)
            self.assertEqual(nav.name, "季度清单.html")
            self.assertEqual(nav.parent, out.resolve())
            self.assertFalse((out / "index.html").exists())

    def test_code_and_name_are_escaped(self):
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td)
            table.rows[0][table.code_column] = "600519<script>"
            index = write_index_html(table, out)
            text = index.read_text(encoding="utf-8")
            # 导航页自带搜索用的 <script>，这里只检查注入内容被转义进单元格
            self.assertIn('<td class="code">600519&lt;script&gt;</td>', text)
            self.assertNotIn("600519<script>", text)


class IndexHtmlExtraColumnsTest(unittest.TestCase):
    """导航页新增的 5 列：原样透传输入 CSV，只做格式化，不补算。"""

    HEADER = ("代码", "名称", "二级行业", "毛利率改善",
              "池内换手分位", "分位星级", "总市值（亿）")

    def _table(self, td, body: str):
        out = Path(td) / "reports"
        out.mkdir()
        csv_path = Path(td) / "rows.csv"
        csv_path.write_bytes(("\ufeff" + ",".join(self.HEADER) + "\r\n" + body).encode())
        table = read_csv_table(csv_path)
        ensure_result_columns(table)
        table.rows[0][SCORE_COLUMN] = "观察"
        return table, out

    def test_header_has_all_ten_columns(self):
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td, "sh603355,莱克电气,小家电,否：20.84→18.83,1.5,***,197.42\r\n")
            text = write_index_html(table, out).read_text(encoding="utf-8")
            for name in ("代码", "名称", "综合评分", "二级行业", "毛利率改善",
                         "池内换手分位", "分位星级", "总市值（亿）", "报告", "东方财富网"):
                self.assertIn(f"<th>{name}</th>", text)
            self.assertEqual(text.count("<th>"), 10)

    def test_values_are_passed_through_verbatim(self):
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td, "sh603355,莱克电气,小家电,否：20.84→18.83,1.5,***,197.42\r\n")
            text = write_index_html(table, out).read_text(encoding="utf-8")
            self.assertIn("<td>小家电</td>", text)
            self.assertIn("1.5<span class=\"unit\">%</span>", text)
            self.assertIn('<span class="stars">***</span>', text)
            self.assertIn("<td class=\"num\">197.42</td>", text)

    def test_margin_column_keeps_only_yes_or_no(self):
        """CSV 里毛利率是一整句，导航页只留开头的「是/否」。"""
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(
                td,
                "sh600368,五洲交通,铁路公路,是：55.91→63.52（环比改善）；营收环比 +13.3%,16.5,***,70.18\r\n"
                "sz002302,西部建设,水泥,否：7.34→5.70（环比未改善）,1.6,**,60.21\r\n",
            )
            text = write_index_html(table, out).read_text(encoding="utf-8")
            self.assertIn('<span class="yes">是</span>', text)
            self.assertIn('<span class="no">否</span>', text)
            # 句子里的数字不能漏进导航页
            self.assertNotIn("55.91", text)
            self.assertNotIn("环比改善", text)

    def test_margin_unknown_renders_placeholder(self):
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td, "sh603355,莱克电气,小家电,不确定,1.5,***,197.42\r\n")
            text = write_index_html(table, out).read_text(encoding="utf-8")
            self.assertNotIn('<span class="yes">', text)
            self.assertNotIn('<span class="no">', text)
            self.assertIn('<span class="na">—</span>', text)

    def test_empty_cells_show_placeholder_not_zero(self):
        """空值一律显示占位符 —— 不补 0、不留白格。"""
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td, "sh603355,莱克电气,,,,\r\n")
            text = write_index_html(table, out).read_text(encoding="utf-8")
            self.assertIn('<span class="na">—</span>', text)
            self.assertNotIn("0.00", text)
            self.assertNotIn("<td></td>", text)

    def test_csv_without_extra_columns_still_renders_ten_columns(self):
        """输入 CSV 没有这几列时，导航页照样出 10 栏（值全部为占位符）。"""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "reports"
            out.mkdir()
            csv_path = Path(td) / "rows.csv"
            csv_path.write_bytes("\ufeff代码,名称\r\n600519,贵州茅台\r\n".encode())
            table = read_csv_table(csv_path)
            ensure_result_columns(table)
            text = write_index_html(table, out).read_text(encoding="utf-8")
            self.assertEqual(text.count("<th>"), 10)
            self.assertIn('<td class="num"><span class="na">—</span></td>', text)

    def test_empty_table_colspan_matches_columns(self):
        """空表兜底行的 colspan 必须跟着列数走，不能写死 5。"""
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "rows.csv"
            csv_path.write_bytes("\ufeff代码,名称\r\n".encode())     # 只有表头，read_csv_table 会拒绝
            table = CsvTable(path=csv_path, fieldnames=["代码", "名称"],
                             rows=[], code_column="代码")
            ensure_result_columns(table)
            text = write_index_html(table, Path(td)).read_text(encoding="utf-8")
            self.assertIn('colspan="10"', text)


class SummaryTest(unittest.TestCase):
    def test_extract_from_rendered_html(self):
        data = support.scored_data()
        summary = extract_score_summary(render_html(data))
        self.assertEqual(summary.conclusion, data["decision"]["label"])
        self.assertEqual(summary.quality, f"{data['quality']['score']:.1f}")
        self.assertEqual(summary.valuation, f"{data['valuation_score']['score']:.1f}")

    def test_missing_section(self):
        with self.assertRaises(SummaryError) as ctx:
            extract_score_summary("<html><body>没有评分区</body></html>")
        self.assertIn("四、综合评分", str(ctx.exception))

    def test_missing_each_field(self):
        head = '<h2>四、综合评分</h2>'
        cases = {
            "质量分 Q": f'{head}<div class="k">估值分 V</div><div class="v">60.0</div>'
                        f'<div class="k">结论</div><div class="v">观察</div></section>',
            "估值分 V": f'{head}<div class="k">质量分 Q</div><div class="v">80.0</div>'
                        f'<div class="k">结论</div><div class="v">观察</div></section>',
            "结论": f'{head}<div class="k">质量分 Q</div><div class="v">80.0</div>'
                    f'<div class="k">估值分 V</div><div class="v">60.0</div></section>',
        }
        for missing, html in cases.items():
            with self.assertRaises(SummaryError) as ctx:
                extract_score_summary(html)
            self.assertIn(missing, str(ctx.exception))

    def test_strips_tags_and_unescapes(self):
        html = ('<h2>四、综合评分</h2>'
                '<div class="k">质量分 Q</div><div class="v"><b>80.5</b></div>'
                '<div class="k">估值分 V</div><div class="v">—</div>'
                '<div class="k">结论</div><div class="v">观察 &amp; 等待</div></section>')
        summary = extract_score_summary(html)
        self.assertEqual(summary.quality, "80.5")
        self.assertEqual(summary.valuation, "—")
        self.assertEqual(summary.conclusion, "观察 & 等待")

    def test_marker_beats_label_text(self):
        """标记位说了算：小标题改成别的字也能取到（0.9.8 的结构解耦）。"""
        html = ('<h2>四、评分汇总</h2>'
                '<div class="k">质量得分</div><div class="v" data-metric="q">77.7</div>'
                '<div class="k">估值得分</div><div class="v" data-metric="v">55.5</div>'
                '<div class="k">最终结论</div><div class="v" data-metric="conclusion">可买</div>')
        summary = extract_score_summary(html)
        self.assertEqual((summary.quality, summary.valuation, summary.conclusion),
                         ("77.7", "55.5", "可买"))

    def test_marker_survives_heading_rewrite_in_real_report(self):
        """真实报告把第二节标题名改了以后，批量提取不能变成「评分提取失败」。"""
        html = render_html(support.scored_data())
        self.assertIn('data-metric="q"', html)
        rewritten = html.replace("四、综合评分", "四、评分")
        summary = extract_score_summary(rewritten)
        self.assertEqual(summary.conclusion, support.scored_data()["decision"]["label"])

    def test_legacy_report_without_marker_still_parses(self):
        """0.9.7 及更早生成的报告没有标记位，靠小标题文字回退解析。"""
        html = ('<h2>四、综合评分</h2>'
                '<div class="k">质量分 Q</div><div class="v">62.7</div>'
                '<div class="k">估值分 V</div><div class="v">55.1</div>'
                '<div class="k">结论</div><div class="v">观察</div></section>')
        summary = extract_score_summary(html)
        self.assertEqual((summary.quality, summary.valuation, summary.conclusion),
                         ("62.7", "55.1", "观察"))


class CodeColumnCandidatesTest(unittest.TestCase):
    def test_candidate_set_is_case_insensitive_friendly(self):
        lowered = {c.casefold() for c in CODE_COLUMN_CANDIDATES}
        for expected in ("代码", "股票代码", "证券代码", "code", "stock_code", "ts_code"):
            self.assertIn(expected.casefold(), lowered)


if __name__ == "__main__":
    unittest.main()
