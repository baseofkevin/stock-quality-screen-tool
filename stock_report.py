#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业质量初筛 CLI。

单股票：
    python3 stock_report.py --stock-code 600519
    python3 stock_report.py --stock-code 301101 --out-dir /tmp/初筛
    python3 stock_report.py --stock-code 600519 --bundle tests/fixtures/mini_bundle.json

批量（读取 CSV 中的股票代码，多线程生成报告并回写 CSV）：
    python3 stock_report.py --csv-input ../stock-kline-screen-tool/csv_output/选股_2026-11-06.csv
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from screen.batch import (  # noqa: E402
    LINK_COLUMN,
    SCORE_COLUMN,
    CsvError,
    ReportResult,
    ensure_result_columns,
    read_csv_table,
    report_uri,
    write_csv_table,
)
from screen.compute import build_report_data  # noqa: E402
from screen.fetch import DataError, fetch_all, load_bundle, normalize_code  # noqa: E402
from screen.render import render_html  # noqa: E402
from screen.score import compute_scores  # noqa: E402
from screen.summary import SummaryError, extract_score_summary  # noqa: E402
from screen.validate import ScreenError, validate  # noqa: E402


def _safe_name(value: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value)).strip(" .")
    return s or "企业"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _link_path(link: str) -> Path | None:
    """把 CSV 里的 file:/// 链接还原成本地路径。"""
    link = (link or "").strip()
    if not link:
        return None
    if link.startswith("file://"):
        parsed = urlparse(link)
        if parsed.scheme != "file":
            return None
        try:
            return Path(url2pathname(parsed.path))
        except ValueError:
            return None
    p = Path(os.path.expanduser(link))
    return p if p.is_absolute() else None


def _find_existing_report(out_dir: Path, code: str) -> Path | None:
    """在输出目录里找该股票最新的一份完整报告。"""
    if not out_dir.is_dir():
        return None
    marker = f"-{code}-"
    matches = [
        p for p in out_dir.glob("*-企业质量初筛-*.html")
        if marker in p.name and p.is_file()
    ]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def _existing_report(row: dict[str, str], out_dir: Path, code: str) -> Path | None:
    linked = _link_path(row.get(LINK_COLUMN, ""))
    if linked is not None and linked.is_file():
        return linked
    return _find_existing_report(out_dir, code)


def _save_csv(table) -> bool:
    try:
        write_csv_table(table)
        return True
    except CsvError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="企业质量初筛：质量 + 估值 + 机构预期，输出 HTML；支持 CSV 批量"
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--stock-code", help="股票代码，如 600519 / sh600519 / 600519.SH")
    source.add_argument(
        "--csv-input",
        help="批量模式：CSV 路径，读取其中的股票代码，生成报告并回写 CSV",
    )
    p.add_argument("--out-dir", default=config.DEFAULT_OUT_DIR, help=f"输出目录，默认 {config.DEFAULT_OUT_DIR}")
    p.add_argument("--name", default="", help="覆盖报告文件名中的公司名（仅单股票模式）")
    p.add_argument("--bundle", default="", help="离线采集包路径（旧 raw JSON），不发起网络请求")
    p.add_argument("--timeout", type=float, default=90.0, help="单次取数超时秒数，默认 90")
    p.add_argument("--workers", type=int, default=4, help="批量模式并发线程数，默认 4")
    p.add_argument("--retries", type=int, default=2,
                   help="取数失败后的重试次数（限频 / 非 JSON / 超时），默认 2")
    p.add_argument("--retry-wait", type=float, default=60.0,
                   help="重试前等待秒数，默认 60")
    p.add_argument("--force", action="store_true",
                   help="批量模式忽略已有报告，全部重新生成")
    p.add_argument("--quiet", action="store_true", help="只输出错误")
    return p


def _generate_report(
    stock_code: str,
    *,
    out_dir: Path,
    bundle: str,
    timeout: float,
    name_override: str = "",
    with_code: bool = False,
    stamp: str | None = None,
    need_summary: bool = False,
    retries: int = 0,
    retry_wait: float = 60.0,
) -> ReportResult:
    """抓数、计算、渲染并落盘一只股票；供单股票和批量线程共用。"""
    if bundle:
        raw = load_bundle(bundle)
    else:
        raw = fetch_all(stock_code, timeout=timeout, retries=retries,
                        retry_wait=retry_wait)
    data = build_report_data(raw["calls"], raw["code"])
    data["data_gaps"] = raw.get("errors") or []
    data = compute_scores(data)
    validate(data)
    html_text = render_html(data)

    name = name_override.strip() or data["meta"].get("name") or data["meta"]["code"]
    code = data["meta"]["code"]
    report_stamp = stamp or f"{datetime.now():%Y%m%d-%H%M%S}"
    base = _safe_name(name)
    if with_code:
        base = f"{base}-{code}"
    filename = f"{base}-企业质量初筛-{report_stamp}.html"
    target = out_dir / filename

    summary = None
    summary_error = ""
    if need_summary:
        try:
            summary = extract_score_summary(html_text)
        except SummaryError as exc:
            summary_error = str(exc)

    _write_atomic(target, html_text)
    return ReportResult(
        code=code,
        name=name,
        target=target,
        summary=summary,
        summary_error=summary_error,
        data=data,
        html_text=html_text,
        gaps=raw.get("errors") or [],
    )


def _run_single(args: argparse.Namespace) -> int:
    out_dir = Path(os.path.expanduser(args.out_dir)).resolve()
    try:
        result = _generate_report(
            args.stock_code,
            out_dir=out_dir,
            bundle=args.bundle,
            timeout=args.timeout,
            name_override=args.name,
            retries=args.retries,
            retry_wait=args.retry_wait,
        )
    except (DataError, ScreenError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"未预期错误：{exc}", file=sys.stderr)
        return 3

    data = result.data or {}
    target = result.target
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
        if result.gaps:
            print("  数据缺口：" + "；".join(
                f"{x.get('tool')}: {x.get('error')}" for x in result.gaps[:4]
            ))
    return 0


def _apply_result(table, indices: list[int], result: ReportResult) -> None:
    for index in indices:
        row = table.rows[index]
        if result.error:
            row[SCORE_COLUMN] = "生成失败"
            row[LINK_COLUMN] = ""
        elif result.summary is None:
            row[SCORE_COLUMN] = "评分提取失败"
            row[LINK_COLUMN] = report_uri(result.target) if result.target else ""
        else:
            row[SCORE_COLUMN] = result.summary.conclusion
            row[LINK_COLUMN] = report_uri(result.target) if result.target else ""


def _run_batch(args: argparse.Namespace) -> int:
    if args.bundle:
        print("错误：--csv-input 批量模式不支持 --bundle（每个股票需要实时取数）", file=sys.stderr)
        return 2
    if args.name:
        print("错误：--csv-input 批量模式不能使用 --name（每只股票使用自身公司名）", file=sys.stderr)
        return 2
    if args.workers < 1:
        print("错误：--workers 必须大于等于 1", file=sys.stderr)
        return 2

    try:
        table = read_csv_table(args.csv_input)
        ensure_result_columns(table)
    except CsvError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    row_codes: dict[int, str] = {}
    row_errors: dict[int, str] = {}
    unique_codes: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(table.rows):
        raw_code = (row.get(table.code_column) or "").strip()
        if not raw_code:
            row_errors[index] = "缺少股票代码"
            continue
        try:
            code = normalize_code(raw_code)
        except ValueError as exc:
            row_errors[index] = str(exc)
            continue
        row_codes[index] = code
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)

    code_rows: dict[str, list[int]] = {}
    for index, code in row_codes.items():
        code_rows.setdefault(code, []).append(index)

    out_dir = Path(os.path.expanduser(args.out_dir)).resolve()
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"

    # 先扫描已有报告：中断后重跑时不重新抓数，只补缺失的股票。
    pending_codes: list[str] = []
    reused_rows = 0
    reused_codes = 0
    for code in unique_codes:
        indices = code_rows[code]
        existing = None if args.force else _existing_report(table.rows[indices[0]], out_dir, code)
        summary = None
        if existing is not None:
            try:
                summary = extract_score_summary(existing.read_text(encoding="utf-8"))
            except (OSError, SummaryError) as exc:
                if not args.quiet:
                    print(f"已有报告不可用，重新生成 {existing.name}：{exc}", file=sys.stderr)
                existing = None
        if existing is not None and summary is not None:
            for index in indices:
                table.rows[index][SCORE_COLUMN] = summary.conclusion
                table.rows[index][LINK_COLUMN] = report_uri(existing)
            reused_codes += 1
            reused_rows += len(indices)
        else:
            pending_codes.append(code)
            for index in indices:
                table.rows[index][SCORE_COLUMN] = ""
                table.rows[index][LINK_COLUMN] = ""

    for index, error in row_errors.items():
        table.rows[index][SCORE_COLUMN] = "代码无效" if "应为" in error else error
        table.rows[index][LINK_COLUMN] = ""

    write_ok = _save_csv(table)
    if not args.quiet:
        if args.force:
            print("--force：忽略已有报告，全部重新生成")
        if reused_codes:
            print(f"已有报告 {reused_codes} 只（{reused_rows} 行），跳过；"
                  f"待生成 {len(pending_codes)} 只")
        else:
            print(f"待生成 {len(pending_codes)} 只股票")

    done_count = 0
    if pending_codes:
        pool = ThreadPoolExecutor(max_workers=args.workers)
        futures = {
            pool.submit(
                _generate_report,
                code,
                out_dir=out_dir,
                bundle="",
                timeout=args.timeout,
                with_code=True,
                stamp=stamp,
                need_summary=True,
                retries=args.retries,
                retry_wait=args.retry_wait,
            ): code
            for code in pending_codes
        }
        total = len(futures)
        try:
            for done, future in enumerate(as_completed(futures), 1):
                code = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = ReportResult(code=code, error=str(exc))
                    print(f"[{done:>3}/{total}] {code} 生成失败：{exc}", file=sys.stderr)
                _apply_result(table, code_rows[code], result)
                done_count += 1
                # 每完成一只就落一次 CSV，Ctrl-C 时已完成进度不会丢。
                write_ok = _save_csv(table) and write_ok
                if not args.quiet:
                    if result.summary is not None:
                        print(f"[{done:>3}/{total}] {result.name} {code}  "
                              f"{result.summary.conclusion}")
                    elif not result.error:
                        print(f"[{done:>3}/{total}] {result.name} {code}  "
                              f"报告已生成，评分提取失败")
                if result.summary_error:
                    print(f"[{done:>3}/{total}] {code} 评分提取失败：{result.summary_error}",
                          file=sys.stderr)
        except KeyboardInterrupt:
            for future in futures:
                future.cancel()
            pool.shutdown(wait=False, cancel_futures=True)
            write_ok = _save_csv(table) and write_ok
            print("\n已中断：本次已完成的报告和 CSV 进度已保存；"
                  "重新运行会跳过已有报告。", file=sys.stderr)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(130)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    ok = 0
    failed = 0
    for index, row in enumerate(table.rows):
        if index in row_errors:
            failed += 1
        elif row.get(SCORE_COLUMN) in ("", "生成失败", "评分提取失败"):
            failed += 1
        else:
            ok += 1

    if not write_ok:
        print("错误：CSV 回写失败；HTML 报告已保留，修复后可重新运行。", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"\n批量完成：成功 {ok} 行（复用 {reused_rows} 行），失败 {failed} 行，"
              f"共 {len(table.rows)} 行；股票 {len(unique_codes)} 只")
        if pending_codes:
            print(f"  本次生成 {done_count}/{len(pending_codes)} 只")
        print(f"  CSV      {table.path}")
        print(f"  报告目录 {out_dir}")
        print(f"  新增列   {SCORE_COLUMN} / {LINK_COLUMN}")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.retries < 0:
        print("错误：--retries 不能小于 0", file=sys.stderr)
        return 2
    if args.retry_wait < 0:
        print("错误：--retry-wait 不能小于 0", file=sys.stderr)
        return 2
    try:
        if args.csv_input:
            return _run_batch(args)
        return _run_single(args)
    except KeyboardInterrupt:
        print("\n已中断。批量模式下重新运行同一条命令即可从已有报告继续。",
              file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
