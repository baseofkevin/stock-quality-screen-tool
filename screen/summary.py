# -*- coding: utf-8 -*-
"""从生成的 HTML 报告里提取「四、综合评分」结论。

批量模式不重新计算分数，只解析已经落盘的 HTML；这样 CSV 里的结论
与用户打开报告看到的内容保持一致。

0.9.8 起报告给这三个数打了稳定标记：

    <div class="v" data-metric="q">62.7</div>

解析优先认标记，认不到才回退到「按小标题文字找」。回退这条路是给 0.9.7 及更早
生成的报告留的：批量模式会复用已有报告，改了字段名不该让老报告全都「评分提取失败」。
"""
from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass

class SummaryError(RuntimeError):
    """HTML 里找不到综合评分区，或字段为空。"""


@dataclass(frozen=True)
class ScoreSummary:
    quality: str
    valuation: str
    conclusion: str


_SECTION_RE = re.compile(
    r"<h2[^>]*>\s*四、综合评分\s*</h2>(.*?)</section>",
    re.S | re.I,
)

# 新路：只看属性，不关心标题文字和 DOM 层级
_MARKER_RE = re.compile(
    r'<div class="v"[^>]*data-metric="(q|v|conclusion)"[^>]*>(.*?)</div>',
    re.S,
)


def _clean(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html_module.unescape(text).strip()


def _metric(block: str, label: str) -> str:
    pattern = re.compile(
        rf'<div class="k">\s*{re.escape(label)}\s*</div>\s*'
        rf'<div class="v"[^>]*>(.*?)</div>',
        re.S,
    )
    match = pattern.search(block)
    return _clean(match.group(1)) if match else ""


def _legacy_metrics(html_text: str) -> dict[str, str]:
    """0.9.7 及更早的报告没有标记位，按小标题文字找。"""
    section = _SECTION_RE.search(html_text or "")
    if not section:
        raise SummaryError("HTML 中未找到「四、综合评分」区")
    block = section.group(1)
    return {
        "q": _metric(block, "质量分 Q"),
        "v": _metric(block, "估值分 V"),
        "conclusion": _metric(block, "结论"),
    }


def extract_score_summary(html_text: str) -> ScoreSummary:
    """解析 HTML 综合评分区，返回 Q 分、V 分和最终结论。"""
    text = html_text or ""
    marked = {m.group(1): _clean(m.group(2)) for m in _MARKER_RE.finditer(text)}
    values = marked if marked else _legacy_metrics(text)
    quality = values.get("q", "")
    valuation = values.get("v", "")
    conclusion = values.get("conclusion", "")
    if not quality:
        raise SummaryError("HTML 综合评分区缺少质量分 Q")
    if not valuation:
        raise SummaryError("HTML 综合评分区缺少估值分 V")
    if not conclusion:
        raise SummaryError("HTML 综合评分区缺少结论")
    return ScoreSummary(quality=quality, valuation=valuation, conclusion=conclusion)
