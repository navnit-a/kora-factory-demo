import html
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

GITHUB_API = "https://api.github.com"
NEW_APP_URL = "https://github.com/settings/apps/new"
OWNER = "navnit-a"
CONNECTION_NAMESPACE = "kora-tenant-example"
PERMISSIONS = {
    "contents": "write",
    "pull_requests": "write",
    "checks": "read",
    "actions": "read",
    "metadata": "read",
}


@dataclass(frozen=True)
class AppCredentials:
    app_id: str
    slug: str
    pem: str


def manifest(name: str, callback_url: str, setup_url: str, repo_url: str) -> dict:
    return {
        "name": name,
        "url": repo_url,
        "redirect_url": callback_url,
        "setup_url": setup_url,
        "public": False,
        "default_permissions": dict(PERMISSIONS),
        "default_events": [],
    }


def create_form(app_manifest: dict, state: str) -> str:
    value = html.escape(json.dumps(app_manifest), quote=True)
    action = html.escape(f"{NEW_APP_URL}?state={state}", quote=True)
    return (
        "<!doctype html><html><body>"
        f'<form method="post" action="{action}">'
        f'<input type="hidden" name="manifest" value="{value}">'
        '<input type="submit" value="Create the GitHub App on GitHub">'
        "</form></body></html>"
    )


def convert(http: httpx.Client, code: str) -> AppCredentials:
    response = http.post(f"{GITHUB_API}/app-manifests/{code}/conversions", timeout=30)
    if response.status_code != 201:
        raise ValueError(
            f"GitHub refused the manifest conversion with HTTP {response.status_code}; "
            "the code lasts one hour, so start again"
        )
    body = response.json()
    return AppCredentials(str(body["id"]), body["slug"], body["pem"])


def callback_code(path: str, expected_state: str) -> str:
    query = parse_qs(urlsplit(path).query)
    if query.get("state", [""])[0] != expected_state:
        raise ValueError("callback state does not match; start again")
    code = query.get("code", [""])[0]
    if not code:
        raise ValueError("GitHub sent no code; start again")
    return code


def setup_installation_id(path: str, expected_state: str) -> str:
    query = parse_qs(urlsplit(path).query)
    if query.get("state", [""])[0] != expected_state:
        raise ValueError("setup state does not match; install the App again from the script")
    value = query.get("installation_id", [""])[0]
    if not value.isdigit():
        raise ValueError("GitHub sent no numeric installation_id; install the App again")
    return value


def install_url(slug: str, state: str) -> str:
    return f"https://github.com/apps/{slug}/installations/new?{urlencode({'state': state})}"


def trusted_host(host: str | None, expected: str) -> bool:
    return host == expected


def with_env_values(text: str, values: dict[str, str]) -> str:
    lines = text.splitlines()
    keys = {line.split("=", 1)[0] for line in lines if "=" in line}
    replaced = [
        f"{key}={values[key]}" if (key := line.split("=", 1)[0]) in values and "=" in line else line
        for line in lines
    ]
    appended = [f"{k}={v}" for k, v in values.items() if k not in keys]
    return "\n".join([*replaced, *appended]) + "\n"


def write_env_atomic(path: Path, text: str) -> None:
    descriptor, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(text)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def connection_manifest(app_id: str, installation_id: str) -> str:
    return "\n".join(
        [
            "apiVersion: runkora.io/v1alpha1",
            "kind: Connection",
            "metadata:",
            "  name: github",
            f"  namespace: {CONNECTION_NAMESPACE}",
            "spec:",
            "  adapter: github_app",
            "  baseHost: github.com",
            "  secretRef: github-app-key",
            "  secretKey: key.pem",
            "  config:",
            f'    app_id: "{app_id}"',
            f"    installation_id: {int(installation_id)}",
            f"    owner: {OWNER}",
            "",
        ]
    )
