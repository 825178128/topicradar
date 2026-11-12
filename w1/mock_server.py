"""本地 OpenAI 兼容 mock 服务：不开 key 也能验证客户端逻辑。

行为：
- 鉴权：Authorization 必须等于 "Bearer test"，否则 401
- 第一次请求故意返回 500，用来验证重试
- stream=true 返回 SSE，stream=false 返回普通 JSON（带 usage）

单独启动：
    python w1/mock_server.py 8000
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    fail_first = True
    expected_key = "test"
    state = {"n": 0}

    def log_message(self, *args):  # 安静
        pass

    def _send(self, code: int, obj: dict) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _event(self, obj: dict) -> None:
        self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
        self.wfile.flush()

    def do_POST(self):
        Handler.state["n"] += 1
        index = Handler.state["n"]
        length = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            req = {}

        if self.headers.get("Authorization", "") != "Bearer " + Handler.expected_key:
            self._send(401, {"error": {"message": "invalid key"}})
            return

        if Handler.fail_first and index == 1:
            self._send(500, {"error": {"message": "mock transient 500"}})
            return

        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for piece in ["你好", "，这是", " mock 流式回复"]:
                self._event({"choices": [{"delta": {"content": piece}}]})
            self._event(
                {
                    "choices": [{"delta": {}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
                }
            )
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            self._send(
                200,
                {
                    "choices": [{"message": {"role": "assistant", "content": "你好，这是 mock 回复"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 6, "total_tokens": 16},
                },
            )


def serve(port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    httpd = serve(port)
    print(f"mock 服务: http://127.0.0.1:{httpd.server_port}  (key=test)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
