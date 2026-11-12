"""W0/W1 自检：不依赖 API key，验证流式、重试、usage 与错误提示。

    python w1/selftest.py
"""
from __future__ import annotations

import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import llm_ping  # noqa: E402
import mock_server  # noqa: E402


def start_mock():
    httpd = mock_server.serve(0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> int:
    httpd = start_mock()
    base = f"http://127.0.0.1:{httpd.server_port}"
    passed: list[str] = []
    failed: list[str] = []

    def check(name: str, fn):
        try:
            fn()
            passed.append(name)
            print(f"PASS  {name}")
        except AssertionError as e:
            failed.append(f"{name}: {e}")
            print(f"FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed.append(f"{name}: {type(e).__name__}: {e}")
            print(f"ERROR {name}: {type(e).__name__}: {e}")

    # 1) 流式 + 首次 500 自动重试
    def t_stream_retry():
        r = llm_ping.chat("hi", base=base, key="test", stream=True, max_retries=2, proxy=None)
        assert "mock" in r["content"], f"流式内容异常: {r['content']!r}"
        assert r["attempts"] == 2, f"应重试 1 次，实际 attempts={r['attempts']}"
        assert r["usage"] and r["usage"]["total_tokens"] == 20, r["usage"]

    # 2) 非流式 + usage
    def t_nonstream():
        r = llm_ping.chat("hi", base=base, key="test", stream=False, max_retries=0, proxy=None)
        assert r["content"].startswith("你好"), r["content"]
        assert r["usage"]["total_tokens"] == 16, r["usage"]

    # 3) 401 可读提示
    def t_401():
        try:
            llm_ping.chat("hi", base=base, key="bad", max_retries=0, proxy=None)
        except llm_ping.PingError as e:
            assert "401" in str(e) and "API_KEY" in str(e), str(e)
            return
        raise AssertionError("401 应该抛 PingError")

    # 4) 费用计算
    def t_cost():
        money = llm_ping.cost_of({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}, 1.0, 2.0)
        assert abs(money - 3.0) < 1e-9, money
        assert llm_ping.cost_of({"prompt_tokens": 1}, 0, 0) is None

    check("流式 + 500 自动重试 + usage", t_stream_retry)
    check("非流式 + usage", t_nonstream)
    check("401 错误提示可读", t_401)
    check("费用计算", t_cost)

    httpd.shutdown()
    print("---")
    print(f"通过 {len(passed)} / 4")
    if failed:
        for item in failed:
            print("  未通过:", item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
