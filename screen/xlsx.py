# -*- coding: utf-8 -*-
"""把批量结果写成带真正超链接按钮的 XLSX。

CSV 只能存文本，无法同时做到「只显示 报告链接」和「点击打开文件」。
XLSX 支持单元格超链接和样式，所以批量模式额外生成一份同名 .xlsx：
链接列显示为「报告链接」按钮，点击直接打开对应 HTML。
"""
from __future__ import annotations

import os
import re
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from screen.batch import (EASTMONEY_COLUMN, EASTMONEY_LINK_TEXT,
                          LINK_COLUMN, SCORE_COLUMN, CsvTable, link_target)

_NUM_RE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
_LINK_TEXT = "报告链接"
_HYPERLINK_TEXT = {
    LINK_COLUMN: _LINK_TEXT,
    EASTMONEY_COLUMN: EASTMONEY_LINK_TEXT,
}


def _col_letter(number: int) -> str:
    """1 → A, 27 → AA。"""
    result = ""
    while number > 0:
        number, rem = divmod(number - 1, 26)
        result = chr(65 + rem) + result
    return result


def _target_uri(cell: str, base_dir: Path) -> str | None:
    target = link_target(cell)
    if not target:
        return None
    if target.lower().startswith(("http://", "https://", "file://")):
        return target
    path = Path(os.path.expanduser(target))
    if not path.is_absolute():
        path = base_dir / path
    try:
        resolved = path.resolve()
    except OSError:
        return None
    return resolved.as_uri() if resolved.is_file() else None


def _cell(ref: str, style: int, value: str, *, text: bool = True) -> str:
    if not text and value and _NUM_RE.fullmatch(value):
        return f'<c r="{ref}" s="{style}"><v>{escape(value)}</v></c>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(value)}</t></is></c>')


def _display_width(value: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in value)


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><color rgb="FF1F2933"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F5F8B"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD0D7DE"/></left>
      <right style="thin"><color rgb="FFD0D7DE"/></right>
      <top style="thin"><color rgb="FFD0D7DE"/></top>
      <bottom style="thin"><color rgb="FFD0D7DE"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="5">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center" wrapText="1"/>
    </xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">
      <alignment vertical="center" wrapText="1"/>
    </xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center" wrapText="1"/>
    </xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/>
  <tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>"""


def _workbook_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="28800" windowHeight="16000"/></bookViews>
  <sheets><sheet name="选股报告" sheetId="1" r:id="rId1"/></sheets>
  <calcPr calcId="0"/>
</workbook>"""


def _workbook_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def write_report_xlsx(table: CsvTable, path: str | Path | None = None) -> Path:
    """生成同名 XLSX：保留全部列，链接列显示为「报告链接」按钮。"""
    target = Path(path).resolve() if path else table.path.with_suffix(".xlsx")
    target.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(table.fieldnames)
    if LINK_COLUMN not in fieldnames:
        fieldnames.append(LINK_COLUMN)
    link_index = fieldnames.index(LINK_COLUMN) + 1
    score_index = fieldnames.index(SCORE_COLUMN) + 1 if SCORE_COLUMN in fieldnames else 0

    # 列宽：取表头和样本内容的最大显示宽度，限制在 8~48。
    widths: list[int] = []
    for name in fieldnames:
        values = [str(row.get(name, "")) for row in table.rows[:40]]
        width = max([_display_width(str(name))] + [_display_width(v) for v in values])
        if name == LINK_COLUMN:
            width = 14
        elif name == EASTMONEY_COLUMN:
            width = 24
        elif name == SCORE_COLUMN:
            width = 18
        widths.append(max(8, min(48, width + 2)))

    cols = "".join(
        f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
        for i, w in enumerate(widths, 1)
    )

    header_cells = "".join(
        _cell(f"{_col_letter(i)}1", 1,
              "报告链接" if name == LINK_COLUMN else str(name))
        for i, name in enumerate(fieldnames, 1)
    )
    rows_xml = [f'<row r="1" ht="24" customHeight="1">{header_cells}</row>']

    hyperlinks: list[tuple[str, str]] = []
    for row_number, row in enumerate(table.rows, 2):
        cells = []
        for col_number, name in enumerate(fieldnames, 1):
            ref = f"{_col_letter(col_number)}{row_number}"
            value = str(row.get(name, ""))
            if name in _HYPERLINK_TEXT:
                uri = _target_uri(value, table.path.parent)
                if uri:
                    cells.append(_cell(ref, 3, _HYPERLINK_TEXT[name]))
                    hyperlinks.append((ref, uri))
                else:
                    cells.append(_cell(ref, 2, "—"))
                continue
            style = 4 if col_number in {1, score_index} else 2
            cells.append(_cell(ref, style, value, text=False))
        rows_xml.append(f'<row r="{row_number}" ht="20" customHeight="1">{"".join(cells)}</row>')

    last_row = len(table.rows) + 1
    last_col = _col_letter(len(fieldnames))
    hyperlink_xml = ""
    rels_xml = ""
    if hyperlinks:
        items = []
        rel_items = []
        for index, (ref, uri) in enumerate(hyperlinks, 1):
            rid = f"rId{index}"
            items.append(f'<hyperlink ref="{ref}" r:id="{rid}"/>')
            rel_items.append(
                f'<Relationship Id="{rid}" '
                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                f'Target={quoteattr(uri)} TargetMode="External"/>'
            )
        hyperlink_xml = "<hyperlinks>" + "".join(items) + "</hyperlinks>"
        rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rel_items) + "</Relationships>"
        )

    sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:{last_col}{last_row}"/>
  <sheetViews>
    <sheetView tabSelected="1" workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
      <selection pane="bottomLeft" activeCell="A2" sqref="A2"/>
    </sheetView>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="20"/>
  <cols>{cols}</cols>
  <sheetData>{"".join(rows_xml)}</sheetData>
  <autoFilter ref="A1:{last_col}{last_row}"/>
  {hyperlink_xml}
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>"""

    tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", _content_types_xml())
            zf.writestr("_rels/.rels", _root_rels_xml())
            zf.writestr("xl/workbook.xml", _workbook_xml())
            zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml())
            zf.writestr("xl/styles.xml", _styles_xml())
            zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
            if rels_xml:
                zf.writestr("xl/worksheets/_rels/sheet1.xml.rels", rels_xml)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return target
