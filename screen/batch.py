# -*- coding: utf-8 -*-
"""批量模式的 CSV 读取与单股票结果结构。

CSV 只做一件事：**读出股票代码**，顺带把原始列留在内存里给导航页 / Excel 展示。
批量模式不写任何 CSV——输入表只读，结果只体现在三处产物上：
`html-report/` 里的 HTML、同目录的导航页、`xlsx-output/` 里的 Excel。
"""
from __future__ import annotations

import codecs
import csv
import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import config
from screen import codes
from screen.summary import ScoreSummary

SCORE_COLUMN = "综合评分"
LINK_COLUMN = "HTML报告链接"
EASTMONEY_COLUMN = "东方财富网股票详情"
EASTMONEY_LINK_TEXT = "东方财富网股票详情"

# 不满足硬门槛（上市不足 N 年）的股票在「综合评分」里写这个值：
# 既不是结论也不是失败，读者/下游脚本据此区分「没结论」和「取数出错」。
SKIP_SCORE_TEXT = f"跳过：上市不足 {config.MIN_ANNUAL_YEARS} 年"

# 兼容常见导出表头；比较时忽略大小写、空格和 BOM。
CODE_COLUMN_CANDIDATES = {
    "代码",
    "股票代码",
    "证券代码",
    "股票",
    "code",
    "stock_code",
    "stockcode",
    "symbol",
    "ts_code",
    "sec_code",
}


class CsvError(RuntimeError):
    """CSV 无法读取。"""


@dataclass
class CsvTable:
    """输入 CSV 的内存副本；只在进程内用，从不写回磁盘。"""

    path: Path
    fieldnames: list[str]
    rows: list[dict[str, str]]
    code_column: str


@dataclass
class ReportResult:
    """单只股票的生成结果；批量线程只返回对象，不直接写文件。"""

    code: str
    name: str = ""
    target: Path | None = None
    summary: ScoreSummary | None = None
    summary_error: str = ""
    data: dict[str, Any] | None = None
    html_text: str = ""
    gaps: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    skipped: bool = False          # 不满足处理条件（上市不足 3 年）：不算失败

    @property
    def ok(self) -> bool:
        return not self.error and not self.skipped


def _clean_header(value: Any) -> str:
    return str(value or "").strip().lstrip("\ufeff")


def _decode(data: bytes) -> str:
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise CsvError("CSV 编码无法识别（支持 UTF-8 / GB18030）") from exc


def _find_code_column(fieldnames: list[str]) -> str:
    lookup = {_clean_header(name).casefold(): name for name in fieldnames if _clean_header(name)}
    for candidate in CODE_COLUMN_CANDIDATES:
        key = candidate.casefold()
        if key in lookup:
            return lookup[key]
    shown = "、".join(_clean_header(name) for name in fieldnames if _clean_header(name))
    raise CsvError(
        "CSV 中找不到股票代码列（可用表头：代码 / 股票代码 / 证券代码 / code）；"
        f"当前表头：{shown or '（空）'}"
    )


def read_csv_table(path: str | Path) -> CsvTable:
    """读取 CSV，保留原表头与行顺序（只读，不回写）。"""
    p = Path(os.path.expanduser(str(path))).resolve()
    if not p.is_file():
        raise CsvError(f"CSV 文件不存在：{p}")
    try:
        data = p.read_bytes()
    except OSError as exc:
        raise CsvError(f"CSV 读取失败：{exc}") from exc
    text = _decode(data)

    reader = csv.DictReader(io.StringIO(text, newline=""))
    original_names = list(reader.fieldnames or [])
    if not original_names:
        raise CsvError("CSV 没有表头")
    fieldnames = [_clean_header(name) for name in original_names]
    if not any(fieldnames):
        raise CsvError("CSV 表头为空")
    code_column = _find_code_column(fieldnames)

    rows: list[dict[str, str]] = []
    for raw in reader:
        row: dict[str, str] = {}
        for original, name in zip(original_names, fieldnames):
            value = raw.get(original)
            row[name] = value if isinstance(value, str) else ""
        rows.append(row)
    if not rows:
        raise CsvError("CSV 没有数据行")
    return CsvTable(
        path=p,
        fieldnames=fieldnames,
        rows=rows,
        code_column=code_column,
    )


def ensure_result_columns(table: CsvTable) -> None:
    """在内存表头末尾补上结果列；重复运行时复用已有列。"""
    for name in (SCORE_COLUMN, LINK_COLUMN, EASTMONEY_COLUMN):
        if name not in table.fieldnames:
            table.fieldnames.append(name)
        for row in table.rows:
            row.setdefault(name, "")


_HYPERLINK_RE = re.compile(r'^=HYPERLINK\(\s*"([^"]+)"', re.I)


def eastmoney_url(raw_code: str) -> str:
    """sh600519 / 600519 / sz300059 → 东方财富个股页；无法识别返回空串。"""
    return codes.eastmoney_url(raw_code)


def eastmoney_link_cell(raw_code: str) -> str:
    url = eastmoney_url(raw_code)
    if not url:
        return ""
    return f'=HYPERLINK("{url}","{EASTMONEY_LINK_TEXT}")'


def report_uri(path: str | Path) -> str:
    """绝对 file:/// 链接（中文按 URL 规范编码）。"""
    return Path(path).resolve().as_uri()


def report_link_cell(path: str | Path) -> str:
    """写成 Excel / LibreOffice / WPS 都能点击的 HYPERLINK 公式。"""
    return f'=HYPERLINK("{report_uri(path)}","打开报告")'


def link_target(cell: str) -> str:
    """从 HYPERLINK 公式或普通文本中取出真正的 URL / 路径。"""
    text = (cell or "").strip()
    match = _HYPERLINK_RE.match(text)
    return match.group(1) if match else text
