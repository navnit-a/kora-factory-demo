import httpx
import pytest
import respx

from factory_demo.kora_api import KoraAuthError, KoraClient, load_client

BASE = "https://api.local.runkora.io:8443"


@respx.mock
def test_start_run_posts_agent_and_message():
    route = respx.post(f"{BASE}/api/v1/runs").mock(
        return_value=httpx.Response(201, json={"id": "run-1", "state": "pending"})
    )
    run = KoraClient(BASE, "tok", verify=False).start_run("at-1", "hello")
    assert run["id"] == "run-1"
    assert route.calls[0].request.headers["authorization"] == "Bearer tok"
    assert route.calls[0].request.read() == b'{"agent_type_id":"at-1","initial_message":"hello"}'


@respx.mock
def test_401_raises_auth_error_with_refresh_hint():
    respx.get(f"{BASE}/api/v1/models").mock(return_value=httpx.Response(401))
    with pytest.raises(KoraAuthError, match="make auth-refresh"):
        KoraClient(BASE, "tok", verify=False).list_models()


@respx.mock
def test_wait_for_run_returns_on_terminal_state():
    respx.get(f"{BASE}/api/v1/runs/run-1").mock(
        side_effect=[
            httpx.Response(200, json={"id": "run-1", "state": "active"}),
            httpx.Response(200, json={"id": "run-1", "state": "completed"}),
        ]
    )
    run = KoraClient(BASE, "tok", verify=False).wait_for_run("run-1", timeout_s=5, poll_s=0)
    assert run["state"] == "completed"


@respx.mock
def test_wait_for_run_times_out():
    respx.get(f"{BASE}/api/v1/runs/run-1").mock(
        return_value=httpx.Response(200, json={"id": "run-1", "state": "pending"})
    )
    with pytest.raises(TimeoutError):
        KoraClient(BASE, "tok", verify=False).wait_for_run("run-1", timeout_s=0, poll_s=0)


def test_load_client_reads_token_and_env_url(tmp_path, monkeypatch):
    creds = tmp_path / "creds.json"
    creds.write_text('{"access_token": "abc", "refresh_token": "r"}')
    ca = tmp_path / "ca.pem"
    ca.write_text("x")
    monkeypatch.setenv("KORA_API_URL", BASE)
    monkeypatch.setenv("KORA_CA_FILE", str(ca))
    client = load_client(str(creds))
    assert client.base_url == BASE
    assert client.token == "abc"
