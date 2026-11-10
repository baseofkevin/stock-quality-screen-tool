# -*- coding: utf-8 -*-
"""批量产物：CSV 读写、结论反解、XLSX、导航页。"""
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import support
from screen.batch import (CODE_COLUMN_CANDIDATES, EASTMONEY_COLUMN,
                          LINK_COLUMN, SCORE_COLUMN, CsvError,
                          eastmoney_link_cell, eastmoney_url,
                          ensure_result_columns, link_target, read_csv_table,
                          report_link_cell, report_uri, write_csv_table)
from screen.index_html import write_index_html
from screen.render import render_html
from screen.summary import SummaryError, extract_score_summary
from screen.xlsx import write_report_xlsx


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
            self.assertEqual(table.encoding, "gb18030")
            self.assertEqual(table.rows[0]["名称"], "贵州茅台")

    def test_lineterminator_detected(self):
        with tempfile.TemporaryDirectory() as td:
            crlf = self._csv(td, "代码,名称\r\n600519,贵州茅台\r\n")
            self.assertEqual(read_csv_table(crlf).lineterminator, "\r\n")
            lf = Path(td) / "lf.csv"
            lf.write_bytes("代码,名称\n600519,贵州茅台\n".encode())
            self.assertEqual(read_csv_table(lf).lineterminator, "\n")

    def test_missing_file(self):
        with self.assertRaises(CsvError):
            read_csv_table(Path(tempfile.gettempdir()) / "不存在.csv")


class CsvWriteTest(unittest.TestCase):
    def test_roundtrip_keeps_bom_crlf_and_extra_columns(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.csv"
            path.write_bytes("\ufeff代码,名称,备注\r\n600519,贵州茅台,保留\r\n".encode())
            table = read_csv_table(path)
            ensure_result_columns(table)
            table.rows[0][SCORE_COLUMN] = "可买"
            table.rows[0][LINK_COLUMN] = report_link_cell(Path(td) / "报告.html")
            write_csv_table(table)

            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", raw)
            row = support.read_csv_rows(path)[0]
            self.assertEqual(row["名称"], "贵州茅台")
            self.assertEqual(row["备注"], "保留")
            self.assertEqual(row[SCORE_COLUMN], "可买")
            self.assertTrue(row[LINK_COLUMN].startswith('=HYPERLINK("file:///'))

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

    def test_keeps_file_permission_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.csv"
            path.write_bytes("代码,名称\n600519,贵州茅台\n".encode())
            os.chmod(path, 0o640)
            table = read_csv_table(path)
            ensure_result_columns(table)
            write_csv_table(table)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            leftovers = [p.name for p in Path(td).iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [])

    def test_gb18030_is_written_back(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.csv"
            path.write_bytes("代码,名称\n600519,贵州茅台\n".encode("gb18030"))
            table = read_csv_table(path)
            ensure_result_columns(table)
            table.rows[0][SCORE_COLUMN] = "观察"
            write_csv_table(table)
            text = path.read_bytes().decode("gb18030")
            self.assertIn("观察", text)
            self.assertIn("贵州茅台", text)


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


class XlsxTest(unittest.TestCase):
    def _table(self, td):
        out = Path(td) / "reports"
        out.mkdir()
        report = out / "报告.html"
        report.write_text("<html>ok</html>", encoding="utf-8")
        csv_path = Path(td) / "rows.csv"
        csv_path.write_bytes("\ufeff代码,名称\r\n600519,贵州茅台\r\n000001,平安银行\r\n".encode())
        table = read_csv_table(csv_path)
        ensure_result_columns(table)
        table.rows[0][SCORE_COLUMN] = "可买"
        table.rows[0][LINK_COLUMN] = report_link_cell(report)
        table.rows[0][EASTMONEY_COLUMN] = eastmoney_link_cell("600519")
        table.rows[1][SCORE_COLUMN] = "生成失败"
        table.rows[1][LINK_COLUMN] = ""
        return table, out

    def test_sheet_and_rels(self):
        with tempfile.TemporaryDirectory() as td:
            table, _ = self._table(td)
            xlsx = write_report_xlsx(table)
            self.assertTrue(xlsx.is_file())
            with zipfile.ZipFile(xlsx) as zf:
                names = set(zf.namelist())
                sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
                rels = zf.read("xl/worksheets/_rels/sheet1.xml.rels").decode("utf-8")
            for part in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                         "xl/styles.xml", "xl/worksheets/sheet1.xml"):
                self.assertIn(part, names)
            self.assertIn("报告链接", sheet)
            self.assertIn("东方财富网股票详情", sheet)
            self.assertIn("可买", sheet)
            self.assertIn("<hyperlink", sheet)
            self.assertIn("autoFilter", sheet)
            self.assertIn("file:///", rels)
            self.assertIn("https://quote.eastmoney.com/sh600519.html", rels)

    def test_missing_report_link_shows_dash(self):
        with tempfile.TemporaryDirectory() as td:
            table, _ = self._table(td)
            xlsx = write_report_xlsx(table)
            with zipfile.ZipFile(xlsx) as zf:
                sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("—", sheet)

    def test_custom_output_path(self):
        with tempfile.TemporaryDirectory() as td:
            table, _ = self._table(td)
            target = Path(td) / "nested" / "结果.xlsx"
            self.assertEqual(write_report_xlsx(table, target), target)
            self.assertTrue(target.is_file())


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

    def test_code_and_name_are_escaped(self):
        with tempfile.TemporaryDirectory() as td:
            table, out = self._table(td)
            table.rows[0][table.code_column] = "600519<script>"
            index = write_index_html(table, out)
            text = index.read_text(encoding="utf-8")
            # 导航页自带搜索用的 <script>，这里只检查注入内容被转义进单元格
            self.assertIn('<td class="code">600519&lt;script&gt;</td>', text)
            self.assertNotIn("600519<script>", text)


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


class CodeColumnCandidatesTest(unittest.TestCase):
    def test_candidate_set_is_case_insensitive_friendly(self):
        lowered = {c.casefold() for c in CODE_COLUMN_CANDIDATES}
        for expected in ("代码", "股票代码", "证券代码", "code", "stock_code", "ts_code"):
            self.assertIn(expected.casefold(), lowered)


if __name__ == "__main__":
    unittest.main()
