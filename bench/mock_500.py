#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def log_message(self,f,*a): pass
    def do_POST(self):
        self.send_response(500); self.send_header("Content-Length","2"); self.end_headers(); self.wfile.write(b"{}")
HTTPServer(("0.0.0.0",9001),H).serve_forever()
