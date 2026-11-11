# -*- coding: utf-8 -*-
"""东方财富取数层：号段换算、跨线程节流（providers/eastmoney.py）。"""
import io
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providers.eastmoney as em  # noqa: E402


class ThrottleTest(unittest.TestCase):
    def setUp(self):
        self._saved = em.GLOBAL_INTERVAL

    def tearDown(self):
        em.set_interval_ms(self._saved * 1000)

    def test_zero_interval_does_not_sleep(self):
        em.set_interval_ms(0)
        start = time.monotonic()
        for _ in range(20):
            em._throttle()
        self.assertLess(time.monotonic() - start, 0.1)

    def test_interval_spaces_calls(self):
        em.set_interval_ms(60)
        start = time.monotonic()
        em._throttle()
        em._throttle()
        self.assertGreaterEqual(time.monotonic() - start, 0.055)

    def test_get_throttles_each_request(self):
        """节流挂在 _get 里：翻页的每一次请求都要等，不能整只股票只等一次。"""
        payload = json.dumps({"result": {"data": [], "pages": 3}}).encode()

        class FakeResp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        calls = []
        with patch.object(em, "_throttle", side_effect=lambda: calls.append(1)), \
                patch("urllib.request.urlopen", side_effect=lambda *a, **k: FakeResp(payload)):
            em._fetch_pages("RPT_TEST", "A", "(X=1)", page_size=1)
        self.assertEqual(len(calls), 3)      # 首页 + 2 页

    def test_env_interval(self):
        with patch.dict("os.environ", {"EASTMONEY_GLOBAL_INTERVAL_MS": "0"}):
            self.assertEqual(em._env_interval(), 0.0)
        with patch.dict("os.environ", {"EASTMONEY_GLOBAL_INTERVAL_MS": "250"}):
            self.assertAlmostEqual(em._env_interval(), 0.25)
        with patch.dict("os.environ", {"EASTMONEY_GLOBAL_INTERVAL_MS": "abc"}):
            self.assertAlmostEqual(em._env_interval(), 0.4)


class FetchErrorTest(unittest.TestCase):
    def test_failures_become_data_gap_not_exception(self):
        """东财失败只记数据缺口：fetch_valuation 返回 ok=False，不抛给上层。"""
        with patch.object(em, "_fetch_pages", side_effect=em.EastMoneyError("限频")):
            result = em.fetch_valuation("600519")
        self.assertFalse(result["ok"])
        self.assertEqual(result["rows"], [])
        self.assertIn("限频", result["error"])

    def test_secucode_is_passed_to_api(self):
        with patch.object(em, "_fetch_pages", return_value={"pages": 1, "rows": []}) as fake:
            em.fetch_valuation("sh600519")
        filter_text = fake.call_args.args[2]      # _fetch_pages(report, columns, filter_text, ...)
        self.assertIn('SECUCODE="600519.SH"', filter_text)


if __name__ == "__main__":
    unittest.main()
