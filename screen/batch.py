# -*- coding: utf-8 -*-
"""批量模式的 CSV 读写与单股票结果结构。

CSV 只做两件事：读出股票代码；在原有列后面追加/更新「综合评分」和
「HTML报告链接」。不重排、不删除用户原有的列和行。
"""
from __future__ import annotations

import codecs
import csv
import io
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from screen.summary import ScoreSummary

SCORE_COLUMN = "综合评分"
LINK_COLUMN = "HTML报告链接"

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
    """CSV 无法读取或回写。"""


@dataclass
class CsvTable:
    path: Path
    fieldnames: list[str]
    rows: list[dict[str, str]]
    code_column: str
    encoding: str
    lineterminator: str
    mode: int


@dataclass
class ReportResult:
    """单只股票的生成结果；批量线程只返回对象，不直接写 CSV。"""

    code: str
    name: str = ""
    target: Path | None = None
    summary: ScoreSummary | None = None
    summary_error: str = ""
    data: dict[str, Any] | None = None
    html_text: str = ""
    gaps: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def _clean_header(value: Any) -> str:
    return str(value or "").strip().lstrip("\ufeff")


def _decode(data: bytes) -> tuple[str, str]:
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig"), "utf-8-sig"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        try:
            return data.decode("gb18030"), "gb18030"
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
    """读取 CSV，保留原表头、行顺序、编码和换行符。"""
    p = Path(os.path.expanduser(str(path))).resolve()
    if not p.is_file():
        raise CsvError(f"CSV 文件不存在：{p}")
    try:
        data = p.read_bytes()
        mode = p.stat().st_mode
    except OSError as exc:
        raise CsvError(f"CSV 读取失败：{exc}") from exc
    text, encoding = _decode(data)
    lineterminator = "\r\n" if b"\r\n" in data else "\n"

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
        encoding=encoding,
        lineterminator=lineterminator,
        mode=mode,
    )


def ensure_result_columns(table: CsvTable) -> None:
    """在表头末尾补上结果列；重复运行时复用已有列。"""
    for name in (SCORE_COLUMN, LINK_COLUMN):
        if name not in table.fieldnames:
            table.fieldnames.append(name)
        for row in table.rows:
            row.setdefault(name, "")


def write_csv_table(table: CsvTable) -> None:
    """原子回写 CSV，保留原文件权限。"""
    tmp = table.path.with_name(f".{table.path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding=table.encoding, newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=table.fieldnames,
                extrasaction="ignore",
                lineterminator=table.lineterminator,
            )
            writer.writeheader()
            for row in table.rows:
                writer.writerow({name: row.get(name, "") for name in table.fieldnames})
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, table.mode)
        os.replace(tmp, table.path)
    except OSError as exc:
        raise CsvError(f"CSV 回写失败：{exc}") from exc
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def report_uri(path: str | Path) -> str:
    """绝对 file:/// 链接，可直接在 Excel / LibreOffice 中点击。"""
    return Path(path).resolve().as_uri()
