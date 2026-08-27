#!/usr/bin/env python3
"""Mock OpenAI-compatible endpoint. Always returns a canned chat completion
in the well-known envelope. Measures the gateway, not the model."""
import json, time
from http.server import BaseHTTPRequestHandler, HTTPServer

RESP = {
    "id": "chatcmpl-mock",
    "object": "chat.completion",
    "created": 0,
    "model": "mock-model",
    "choices": [{
        "index": 0,
        "message": {"role": "assistant", "content": "mock-response"},
        "finish_reason": "stop",
    }],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}

class H(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_POST(self):
        body = json.dumps(RESP).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8000), H).serve_forever()
