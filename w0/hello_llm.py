"""W00 交付物：最小 LLM 调用。

目标：证明"我能用代码调到模型"，不追求功能。
    python w0/hello_llm.py "你好"
"""
import json
import os
import sys
from urllib import error, request


def load_env(path=".env"):
    cfg = {}
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


def main():
    env = load_env(os.path.join(os.path.dirname(__file__), "..", ".env"))
    key = env.get("API_KEY") or os.environ.get("API_KEY", "")
    base = (env.get("API_BASE") or "https://api.deepseek.com").rstrip("/")
    model = env.get("MODEL") or "deepseek-chat"
    proxy = env.get("HTTPS_PROXY") or os.environ.get("HTTPS_PROXY") or None

    if not key:
        print("缺少 API_KEY：把 .env.example 复制成 .env，填入 API_KEY 再运行。", file=sys.stderr)
        return 2

    prompt = sys.argv[1] if len(sys.argv) > 1 else "用一句话解释什么是 AI agent"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    handlers = [request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
    opener = request.build_opener(*handlers)
    req = request.Request(
        base + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )

    try:
        with opener.open(req, timeout=60) as resp:
            data = json.load(resp)
    except error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
        print("401=key 不对；404=base 路径不对；429=限流。", file=sys.stderr)
        return 1
    except error.URLError as e:
        print(f"网络不通：{e.reason}（检查代理 HTTPS_PROXY）", file=sys.stderr)
        return 1

    print(data["choices"][0]["message"]["content"])
    print("---")
    print("usage:", data.get("usage"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
