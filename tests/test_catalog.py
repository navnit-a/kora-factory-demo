import httpx
import respx

from factory_demo.catalog import (
    CLAUDE_PROVIDER,
    DEMO_MODELS,
    OPENAI_PROVIDER,
    DemoModel,
    missing_virtual_models,
    needs_retarget,
    price_override_request,
    priced_by_override,
    retargeted,
    virtual_model_request,
)
from factory_demo.kora_api import KoraClient

BASE = "https://api.local.runkora.io"
HAIKU = DemoModel(
    "anthropic", "claude-haiku-5-5", "Claude Haiku 5.5", CLAUDE_PROVIDER, "claude-haiku-5-5"
)
GPT = DemoModel("openai", "gpt-5-5", "GPT-5.5", OPENAI_PROVIDER, "gpt-5.5")


def test_virtual_model_request_routes_one_provider_model_by_priority():
    assert virtual_model_request(HAIKU) == {
        "family": "anthropic",
        "name": "claude-haiku-5-5",
        "display_name": "Claude Haiku 5.5",
        "description": "Claude Haiku 5.5 on the ClearRoute Azure Foundry resource",
        "strategy": "priority",
        "enabled": True,
        "routes": [
            {
                "provider": "compatible:ailabs-claude",
                "model_id": "claude-haiku-5-5",
                "priority": 1,
                "weight": 100,
                "enabled": True,
            }
        ],
    }


def test_openai_models_use_a_dashed_name_and_route_to_the_dotted_deployment():
    body = virtual_model_request(GPT)
    assert body["family"] == "openai"
    assert body["name"] == "gpt-5-5"
    assert body["routes"][0] == {
        "provider": "azure:ailabs-openai",
        "model_id": "gpt-5.5",
        "priority": 1,
        "weight": 100,
        "enabled": True,
    }


def test_demo_models_are_the_five_foundry_deployments():
    assert [f"{m.family}/{m.name}" for m in DEMO_MODELS] == [
        "anthropic/claude-haiku-5-5",
        "anthropic/claude-sonnet-5-5",
        "anthropic/claude-fable-5-1",
        "openai/gpt-5-5",
        "openai/gpt-5-4",
    ]


def test_only_the_compatible_provider_needs_price_overrides():
    assert [m.name for m in DEMO_MODELS if priced_by_override(m)] == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
        "claude-fable-5-1",
    ]


def test_missing_virtual_models_matches_on_family_and_name():
    existing = [
        {"family": "anthropic", "name": "claude-haiku-5-5"},
        {"family": "anthropic", "name": "gpt-5-5"},
    ]
    missing = [f"{m.family}/{m.name}" for m in missing_virtual_models(existing)]
    assert "anthropic/claude-haiku-5-5" not in missing
    assert "openai/gpt-5-5" in missing


def test_price_override_copies_the_synced_azure_price_for_haiku():
    assert price_override_request(HAIKU) == {
        "input_cost_per_1m": 0.1,
        "output_cost_per_1m": 0.5,
        "cache_read_cost_per_1m": 0.01,
        "cache_write_cost_per_1m": 0.125,
    }


def test_needs_retarget_only_when_a_route_uses_another_provider():
    assert needs_retarget({"routes": [{"provider": "azure:ailabs"}]}, HAIKU)
    assert not needs_retarget({"routes": [{"provider": "compatible:ailabs-claude"}]}, HAIKU)


def test_retargeted_returns_a_new_body_and_leaves_the_input_alone():
    existing = {"id": "vm-1", "routes": [{"provider": "azure:ailabs"}]}
    body = retargeted(HAIKU)
    assert body["routes"][0]["provider"] == "compatible:ailabs-claude"
    assert existing["routes"][0]["provider"] == "azure:ailabs"
    assert "id" not in body


@respx.mock
def test_client_lists_gateway_models_from_the_openai_shaped_route():
    respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(200, json={"object": "list", "data": [{"id": "anthropic/x"}]})
    )
    assert KoraClient(BASE, "tok").list_models() == [{"id": "anthropic/x"}]


@respx.mock
def test_client_reads_creates_and_updates_virtual_models_and_sets_prices():
    respx.get(f"{BASE}/v1/catalog/virtual-models").mock(
        return_value=httpx.Response(200, json={"data": [{"name": "claude-haiku-5-5"}]})
    )
    create = respx.post(f"{BASE}/v1/catalog/virtual-models").mock(
        return_value=httpx.Response(201, json={"id": "vm-1"})
    )
    put_vm = respx.put(f"{BASE}/v1/catalog/virtual-models/vm-1").mock(
        return_value=httpx.Response(200, json={"id": "vm-1"})
    )
    put_price = respx.put(
        f"{BASE}/v1/catalog/pricing/compatible:ailabs-claude/claude-haiku-5-5/override"
    ).mock(return_value=httpx.Response(204))
    client = KoraClient(BASE, "tok")
    assert client.list_virtual_models() == [{"name": "claude-haiku-5-5"}]
    assert client.create_virtual_model({"name": "n"}) == {"id": "vm-1"}
    assert create.calls[0].request.read() == b'{"name":"n"}'
    client.update_virtual_model("vm-1", {"name": "n"})
    client.set_price_override("compatible:ailabs-claude", "claude-haiku-5-5", {"x": 1})
    assert put_vm.called and put_price.called
