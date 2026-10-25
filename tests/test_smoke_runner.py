import httpx
import pytest
import respx

from factory_demo.kora_api import KoraClient
from factory_demo.smoke_runner import budget_stop, ensure_agent, run_once, smoke, wait_until_active

BASE = "https://api.local.runkora.io"


def client() -> KoraClient:
    return KoraClient(BASE, "tok")


def no_sleep(_: float) -> None:
    return None


@respx.mock
def test_ensure_agent_reuses_an_existing_smoke_agent():
    respx.get(f"{BASE}/api/v1/agent-types").mock(
        return_value=httpx.Response(200, json={"agent_types": [{"id": "at-1", "slug": "smoke"}]})
    )
    create = respx.post(f"{BASE}/api/v1/agent-types")
    assert ensure_agent(client())["id"] == "at-1"
    assert not create.called


@respx.mock
def test_ensure_agent_creates_it_on_haiku_in_node_web():
    respx.get(f"{BASE}/api/v1/agent-types").mock(
        return_value=httpx.Response(200, json={"agent_types": None})
    )
    respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "anthropic/claude-haiku-5-5"}]})
    )
    respx.get(f"{BASE}/api/v1/environments").mock(
        return_value=httpx.Response(200, json={"environments": [{"id": "e-1", "slug": "node-web"}]})
    )
    create = respx.post(f"{BASE}/api/v1/agent-types").mock(
        return_value=httpx.Response(201, json={"id": "at-2"})
    )
    assert ensure_agent(client())["id"] == "at-2"
    sent = create.calls[0].request.read()
    assert b'"model_id":"anthropic/claude-haiku-5-5"' in sent and b'"environment_id":"e-1"' in sent


@respx.mock
def test_ensure_agent_names_the_missing_environment():
    respx.get(f"{BASE}/api/v1/agent-types").mock(
        return_value=httpx.Response(200, json={"agent_types": []})
    )
    respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "anthropic/claude-haiku-5-5"}]})
    )
    respx.get(f"{BASE}/api/v1/environments").mock(
        return_value=httpx.Response(200, json={"environments": []})
    )
    with pytest.raises(LookupError, match="node-web"):
        ensure_agent(client())


@respx.mock
def test_wait_until_active_times_out_with_the_state():
    respx.get(f"{BASE}/api/v1/agent-types/at-1").mock(
        return_value=httpx.Response(200, json={"state": "provisioning"})
    )
    with pytest.raises(TimeoutError, match="provisioning"):
        wait_until_active(client(), "at-1", timeout_s=0, sleep=no_sleep)


def mock_run(final_state: str, spend: float) -> None:
    respx.post(f"{BASE}/api/v1/runs").mock(return_value=httpx.Response(201, json={"id": "r-1"}))
    respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        return_value=httpx.Response(200, json={"id": "r-1", "state": final_state})
    )
    respx.get(f"{BASE}/v1/usage/run/r-1").mock(
        return_value=httpx.Response(200, json={"run_id": "r-1", "spend_usd": spend})
    )


@respx.mock
def test_smoke_passes_when_the_run_goes_idle_with_a_cost():
    mock_run("idle", 0.0017)
    assert smoke(client(), "at-1") == 0


@respx.mock
def test_smoke_fails_when_the_run_cost_nothing():
    mock_run("idle", 0)
    assert smoke(client(), "at-1") == 1


@respx.mock
def test_run_once_shows_tenant_pods_when_the_run_hangs():
    respx.post(f"{BASE}/api/v1/runs").mock(return_value=httpx.Response(201, json={"id": "r-1"}))
    respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        return_value=httpx.Response(200, json={"id": "r-1", "state": "pending"})
    )
    shown = []
    with pytest.raises(TimeoutError):
        run_once(client(), "at-1", "go", timeout_s=0, show_pods=lambda: shown.append(True))
    assert shown == [True]


@respx.mock
def test_budget_stop_restores_the_normal_limit_even_when_the_run_was_not_stopped():
    mock_run("idle", 0.002)
    patch = respx.patch(f"{BASE}/api/v1/agent-types/at-1").mock(
        return_value=httpx.Response(200, json={})
    )
    assert budget_stop(client(), "at-1", sleep=no_sleep) == 1
    bodies = [c.request.read() for c in patch.calls]
    assert bodies == [
        b'{"budget":{"per_run_limit_usd":0.001}}',
        b'{"budget":{"per_run_limit_usd":0.2}}',
    ]


@respx.mock
def test_budget_stop_passes_on_budget_exhausted():
    mock_run("budget_exhausted", 0.0033)
    respx.patch(f"{BASE}/api/v1/agent-types/at-1").mock(return_value=httpx.Response(200, json={}))
    assert budget_stop(client(), "at-1", sleep=no_sleep) == 0
