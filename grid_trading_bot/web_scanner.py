"""Web-based scanner dashboard — scan-only, no trading.

Starts a local HTTP server that serves an HTML dashboard and exposes
a JSON API to run the symbol scanner.

Usage:
    python -m grid_trading_bot.web_scanner [--port 8080] [--testnet]

Requires GRID_BOT_API_KEY and GRID_BOT_API_SECRET in .env or environment.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import Config
from .scanner import SymbolAnalysis, scan_symbols

logger = logging.getLogger(__name__)

# Global scan state shared between request handler and scan thread
_scan_lock = threading.Lock()
_scan_running = False
_scan_results: list[dict] | None = None
_scan_error: str | None = None


def _run_scan(api_key: str, api_secret: str, testnet: bool, top_n: int) -> None:
    """Run the scanner in a background thread and store results globally."""
    global _scan_running, _scan_results, _scan_error

    try:
        analyses = scan_symbols(api_key, api_secret, testnet=testnet, top_n=top_n)
        with _scan_lock:
            _scan_results = [asdict(a) for a in analyses]
            _scan_error = None
    except Exception as exc:
        with _scan_lock:
            _scan_results = None
            _scan_error = str(exc)
        logger.exception("Scan failed")
    finally:
        with _scan_lock:
            _scan_running = False


class ScannerHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the scanner dashboard."""

    api_key: str = ""
    api_secret: str = ""
    testnet: bool = False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._serve_html()
        elif path == "/api/scan":
            self._handle_scan(parsed.query)
        elif path == "/api/status":
            self._handle_status()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _serve_html(self) -> None:
        html_path = Path(__file__).parent / "static" / "scanner.html"
        content = html_path.read_text(encoding="utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _handle_scan(self, query: str) -> None:
        global _scan_running, _scan_results, _scan_error

        params = parse_qs(query)
        top_n = int(params.get("top", ["10"])[0])
        top_n = max(1, min(top_n, 50))

        with _scan_lock:
            if _scan_running:
                self._json_response({"status": "running"})
                return
            _scan_running = True
            _scan_results = None
            _scan_error = None

        thread = threading.Thread(
            target=_run_scan,
            args=(self.api_key, self.api_secret, self.testnet, top_n),
            daemon=True,
        )
        thread.start()
        self._json_response({"status": "started"})

    def _handle_status(self) -> None:
        with _scan_lock:
            if _scan_running:
                self._json_response({"status": "running"})
            elif _scan_error:
                self._json_response({"status": "error", "error": _scan_error})
            elif _scan_results is not None:
                self._json_response({"status": "done", "results": _scan_results})
            else:
                self._json_response({"status": "idle"})

    def _json_response(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        logger.debug(format, *args)


def serve(port: int = 8080, testnet: bool = False) -> None:
    """Start the scanner web server."""
    # Load config just for API keys
    try:
        config = Config(
            upper_price=1.0, lower_price=0.5,  # dummy values to pass validation
        )
    except Exception as exc:
        print(f"Error loading config: {exc}")
        print("Set GRID_BOT_API_KEY and GRID_BOT_API_SECRET in .env or environment.")
        sys.exit(1)

    ScannerHandler.api_key = config.api_key
    ScannerHandler.api_secret = config.api_secret
    ScannerHandler.testnet = testnet or config.testnet

    server = HTTPServer(("0.0.0.0", port), ScannerHandler)
    url = f"http://localhost:{port}"

    print(f"\n  Grid Trading Scanner Dashboard")
    print(f"  {'Testnet' if ScannerHandler.testnet else 'Mainnet'} mode")
    print(f"  Open {url} in your browser")
    print(f"  Press Ctrl+C to stop\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid Trading Scanner Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    parser.add_argument("--testnet", action="store_true", help="Use Binance testnet")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    serve(port=args.port, testnet=args.testnet)


if __name__ == "__main__":
    main()
