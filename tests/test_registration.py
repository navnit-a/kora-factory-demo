import httpx
import respx

from factory_demo.catalog import DEMO_MODELS
from factory_demo.kora_api import KoraClient
from factory_demo.registration import register_models, unpriced_models

BASE = "https://api.local.runkora.io"


def priced(provider: str, model_id: str, cost: float) -> dict:
    return {
        "provider": provider,
        "model_id": model_id,
        "effective_input_cost_per_1m": cost,
        "effective_output_cost_per_1m": cost,
    }


@respx.mock
def test_register_creates_missing_retargets_stale_and_prices_overrides():
    stale = {
        "id": "vm-1",
        "family": "anthropic",
        "name": "claude-haiku-5-5",
        "routes": [{"provider": "azure:ailabs"}],
    }
    respx.get(f"{BASE}/v1/catalog/virtual-models").mock(
        return_value=httpx.Response(200, json={"data": [stale]})
    )
    create = respx.post(f"{BASE}/v1/catalog/virtual-models").mock(
        return_value=httpx.Response(201, json={"id": "new"})
    )
    retarget = respx.put(f"{BASE}/v1/catalog/virtual-models/vm-1").mock(
        return_value=httpx.Response(200, json={})
    )
    prices = respx.put(url__regex=r".*/v1/catalog/pricing/.*/override").mock(
        return_value=httpx.Response(204)
    )
    log = register_models(KoraClient(BASE, "tok"))
    assert create.call_count == len(DEMO_MODELS) - 1
    assert retarget.call_count == 1
    assert prices.call_count == 3
    assert "routed anthropic/claude-haiku-5-5 to compatible:ailabs-claude" in log


def test_unpriced_models_names_every_demo_model_without_a_positive_price():
    pricing = [
        priced("compatible:ailabs-claude", "claude-haiku-5-5", 0.1),
        priced("compatible:ailabs-claude", "claude-sonnet-5-5", 0),
        priced("azure", "gpt-5.5", 5),
    ]
    assert unpriced_models(pricing) == [
        "anthropic/claude-sonnet-5-5",
        "anthropic/claude-fable-5-1",
        "openai/gpt-5-4",
    ]


def test_unpriced_models_reads_azure_prices_under_the_base_provider_name():
    pricing = [
        priced("compatible:ailabs-claude", m, 1)
        for m in ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-fable-5-1")
    ] + [priced("azure", "gpt-5.5", 5), priced("azure", "gpt-5.4", 2.5)]
    assert unpriced_models(pricing) == []
