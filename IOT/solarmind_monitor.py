#!/usr/bin/env python3
"""Run the complete SolarMind viewer locally on Kali using the Mac's LAN API."""
import argparse
import json
import re
import shutil
import threading
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import urlopen


class Monitor(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlsplit(self.path)
        path = request.path
        if request.scheme or request.netloc:
            self.send_error(400)
            return

        # Keep the download URLs from the first Linux client working.
        if path in ("/history.csv", "/history.json"):
            extension = path.rsplit(".", 1)[1]
            path = f"/sites/{quote(self.server.site, safe='')}/export.{extension}"

        pages = {"/", "/docs", "/openapi.json", "/weather", "/arduino", "/dashboard/data"}
        if path not in pages and not re.fullmatch(
                r"/sites/[^/]+/(?:live|latest|readings|export\.(?:json|csv))", path):
            self.send_error(404)
            return

        full_history = path.endswith("/readings") and "limit" not in parse_qs(request.query, keep_blank_values=True)
        upstream_path = path.rsplit("/", 1)[0] + "/export.json" if full_history else path
        url = self.server.api + upstream_path
        query = request.query
        if query:
            url += "?" + query
        try:
            upstream = urlopen(url, timeout=10)
        except HTTPError as error:
            upstream = error  # Preserve API status and validation messages.
        except OSError as error:
            self.send_error(502, f"Cannot reach Mac viewer at {self.server.api}: {error}")
            return

        with upstream:
            body = None
            if full_history and upstream.status == 200:
                body = json.dumps(json.load(upstream)[::-1]).encode()
            elif path == "/dashboard/data" and upstream.status == 200:
                try:
                    dashboard = json.load(upstream)
                    site = quote(dashboard["config"]["site_id"], safe="")
                    with urlopen(f"{self.server.api}/sites/{site}/export.json", timeout=30) as history:
                        dashboard["readings"] = json.load(history)[::-1]
                    body = json.dumps(dashboard).encode()
                except (OSError, ValueError, KeyError, TypeError) as error:
                    self.send_error(502, f"Cannot load minute history: {error}")
                    return
            self.send_response(upstream.status)
            self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")
            if not full_history and upstream.headers.get("Content-Disposition"):
                self.send_header("Content-Disposition", upstream.headers["Content-Disposition"])
            self.end_headers()
            try:
                if body is not None:
                    self.wfile.write(body)
                elif path == "/" and upstream.status == 200:
                    html = upstream.read().decode("utf-8")
                    html = html.replace("Latest 100 minute averages", "All saved minute averages").replace("Recent minute averages", "All saved minute averages")
                    html = re.sub(r'(<input\b[^>]*\bid="test-limit"[^>]*\bvalue=")\d+(")',
                                  r'\g<1>100\2', html)
                    html = html.replace('id="test-site" value="test-01"',
                                        'id="test-site" value="' + escape(self.server.site, quote=True) + '"')
                    self.wfile.write(html.encode("utf-8"))
                else:
                    shutil.copyfileobj(upstream, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://192.168.1.107:8011")
    parser.add_argument("--site", default="test-01")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", 0), Monitor) as server:
        server.api = args.api.rstrip("/")
        server.site = args.site
        address = f"http://127.0.0.1:{server.server_port}/"
        print(f"Open {address} on Kali. Press Ctrl+C to stop.", flush=True)
        threading.Thread(target=webbrowser.open, args=(address,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
