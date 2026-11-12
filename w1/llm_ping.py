"""W1 交付物：LLM 调用最小闭环。

覆盖：流式 / 重试（429、5xx、超时）/ 错误可读提示 / token 与费用统计。
依赖：仅标准库（W1 的后续任务是用 httpx 重写，对比差异）。

用法：
    python w1/llm_ping.py "用一句话解释什么是 agent"
    python w1/llm_ping.py "你好" --stream --max-retries 2
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from urllib import error, request

DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
RETRYABLE_HTTP = {429, 500, 502, 503, 504}


class PingError(RuntimeError):
    """带可读提示的调用失败。"""


def log(msg: str) -> None:
    print(f"[llm_ping] {msg}", file=sys.stderr)


def load_env(path: str) -> dict:
    cfg: dict = {}
    if not os.path.exists(path):
        return cfg
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def build_payload(model: str, prompt: str, stream: bool) -> bytes:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if stream:
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
    return json.dumps(payload).encode("utf-8")


def open_response(url: str, payload: bytes, key: str, proxy: str | None, timeout: int = 60):
    handlers = [request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
    opener = request.build_opener(*handlers)
    req = request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "Accept": "text/event-stream, application/json",
        },
        method="POST",
    )
    return opener.open(req, timeout=timeout)


def consume_stream(resp) -> tuple[str, dict | None]:
    """逐行解析 SSE，返回 (文本, usage)。"""
    chunks: list[str] = []
    usage = None
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        if obj.get("usage"):
            usage = obj["usage"]
        for choice in obj.get("choices", []):
            delta = choice.get("delta") or {}
            if delta.get("content"):
                chunks.append(delta["content"])
    return "".join(chunks), usage


def chat(
    prompt: str,
    *,
    base: str = DEFAULT_BASE,
    key: str = "",
    model: str = DEFAULT_MODEL,
    stream: bool = False,
    proxy: str | None = None,
    max_retries: int = 2,
) -> dict:
    url = base.rstrip("/") + "/chat/completions"
    payload = build_payload(model, prompt, stream)
    started = time.perf_counter()
    attempts = 0

    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        try:
            with open_response(url, payload, key, proxy) as resp:
                if stream:
                    content, usage = consume_stream(resp)
                else:
                    obj = json.load(resp)
                    content = obj["choices"][0]["message"]["content"]
                    usage = obj.get("usage")
            return {
                "content": content,
                "usage": usage,
                "attempts": attempts,
                "elapsed": round(time.perf_counter() - started, 2),
            }
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code in RETRYABLE_HTTP and attempt < max_retries:
                wait = 2 ** attempt
                log(f"HTTP {e.code}，{wait}s 后重试（第 {attempts} 次）")
                time.sleep(wait)
                continue
            if e.code == 401:
                raise PingError("401 鉴权失败：检查 .env 里的 API_KEY 是否正确或已过期") from e
            if e.code == 404:
                raise PingError(f"404 路径不存在：API_BASE 是否拼接正确？{base}") from e
            if e.code == 429:
                raise PingError("429 限流：降低频率、换 key，或稍后重试") from e
            raise PingError(f"HTTP {e.code}：{detail}") from e
        except (error.URLError, socket.timeout, TimeoutError) as e:
            reason = getattr(e, "reason", e)
            if attempt < max_retries:
                wait = 2 ** attempt
                log(f"网络异常（{reason}），{wait}s 后重试（第 {attempts} 次）")
                time.sleep(wait)
                continue
            raise PingError(f"网络不通：{reason}。检查 HTTPS_PROXY 或 DNS") from e

    raise PingError("超过最大重试次数")  # 理论上到不了


def cost_of(usage: dict | None, price_in: float, price_out: float) -> float | None:
    if not usage:
        return None
    if price_in <= 0 and price_out <= 0:
        return None
    return (
        usage.get("prompt_tokens", 0) / 1_000_000 * price_in
        + usage.get("completion_tokens", 0) / 1_000_000 * price_out
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="最小 LLM 调用：流式/重试/成本")
    parser.add_argument("prompt", nargs="?", default="用一句话解释什么是 AI agent")
    parser.add_argument("--stream", action="store_true", help="流式输出")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--base", default=None)
    parser.add_argument("--key", default=None)
    parser.add_argument("--model", default=None, help="模型名")
    parser.add_argument("--no-proxy", action="store_true", help="忽略 .env 里的代理")
    args = parser.parse_args(argv)

    env = load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
    base = args.base or env.get("API_BASE") or os.environ.get("API_BASE") or DEFAULT_BASE
    key = args.key or env.get("API_KEY") or os.environ.get("API_KEY", "")
    model = args.model or env.get("MODEL") or DEFAULT_MODEL
    proxy = None
    if not args.no_proxy:
        proxy = env.get("HTTPS_PROXY") or os.environ.get("HTTPS_PROXY") or None
    price_in = float(env.get("PRICE_INPUT_PER_M") or 0)
    price_out = float(env.get("PRICE_OUTPUT_PER_M") or 0)

    if not key:
        log("缺少 API_KEY：复制 .env.example 为 .env 并填写，或用 --key 传入")
        return 2

    try:
        result = chat(
            args.prompt,
            base=base,
            key=key,
            model=model,
            stream=args.stream,
            proxy=proxy,
            max_retries=args.max_retries,
        )
    except PingError as e:
        log(str(e))
        return 1

    print(result["content"])
    print("---")
    usage = result["usage"] or {}
    line = (
        f"tokens: prompt={usage.get('prompt_tokens', '?')} "
        f"completion={usage.get('completion_tokens', '?')} "
        f"total={usage.get('total_tokens', '?')} | "
        f"耗时 {result['elapsed']}s | 尝试 {result['attempts']} 次"
    )
    money = cost_of(result["usage"], price_in, price_out)
    if money is not None:
        line += f" | 费用 ¥{money:.4f}"
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
