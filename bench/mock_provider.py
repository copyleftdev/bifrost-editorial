#!/usr/bin/env python3
"""Mock OpenAI-compatible provider for the bench. Listens on PORT env (default 9000).
Returns canned chat completions; identifies itself in the response content so
load-balancing/failover is observable from the client side."""
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "9000"))
NAME = os.environ.get("NAME", f"provider-{PORT}")

class H(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_POST(self):
        body = json.dumps({
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": 0,
            "model": "mock",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": f"answered-by:{NAME}"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    print(f"{NAME} on :{PORT}", file=sys.stderr)
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
