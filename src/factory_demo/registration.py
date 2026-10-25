from factory_demo.catalog import (
    DEMO_MODELS,
    DemoModel,
    missing_virtual_models,
    needs_retarget,
    price_override_request,
    priced_by_override,
    retargeted,
    virtual_model_request,
)
from factory_demo.kora_api import KoraClient


def register_models(client: KoraClient) -> list[str]:
    existing = client.list_virtual_models()
    created = [_create(client, m) for m in missing_virtual_models(existing)]
    routed = [_retarget(client, vm, m) for vm, m in _stale(existing)]
    prices = [_price(client, m) for m in DEMO_MODELS if priced_by_override(m)]
    return [*created, *routed, *prices]


def unpriced_models(pricing: list[dict]) -> list[str]:
    prices = {(_pricing_provider(p["provider"]), p["model_id"]): p for p in pricing}
    return [
        f"{m.family}/{m.name}"
        for m in DEMO_MODELS
        if not _has_price(prices.get((_pricing_provider(m.provider), m.provider_model_id)))
    ]


def _stale(existing: list[dict]) -> list[tuple[dict, DemoModel]]:
    by_key = {(m.family, m.name): m for m in DEMO_MODELS}
    pairs = [(vm, by_key.get((vm.get("family"), vm.get("name")))) for vm in existing]
    return [(vm, m) for vm, m in pairs if m is not None and needs_retarget(vm, m)]


def _create(client: KoraClient, model: DemoModel) -> str:
    client.create_virtual_model(virtual_model_request(model))
    return f"created {model.family}/{model.name}"


def _retarget(client: KoraClient, existing: dict, model: DemoModel) -> str:
    client.update_virtual_model(existing["id"], retargeted(model))
    return f"routed {model.family}/{model.name} to {model.provider}"


def _price(client: KoraClient, model: DemoModel) -> str:
    client.set_price_override(
        model.provider, model.provider_model_id, price_override_request(model)
    )
    return f"price override set for {model.provider}/{model.provider_model_id}"


def _pricing_provider(provider: str) -> str:
    return provider if provider.startswith("compatible:") else provider.split(":", 1)[0]


def _has_price(row: dict | None) -> bool:
    if row is None:
        return False
    return (row.get("effective_input_cost_per_1m") or 0) > 0 and (
        row.get("effective_output_cost_per_1m") or 0
    ) > 0
