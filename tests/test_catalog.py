import httpx
import respx

from factory_demo.catalog import (
    DEMO_MODELS,
    PROVIDER,
    missing_virtual_models,
    price_override_request,
    retargeted,
    virtual_model_request,
)
from factory_demo.kora_api import KoraClient

BASE = "https://api.local.runkora.io"


def test_virtual_model_request_routes_one_provider_model_by_priority():
    body = virtual_model_request("claude-haiku-5-5", "Claude Haiku 5.5", "azure:ailabs")
    assert body == {
        "family": "anthropic",
        "name": "claude-haiku-5-5",
        "display_name": "Claude Haiku 5.5",
        "description": "Claude Haiku 5.5 on the ClearRoute Azure Foundry resource",
        "strategy": "priority",
        "enabled": True,
        "routes": [
            {
                "provider": "azure:ailabs",
                "model_id": "claude-haiku-5-5",
                "priority": 1,
                "weight": 100,
                "enabled": True,
            }
        ],
    }


def test_demo_models_are_the_three_foundry_deployments():
    assert [name for name, _ in DEMO_MODELS] == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
        "claude-fable-5-1",
    ]


def test_missing_virtual_models_skips_names_already_registered():
    existing = [{"family": "anthropic", "name": "claude-haiku-5-5"}]
    assert [n for n, _ in missing_virtual_models(existing)] == [
        "claude-sonnet-5-5",
        "claude-fable-5-1",
    ]


@respx.mock
def test_client_lists_gateway_models_from_the_openai_shaped_route():
    respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(200, json={"object": "list", "data": [{"id": "anthropic/x"}]})
    )
    assert KoraClient(BASE, "tok").list_models() == [{"id": "anthropic/x"}]


@respx.mock
def test_client_reads_and_creates_virtual_models():
    respx.get(f"{BASE}/v1/catalog/virtual-models").mock(
        return_value=httpx.Response(200, json={"data": [{"name": "claude-haiku-5-5"}]})
    )
    create = respx.post(f"{BASE}/v1/catalog/virtual-models").mock(
        return_value=httpx.Response(201, json={"id": "vm-1"})
    )
    client = KoraClient(BASE, "tok")
    assert client.list_virtual_models() == [{"name": "claude-haiku-5-5"}]
    assert client.create_virtual_model({"name": "n"}) == {"id": "vm-1"}
    assert create.calls[0].request.read() == b'{"name":"n"}'


def test_default_provider_is_the_compatible_foundry_endpoint():
    assert PROVIDER == "compatible:ailabs-claude"
    route = virtual_model_request("claude-haiku-5-5", "Claude Haiku 5.5")["routes"][0]
    assert route["provider"] == "compatible:ailabs-claude"


def test_price_override_copies_the_synced_azure_price_for_haiku():
    assert price_override_request("claude-haiku-5-5") == {
        "input_cost_per_1m": 0.1,
        "output_cost_per_1m": 0.5,
        "cache_read_cost_per_1m": 0.01,
        "cache_write_cost_per_1m": 0.125,
    }


def test_retargeted_returns_a_new_body_on_the_new_provider_and_leaves_the_input_alone():
    existing = {
        "id": "vm-1",
        "family": "anthropic",
        "name": "claude-fable-5-1",
        "display_name": "Claude Fable 5.1",
        "routes": [{"provider": "azure:ailabs", "model_id": "claude-fable-5-1"}],
    }
    body = retargeted(existing)
    assert body["routes"][0]["provider"] == "compatible:ailabs-claude"
    assert existing["routes"][0]["provider"] == "azure:ailabs"
    assert "id" not in body


def test_needs_retarget_only_when_a_route_uses_another_provider():
    from factory_demo.catalog import needs_retarget

    assert needs_retarget({"routes": [{"provider": "azure:ailabs"}]})
    assert not needs_retarget({"routes": [{"provider": "compatible:ailabs-claude"}]})


@respx.mock
def test_client_updates_a_virtual_model_and_sets_a_price_override():
    put_vm = respx.put(f"{BASE}/v1/catalog/virtual-models/vm-1").mock(
        return_value=httpx.Response(200, json={"id": "vm-1"})
    )
    put_price = respx.put(
        f"{BASE}/v1/catalog/pricing/compatible:ailabs-claude/claude-haiku-5-5/override"
    ).mock(return_value=httpx.Response(204))
    client = KoraClient(BASE, "tok")
    client.update_virtual_model("vm-1", {"name": "n"})
    client.set_price_override(
        "compatible:ailabs-claude", "claude-haiku-5-5", {"input_cost_per_1m": 1}
    )
    assert put_vm.called and put_price.called
