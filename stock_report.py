#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业质量初筛 CLI。

单股票：
    python3 stock_report.py --stock-code 600519
    python3 stock_report.py --stock-code 301101 --out-dir /tmp/初筛
    python3 stock_report.py --stock-code 600519 --bundle tests/fixtures/mini_bundle.json

批量（读取 CSV 的代码列，多线程生成报告；输入 CSV 只读，不写任何 CSV）：
    python3 stock_report.py --csv ../stock-kline-screen-tool/csv_output/选股_2026-11-06.csv

批量产物只有两处：HTML 进 --out-dir（默认 html-report/）；同目录生成导航页
`<输入 CSV 主名>.html`。**输入 CSV 本身不会被改动**，指向只读表也安全；
批量不产出 CSV，也不产出 Excel：评分、链接与二级行业等扩展列只体现在导航页里。
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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from screen.batch import (  # noqa: E402
    EASTMONEY_COLUMN,
    LINK_COLUMN,
    SCORE_COLUMN,
    SKIP_SCORE_TEXT,
    CsvError,
    ReportResult,
    eastmoney_link_cell,
    ensure_result_columns,
    read_csv_table,
    report_link_cell,
)
from screen.compute import build_report_data  # noqa: E402
from screen.fetch import DataError, fetch_all, load_bundle, normalize_code, set_quiet  # noqa: E402
from screen.index_html import write_index_html  # noqa: E402
from screen.render import render_html  # noqa: E402
from screen.score import compute_scores  # noqa: E402
from screen.summary import SummaryError, extract_score_summary  # noqa: E402
from screen.validate import ScreenError, SkipStock, validate  # noqa: E402


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


def _find_existing_report(out_dir: Path, code: str) -> Path | None:
    """在输出目录里找该股票最新的一份完整报告（增量续跑的唯一依据）。"""
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="企业质量初筛：质量 + 估值 + 机构预期，输出 HTML；支持 CSV 批量"
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--stock-code", help="股票代码，如 600519 / sh600519 / 600519.SH")
    source.add_argument(
        "--csv", "--csv-input", dest="csv_input", metavar="CSV",
        help="批量模式：读取该 CSV 的代码列（代码 / 股票代码 / 证券代码 / code），逐只生成报告。"
             "输入 CSV 只读，不会被改动，也不会产出新的 CSV 或 Excel；评分、链接与"
             "二级行业等扩展列只体现在导航页（--out-dir 下的 <输入 CSV 主名>.html）里。"
             "--csv-input 是这个参数的旧名，行为完全一致。",
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


def _score_line(data: dict) -> str:
    """CLI 摘要里的 Q/V 那一行。

    金融股的 Q/V 是 None（not_applicable），直接 `f"{x:.1f}"` 会抛
    TypeError，所以这里显式区分“不适用”和“算不出来（—）”。
    两栏写法必须一致：Q 也不能一律打成「不适用」。
    """
    q_block = data.get("quality") or {}
    qs = q_block.get("score")
    if isinstance(qs, (int, float)):
        q_text = f"{qs:.1f} / 100"
    else:
        q_text = "不适用" if q_block.get("not_applicable") else "—"
    v_block = data.get("valuation_score") or {}
    vs = v_block.get("score")
    if isinstance(vs, (int, float)):
        v_text = f"{vs:.1f} / 100"
    else:
        v_text = "不适用" if v_block.get("not_applicable") else "—"
    return f"  质量分 Q {q_text}   估值分 V {v_text}"


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
    except SkipStock as exc:
        # 不是错误：不满足处理条件（上市不足 3 年），不生成报告，退出码 0
        print(f"跳过  {args.stock_code}：{exc}")
        return 0
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
        # 分母用「适用项」：金融股有 5 项口径不适用，算进分母会出现 6/14 这种假数字
        applicable = (dq.get("risk_total") or 0) - (dq.get("risk_na") or 0)
        print(f"已生成  {target}")
        print(_score_line(data))
        print(f"  数据    风险检查 {dq.get('risk_known', '—')}/{applicable or '—'}；"
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
        if result.skipped:
            row[SCORE_COLUMN] = SKIP_SCORE_TEXT
            row[LINK_COLUMN] = ""
        elif result.error:
            row[SCORE_COLUMN] = "生成失败"
            row[LINK_COLUMN] = ""
        elif result.summary is None:
            row[SCORE_COLUMN] = "评分提取失败"
            row[LINK_COLUMN] = report_link_cell(result.target) if result.target else ""
        else:
            row[SCORE_COLUMN] = result.summary.conclusion
            row[LINK_COLUMN] = report_link_cell(result.target) if result.target else ""


def _run_batch(args: argparse.Namespace) -> int:
    if args.bundle:
        print("错误：批量模式（--csv）不支持 --bundle（每个股票需要实时取数）", file=sys.stderr)
        return 2
    if args.name:
        print("错误：批量模式（--csv）不能使用 --name（每只股票使用自身公司名）", file=sys.stderr)
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
        table.rows[index][EASTMONEY_COLUMN] = eastmoney_link_cell(code)
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
        # 续跑只看输出目录里已有的报告（带代码的文件名），不依赖任何 CSV
        existing = None if args.force else _find_existing_report(out_dir, code)
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
                table.rows[index][LINK_COLUMN] = report_link_cell(existing)
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
        table.rows[index][EASTMONEY_COLUMN] = ""

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
                except SkipStock as exc:
                    # 不填 error：跳过不是失败，error 只留给真错误
                    result = ReportResult(code=code, skipped=True)
                    if not args.quiet:
                        print(f"[{done:>3}/{total}] {code}  跳过：{exc}", file=sys.stderr)
                except Exception as exc:  # noqa: BLE001
                    result = ReportResult(code=code, error=str(exc))
                    print(f"[{done:>3}/{total}] {code} 生成失败：{exc}", file=sys.stderr)
                _apply_result(table, code_rows[code], result)
                done_count += 1
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
            try:
                write_index_html(table, out_dir)
            except Exception:
                pass
            print("\n已中断：本次已完成的报告已保存，导航页按已完成部分生成；"
                  "重新运行会跳过已有报告。", file=sys.stderr)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(130)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    ok = 0
    failed = 0
    skipped = 0
    for index, row in enumerate(table.rows):
        if index in row_errors:
            failed += 1
        elif row.get(SCORE_COLUMN) == SKIP_SCORE_TEXT:
            skipped += 1                      # 硬门槛跳过：不是失败，不影响退出码
        elif row.get(SCORE_COLUMN) in ("", "生成失败", "评分提取失败"):
            failed += 1
        else:
            ok += 1

    nav_path: Path | None = None
    try:
        nav_path = write_index_html(table, out_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"警告：导航页生成失败（HTML 报告不受影响）：{exc}", file=sys.stderr)

    if not args.quiet:
        print(f"\n批量完成：成功 {ok} 行（复用 {reused_rows} 行），失败 {failed} 行，"
              f"共 {len(table.rows)} 行；股票 {len(unique_codes)} 只")
        if skipped:
            print(f"  跳过 {skipped} 行（{SKIP_SCORE_TEXT}）")
        if pending_codes:
            print(f"  本次生成 {done_count}/{len(pending_codes)} 只")
        print(f"  输入 CSV {table.path}（只读，未改动）")
        print(f"  报告目录 {out_dir}")
        if nav_path is not None:
            print(f"  导航页   {nav_path}")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.retries < 0:
        print("错误：--retries 不能小于 0", file=sys.stderr)
        return 2
    if args.retry_wait < 0:
        print("错误：--retry-wait 不能小于 0", file=sys.stderr)
        return 2
    # --quiet 连取数层的重试警告一起静音（失败仍会记进数据缺口）
    set_quiet(args.quiet)
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
