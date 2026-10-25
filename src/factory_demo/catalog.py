PROVIDER = "compatible:ailabs-claude"
FAMILY = "anthropic"
DEMO_MODELS = (
    ("claude-haiku-5-5", "Claude Haiku 5.5"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5"),
    ("claude-fable-5-1", "Claude Fable 5.1"),
)
AZURE_SYNCED_PRICES = {
    "claude-haiku-5-5": (0.1, 0.5, 0.01, 0.125),
    "claude-sonnet-5-5": (2.0, 10.0, 0.2, 2.5),
    "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5),
}


def virtual_model_request(name: str, display_name: str, provider: str = PROVIDER) -> dict:
    return {
        "family": FAMILY,
        "name": name,
        "display_name": display_name,
        "description": f"{display_name} on the ClearRoute Azure Foundry resource",
        "strategy": "priority",
        "enabled": True,
        "routes": [
            {
                "provider": provider,
                "model_id": name,
                "priority": 1,
                "weight": 100,
                "enabled": True,
            }
        ],
    }


def missing_virtual_models(existing: list[dict]) -> list[tuple[str, str]]:
    registered = {m.get("name") for m in existing if m.get("family", FAMILY) == FAMILY}
    return [(name, display) for name, display in DEMO_MODELS if name not in registered]


def needs_retarget(existing: dict, provider: str = PROVIDER) -> bool:
    return any(route.get("provider") != provider for route in existing.get("routes", []))


def retargeted(existing: dict, provider: str = PROVIDER) -> dict:
    return virtual_model_request(existing["name"], existing["display_name"], provider)


def price_override_request(name: str) -> dict:
    input_cost, output_cost, cache_read, cache_write = AZURE_SYNCED_PRICES[name]
    return {
        "input_cost_per_1m": input_cost,
        "output_cost_per_1m": output_cost,
        "cache_read_cost_per_1m": cache_read,
        "cache_write_cost_per_1m": cache_write,
    }
