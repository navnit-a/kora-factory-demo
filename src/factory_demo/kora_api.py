import json
import os
import subprocess
import time
from pathlib import Path

import httpx

TERMINAL_STATES = frozenset({"completed", "failed", "budget_exhausted"})
DEFAULT_API_URL = "https://api.local.runkora.io"
DEFAULT_CREDENTIALS = "/tmp/kora_credentials.json"
AUTH_HINT = "kora token rejected: run 'make auth-refresh' in the kora checkout"


class KoraAuthError(Exception):
    pass


class KoraClient:
    def __init__(self, base_url: str, token: str, verify: str | bool = True):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify = verify
        self._http: httpx.Client | None = None

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.token}"},
                verify=self.verify,
                timeout=30.0,
            )
        return self._http

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | list:
        content = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        headers = {} if body is None else {"Content-Type": "application/json"}
        response = self._client().request(method, path, content=content, headers=headers)
        if response.status_code == 401:
            raise KoraAuthError(AUTH_HINT)
        response.raise_for_status()
        return response.json() if response.content else {}

    def list_models(self) -> list[dict]:
        return _as_list(self._request("GET", "/api/v1/models"))

    def list_environments(self) -> list[dict]:
        return _as_list(self._request("GET", "/api/v1/environments"))

    def list_agents(self) -> list[dict]:
        return _as_list(self._request("GET", "/api/v1/agent-types"))

    def create_agent(self, request: dict) -> dict:
        return self._request("POST", "/api/v1/agent-types", request)

    def get_agent(self, agent_id: str) -> dict:
        return self._request("GET", f"/api/v1/agent-types/{agent_id}")

    def update_agent(self, agent_id: str, patch: dict) -> dict:
        return self._request("PATCH", f"/api/v1/agent-types/{agent_id}", patch)

    def start_run(self, agent_type_id: str, initial_message: str) -> dict:
        body = {"agent_type_id": agent_type_id, "initial_message": initial_message}
        return self._request("POST", "/api/v1/runs", body)

    def get_run(self, run_id: str) -> dict:
        return self._request("GET", f"/api/v1/runs/{run_id}")

    def run_usage(self, run_id: str) -> dict:
        return self._request("GET", f"/api/v1/runs/{run_id}/usage")

    def wait_for_run(self, run_id: str, timeout_s: int = 600, poll_s: float = 5.0) -> dict:
        deadline = time.monotonic() + timeout_s
        while True:
            run = self.get_run(run_id)
            if run.get("state") in TERMINAL_STATES:
                return run
            if time.monotonic() >= deadline:
                raise TimeoutError(f"run {run_id} still {run.get('state')} after {timeout_s}s")
            time.sleep(poll_s)


def _as_list(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return payload
    for key in ("items", "data", "models", "environments", "agent_types"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def default_ca_file() -> str | bool:
    configured = os.environ.get("KORA_CA_FILE")
    if configured:
        return configured
    try:
        root = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return True
    candidate = Path(root.stdout.strip()) / "rootCA.pem"
    return str(candidate) if candidate.exists() else True


def read_credentials(path: str) -> dict:
    file = Path(path)
    stat = file.stat()
    if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
        raise PermissionError(f"{path} must be owned by you and chmod 600; refusing to read it")
    return json.loads(file.read_text())


def load_client(
    credentials_path: str = DEFAULT_CREDENTIALS, base_url: str | None = None
) -> KoraClient:
    credentials = read_credentials(credentials_path)
    url = base_url or os.environ.get("KORA_API_URL") or DEFAULT_API_URL
    return KoraClient(url, credentials["access_token"], verify=default_ca_file())
