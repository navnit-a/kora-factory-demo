import os
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factory_demo.github_app import (  # noqa: E402
    callback_code,
    convert,
    create_form,
    install_url,
    manifest,
    setup_installation_id,
    trusted_host,
    with_env_values,
    write_env_atomic,
)

HOST, PORT = "127.0.0.1", 8765
BASE = f"http://{HOST}:{PORT}"
APP_NAME = "kora-factory-navnit-a"
REPO_URL = "https://github.com/navnit-a/platformcon-day-planner"
KEY_FILE = ROOT / "deploy/generated/github-app.pem"
ENV_FILE = ROOT / ".env"
STATE = secrets.token_urlsafe(24)
CREATED: dict[str, str] = {}


def write_env(values: dict[str, str]) -> None:
    write_env_atomic(ENV_FILE, with_env_values(ENV_FILE.read_text(), values))


def write_key(pem: str) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(pem)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not trusted_host(self.headers.get("Host"), f"{HOST}:{PORT}"):
            self.send_error(403)
            return
        try:
            if self.path == "/":
                body = manifest(APP_NAME, f"{BASE}/callback", f"{BASE}/setup", REPO_URL)
                return self._page(create_form(body, STATE))
            if self.path.startswith("/callback"):
                with httpx.Client() as http:
                    app = convert(http, callback_code(self.path, STATE))
                write_key(app.pem)
                write_env({"GITHUB_APP_ID": app.app_id, "GITHUB_APP_SLUG": app.slug})
                CREATED["slug"] = app.slug
                print(f"created GitHub App {app.slug} (id {app.app_id}); key in {KEY_FILE}")
                return self._redirect(install_url(app.slug, STATE))
            if self.path.startswith("/setup"):
                if "slug" not in CREATED:
                    raise ValueError("create the App first; setup is only accepted after it")
                installation = setup_installation_id(self.path, STATE)
                write_env({"GITHUB_APP_INSTALLATION_ID": installation})
                print(f"installed, installation id {installation}")
                self._page("<p>Installed. You can close this tab.</p>")
                raise SystemExit(0)
            self.send_error(404)
        except ValueError as error:
            print(error, file=sys.stderr)
            self._page(f"<p>{error}</p>", status=400)

    def log_message(self, *_: object) -> None:
        return None

    def _page(self, html: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _redirect(self, url: str) -> None:
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()


def main() -> int:
    server = HTTPServer((HOST, PORT), Handler)
    print(f"open {BASE}/ and press the button; waiting for GitHub")
    webbrowser.open(f"{BASE}/")
    try:
        server.serve_forever()
    except SystemExit:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
