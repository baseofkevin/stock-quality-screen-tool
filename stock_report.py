#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业质量初筛 CLI。

用法：
    python3 stock_report.py --stock-code 600519
    # 默认输出到项目目录下的 html-report/
    python3 stock_report.py --stock-code 301101 --out-dir /tmp/初筛
    python3 stock_report.py --stock-code 600519 --bundle tests/fixtures/mini_bundle.json
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from screen.compute import build_report_data  # noqa: E402
from screen.fetch import DataError, fetch_all, load_bundle  # noqa: E402
from screen.render import render_html  # noqa: E402
from screen.score import compute_scores  # noqa: E402
from screen.validate import ScreenError, validate  # noqa: E402


def _safe_name(value: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value)).strip(" .")
    return s or "企业"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="企业质量初筛：质量 + 估值 + 机构预期，输出单个 HTML")
    p.add_argument("--stock-code", required=True, help="股票代码，如 600519 / sh600519 / 600519.SH")
    p.add_argument("--out-dir", default=config.DEFAULT_OUT_DIR, help=f"输出目录，默认 {config.DEFAULT_OUT_DIR}")
    p.add_argument("--name", default="", help="覆盖报告文件名中的公司名")
    p.add_argument("--bundle", default="", help="离线采集包路径（旧 raw JSON），不发起网络请求")
    p.add_argument("--timeout", type=float, default=90.0, help="单次取数超时秒数，默认 90")
    p.add_argument("--quiet", action="store_true", help="只输出错误")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.bundle:
            raw = load_bundle(args.bundle)
        else:
            raw = fetch_all(args.stock_code, timeout=args.timeout)
        data = build_report_data(raw["calls"], raw["code"])
        data["data_gaps"] = raw.get("errors") or []
        data = compute_scores(data)
        validate(data)
        html_text = render_html(data)
    except (DataError, ScreenError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"未预期错误：{exc}", file=sys.stderr)
        return 3

    name = args.name.strip() or data["meta"].get("name") or data["meta"]["code"]
    out_dir = Path(os.path.expanduser(args.out_dir)).resolve()
    filename = f"{_safe_name(name)}-企业质量初筛-{datetime.now():%Y%m%d}.html"
    target = out_dir / filename
    _write_atomic(target, html_text)

    if not args.quiet:
        d = data["decision"]
        dq = data.get("data_quality") or {}
        vs = data["valuation_score"].get("score")
        v_text = f"{vs:.1f}" if vs is not None else "—"
        print(f"已生成  {target}")
        print(f"  质量分 Q {data['quality']['score']:.1f} / 100   "
              f"估值分 V {v_text} / 100")
        print(f"  数据    风险检查 {dq.get('risk_known', '—')}/{dq.get('risk_total', '—')}；"
              f"机构覆盖 {dq.get('institution_coverage', '—')} 家")
        print(f"  结论    {d['label']}（{d['reason']}）")
        print(f"  文件    {target.stat().st_size / 1024:.1f} KB")
        gaps = raw.get("errors") or []
        if gaps:
            print("  数据缺口：" + "；".join(f"{x.get('tool')}: {x.get('error')}" for x in gaps[:4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
