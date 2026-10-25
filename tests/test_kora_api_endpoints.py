import subprocess

import httpx
import respx

from factory_demo import kora_api
from factory_demo.kora_api import KoraClient, default_ca_file

BASE = "https://api.local.runkora.io"


def client() -> KoraClient:
    return KoraClient(BASE, "tok")


@respx.mock
def test_list_endpoints_unwrap_an_items_envelope():
    respx.get(f"{BASE}/api/v1/environments").mock(
        return_value=httpx.Response(200, json={"items": [{"slug": "node-web"}]})
    )
    respx.get(f"{BASE}/api/v1/agent-types").mock(
        return_value=httpx.Response(200, json=[{"slug": "smoke"}])
    )
    respx.get(f"{BASE}/v1/models").mock(return_value=httpx.Response(200, json={"total": 0}))
    assert client().list_environments() == [{"slug": "node-web"}]
    assert client().list_agents() == [{"slug": "smoke"}]
    assert client().list_models() == []


@respx.mock
def test_agent_and_run_reads_hit_their_paths():
    respx.post(f"{BASE}/api/v1/agent-types").mock(
        return_value=httpx.Response(201, json={"id": "at-1"})
    )
    respx.get(f"{BASE}/api/v1/agent-types/at-1").mock(
        return_value=httpx.Response(200, json={"state": "active"})
    )
    patch = respx.patch(f"{BASE}/api/v1/agent-types/at-1").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get(f"{BASE}/api/v1/runs/r-1/usage").mock(
        return_value=httpx.Response(200, json={"cost_usd": 0.03})
    )
    c = client()
    assert c.create_agent({"slug": "smoke"}) == {"id": "at-1"}
    assert c.get_agent("at-1") == {"state": "active"}
    c.update_agent("at-1", {"budget": {"per_run_limit_usd": 0.01}})
    assert patch.calls[0].request.read() == b'{"budget":{"per_run_limit_usd":0.01}}'
    assert c.run_usage("r-1") == {"cost_usd": 0.03}


@respx.mock
def test_empty_body_returns_an_empty_dict():
    respx.patch(f"{BASE}/api/v1/agent-types/at-1").mock(return_value=httpx.Response(204))
    assert client().update_agent("at-1", {}) == {}


def test_default_ca_file_prefers_the_environment(monkeypatch):
    monkeypatch.setenv("KORA_CA_FILE", "/some/ca.pem")
    assert default_ca_file() == "/some/ca.pem"


def test_default_ca_file_uses_mkcert_root_when_present(tmp_path, monkeypatch):
    (tmp_path / "rootCA.pem").write_text("x")
    monkeypatch.delenv("KORA_CA_FILE", raising=False)
    done = subprocess.CompletedProcess([], 0, stdout=f"{tmp_path}\n")
    monkeypatch.setattr(kora_api.subprocess, "run", lambda *a, **k: done)
    assert default_ca_file() == str(tmp_path / "rootCA.pem")


def test_default_ca_file_falls_back_to_system_trust_without_mkcert(monkeypatch):
    monkeypatch.delenv("KORA_CA_FILE", raising=False)

    def missing(*args, **kwargs):
        raise OSError("mkcert not installed")

    monkeypatch.setattr(kora_api.subprocess, "run", missing)
    assert default_ca_file() is True
