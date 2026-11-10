# -*- coding: utf-8 -*-
"""取数层：代码归一、采集包加载、重试与限频（screen/fetch.py）。"""
import json
import os
import tempfile
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pathlib import Path
from unittest.mock import patch

import support
from screen import fetch
from screen.fetch import (DataError, WestockClient, call_map, load_bundle,
                          normalize_code, six)


class NormalizeCodeTest(unittest.TestCase):
    def test_accepts_common_forms(self):
        self.assertEqual(normalize_code("600519"), "sh600519")
        self.assertEqual(normalize_code("SH600519"), "sh600519")
        self.assertEqual(normalize_code("sh600519"), "sh600519")
        self.assertEqual(normalize_code("600519.SH"), "sh600519")
        self.assertEqual(normalize_code("600519.sh"), "sh600519")
        self.assertEqual(normalize_code(" 600519 "), "sh600519")

    def test_market_prefix_by_first_digit(self):
        self.assertEqual(normalize_code("000001"), "sz000001")
        self.assertEqual(normalize_code("300059"), "sz300059")
        self.assertEqual(normalize_code("688111"), "sh688111")
        self.assertEqual(normalize_code("900901"), "sh900901")
        self.assertEqual(normalize_code("430047"), "bj430047")
        self.assertEqual(normalize_code("830799"), "bj830799")
        self.assertEqual(normalize_code("920001"), "bj920001")

    def test_explicit_prefix_is_trusted(self):
        # 用户显式给了市场前缀就按前缀走，不再按首位推断
        self.assertEqual(normalize_code("sz600519"), "sz600519")
        self.assertEqual(normalize_code("bj600519"), "bj600519")

    def test_invalid_raises_value_error(self):
        for raw in ("", None, "60051", "6005190", "abcdef", "600519.XX", "sh600519.SH"):
            with self.assertRaises(ValueError, msg=raw):
                normalize_code(raw)

    def test_six_strips_prefix(self):
        self.assertEqual(six("sh600519"), "600519")
        self.assertEqual(six("600519"), "600519")


class EnvSecondsTest(unittest.TestCase):
    def test_reads_milliseconds_as_seconds(self):
        with patch.dict(os.environ, {"WESTOCK_GLOBAL_INTERVAL_MS": "1600"}):
            self.assertAlmostEqual(fetch._env_seconds_ms("WESTOCK_GLOBAL_INTERVAL_MS", 999), 1.6)

    def test_invalid_value_falls_back_to_default(self):
        with patch.dict(os.environ, {"WESTOCK_GLOBAL_INTERVAL_MS": "abc"}):
            self.assertAlmostEqual(fetch._env_seconds_ms("WESTOCK_GLOBAL_INTERVAL_MS", 1600), 1.6)

    def test_negative_is_clamped_to_zero(self):
        with patch.dict(os.environ, {"WESTOCK_GLOBAL_INTERVAL_MS": "-5"}):
            self.assertEqual(fetch._env_seconds_ms("WESTOCK_GLOBAL_INTERVAL_MS", 1600), 0.0)


class ThrottleTest(unittest.TestCase):
    def test_disabled_when_interval_zero(self):
        with patch.object(fetch, "GLOBAL_INTERVAL", 0):
            fetch._throttle()
            fetch._throttle()

    def test_second_call_waits_for_interval(self):
        with patch.object(fetch, "GLOBAL_INTERVAL", 0.05), \
                patch.object(fetch, "_NEXT_CALL_AT", 0.0):
            fetch._throttle()
            start = time.monotonic()
            fetch._throttle()
            self.assertGreaterEqual(time.monotonic() - start, 0.04)


class RetryableTest(unittest.TestCase):
    def test_temporary_errors_are_retryable(self):
        for text in ("返回不是 JSON", "服务限频", "HTTP 429", "请求超时",
                     "连接失败 ECONNRESET", "network error", "502 Bad Gateway"):
            self.assertTrue(fetch._is_retryable(DataError(text)), text)

    def test_logic_errors_are_not_retryable(self):
        for text in ("股票代码应为 600519", "没有权限", "参数错误"):
            self.assertFalse(fetch._is_retryable(DataError(text)), text)


class ClientRetryTest(unittest.TestCase):
    """重试策略：可重试错误按次数重试，间隔 = retry_wait + 0~5s 抖动。"""

    def setUp(self):
        # 重试会真的 sleep（retry_wait + random.uniform(0, 5)），测试里短路掉
        self._sleep = patch("screen.fetch.time.sleep").start()
        self.addCleanup(patch.stopall)

    def test_retries_then_succeeds(self):
        client = WestockClient(retries=2, retry_wait=0)
        with patch.object(client, "_call_once",
                          side_effect=[DataError("限频"), {"ok": True}]) as mocked:
            self.assertEqual(client.call("data_quote", {"code": "sh600519"}), {"ok": True})
        self.assertEqual(mocked.call_count, 2)
        self._sleep.assert_called_once()

    def test_gives_up_after_retries(self):
        client = WestockClient(retries=1, retry_wait=0)
        with patch.object(client, "_call_once", side_effect=DataError("限频")) as mocked:
            with self.assertRaises(DataError):
                client.call("data_quote", {"code": "sh600519"})
        self.assertEqual(mocked.call_count, 2)  # 首次 + 1 次重试

    def test_no_retry_for_non_retryable_error(self):
        client = WestockClient(retries=3, retry_wait=0)
        with patch.object(client, "_call_once", side_effect=DataError("参数错误")) as mocked:
            with self.assertRaises(DataError):
                client.call("data_quote", {"code": "sh600519"})
        self.assertEqual(mocked.call_count, 1)

    def test_no_retry_when_retries_zero(self):
        client = WestockClient(retries=0)
        with patch.object(client, "_call_once", side_effect=DataError("限频")) as mocked:
            with self.assertRaises(DataError):
                client.call("data_quote", {"code": "sh600519"})
        self.assertEqual(mocked.call_count, 1)


class LoadBundleTest(unittest.TestCase):
    def _write(self, path: Path, payload) -> Path:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_normalizes_code_and_keeps_errors(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(Path(td) / "b.json", {
                "code": "600519",
                "calls": [{"tool": "data_quote", "params": {"code": "600519"}, "response": {}}],
                "errors": [{"tool": "data_rating", "error": "限频"}],
            })
            bundle = load_bundle(path)
            self.assertEqual(bundle["code"], "sh600519")
            self.assertEqual(len(bundle["calls"]), 1)
            self.assertEqual(bundle["errors"][0]["tool"], "data_rating")

    def test_code_falls_back_to_call_params(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(Path(td) / "b.json", {
                "calls": [{"tool": "data_quote", "params": {"code": "300059"}, "response": {}}],
            })
            self.assertEqual(load_bundle(path)["code"], "sz300059")

    def test_missing_file_raises(self):
        with self.assertRaises(DataError):
            load_bundle(Path(tempfile.gettempdir()) / "不存在的采集包.json")

    def test_broken_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(DataError):
                load_bundle(path)

    def test_missing_calls_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(Path(td) / "b.json", {"code": "600519", "calls": []})
            with self.assertRaises(DataError):
                load_bundle(path)

    def test_missing_code_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(Path(td) / "b.json", {
                "calls": [{"tool": "data_quote", "params": {}, "response": {}}],
            })
            with self.assertRaises(DataError):
                load_bundle(path)


class CallMapTest(unittest.TestCase):
    def test_same_tool_keeps_last(self):
        calls = [
            {"tool": "data_quote", "response": {"n": 1}},
            {"tool": "data_finance", "response": {"n": 2}},
            {"tool": "data_quote", "response": {"n": 3}},
        ]
        mapped = call_map(calls)
        self.assertEqual(mapped["data_quote"]["response"]["n"], 3)
        self.assertEqual(mapped["data_finance"]["response"]["n"], 2)
        self.assertEqual(set(mapped), {"data_quote", "data_finance"})


if __name__ == "__main__":
    unittest.main()
