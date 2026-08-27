#!/usr/bin/env python3
"""Minimal MCP (JSON-RPC over HTTP) server exposing one tool: get_time.
Bifrost connects as an MCP client; the demo proves tool discovery works."""
import json, os
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "9003"))
TOOLS = [{
    "name": "get_time",
    "description": "Returns the current UTC time",
    "inputSchema": {"type": "object", "properties": {}},
}]

class H(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._respond({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            return
        method = req.get("method")
        rid = req.get("id")
        if method == "initialize":
            self._respond({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bench-mcp", "version": "0.1"},
            }})
        elif method == "notifications/initialized":
            self._respond(None, status=202)
        elif method == "tools/list":
            self._respond({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            name = req["params"]["name"]
            if name == "get_time":
                import datetime
                self._respond({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": datetime.datetime.now(datetime.timezone.utc).isoformat()}],
                }})
            else:
                self._respond({"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "unknown tool"}})
        else:
            self._respond({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown method"}})

    def _respond(self, payload, status=200):
        if payload is None:
            self.send_response(status); self.end_headers(); return
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
