#!/usr/bin/env python3
"""Mock provider v2 for the migration bench: realistic usage + latency.
Env: PORT (9000 def), NAME, LATENCY_MS (default 200), TOKENS_OUT (default 150)."""
import json, os, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "9000"))
NAME = os.environ.get("NAME", f"provider-{PORT}")
LATENCY = float(os.environ.get("LATENCY_MS", "200")) / 1000
TOKENS_OUT = int(os.environ.get("TOKENS_OUT", "150"))
stats = {"requests": 0}
lock = threading.Lock()

class H(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_POST(self):
        body_raw = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
        with lock: stats["requests"] += 1
        req: dict = {}
        try:
            parsed = json.loads(body_raw)
            if isinstance(parsed, dict): req = parsed
            prompt_tokens = sum(len(m.get("content", "").split()) for m in req.get("messages", []))
        except (json.JSONDecodeError, TypeError):
            prompt_tokens = 0
        time.sleep(LATENCY)
        resp = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.get("model", "mock") if isinstance(req, dict) else "mock",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": f"answered-by:{NAME}"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": prompt_tokens or 10,
                      "completion_tokens": TOKENS_OUT,
                      "total_tokens": (prompt_tokens or 10) + TOKENS_OUT},
        }
        body = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/__stats":
            body = json.dumps(stats).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    print(f"{NAME} on :{PORT} latency={LATENCY*1000}ms", file=sys.stderr)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
