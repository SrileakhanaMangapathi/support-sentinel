"""Local, single-worker UI server. Run: python server.py"""
import json
import os
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from agent import Store, run_agent, gmail_message, ReviewRequired

ROOT = Path(__file__).resolve().parent


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class SupportServer(HTTPServer):
    def service_actions(self):
        self.watcher.tick()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, data, status=200, content_type="application/json"):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def allowed_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def do_GET(self):
        if not self.allowed_host():
            return self.respond({"error": "Invalid host"}, 403)
        assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if self.path in assets:
            name, mime = assets[self.path]
            return self.respond((ROOT / "static" / name).read_bytes(), content_type=mime)
        if self.path == "/api/state":
            return self.respond({"csrf": self.server.csrf, "runs": self.server.store.runs(), "watcher": self.server.watcher.status(),
                "configured": {"OpenAI": bool(os.getenv("OPENAI_API_KEY")), "Gmail": (bool(os.getenv("GMAIL_ACCESS_TOKEN")) or (ROOT / "data" / "gmail-token.json").exists()),
                    "Notion": all(os.getenv(k) for k in ("NOTION_TOKEN", "NOTION_DATA_SOURCE_ID")),
                    "Slack": all(os.getenv(k) for k in ("SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"))}})
        self.respond({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.allowed_host() or self.headers.get("X-CSRF-Token") != self.server.csrf:
            return self.respond({"error": "Refresh this local page and try again."}, 403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 50000:
                raise ValueError("Invalid request size.")
            data = json.loads(self.rfile.read(length))
            if self.path == "/api/watcher":
                if not isinstance(data.get("enabled"), bool):
                    raise ValueError("Enabled must be true or false.")
                return self.respond(self.server.watcher.configure(data["enabled"]))
            if self.path == "/api/gmail":
                return self.respond(gmail_message(data["id"]))
            if self.path != "/api/run":
                return self.respond({"error": "Not found"}, 404)
            if data.get("mode") == "live":
                if data.get("authorize_live") is not True:
                    raise ValueError("Review and enable live writes before running.")
                # Always re-read live source; submitted body cannot substitute for Gmail evidence.
                data["email"] = gmail_message(data["email"]["id"])
            self.respond(run_agent(self.server.store, data["email"], data.get("mode", "demo"), data.get("fault", "none"), data.get("use_ai", False)))
        except (ValueError, KeyError, TypeError, ReviewRequired) as exc:
            self.respond({"error": str(exc)}, 400)
        except Exception:
            self.respond({"error": "Unexpected failure. Check the saved audit trail; do not blindly repeat external creates."}, 500)


def main():
    load_env()
    (ROOT / "data").mkdir(exist_ok=True)
    server = SupportServer(("127.0.0.1", int(os.getenv("PORT", "8765"))), Handler)
    server.csrf = secrets.token_urlsafe(32)
    server.store = Store(ROOT / "data" / "support.db")
    from watcher import InboxWatcher
    server.watcher = InboxWatcher(server.store)
    print(f"Support Sentinel running at http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.store.db.close()
        server.server_close()


if __name__ == "__main__":
    main()
