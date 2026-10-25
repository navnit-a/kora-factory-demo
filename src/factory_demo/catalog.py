from dataclasses import dataclass

CLAUDE_PROVIDER = "compatible:ailabs-claude"
OPENAI_PROVIDER = "azure:ailabs-openai"


@dataclass(frozen=True)
class DemoModel:
    family: str
    name: str
    display_name: str
    provider: str
    provider_model_id: str


DEMO_MODELS = (
    DemoModel(
        "anthropic", "claude-haiku-5-5", "Claude Haiku 5.5", CLAUDE_PROVIDER, "claude-haiku-5-5"
    ),
    DemoModel(
        "anthropic", "claude-sonnet-5-5", "Claude Sonnet 5.5", CLAUDE_PROVIDER, "claude-sonnet-5-5"
    ),
    DemoModel(
        "anthropic", "claude-fable-5-1", "Claude Fable 5.1", CLAUDE_PROVIDER, "claude-fable-5-1"
    ),
    DemoModel("openai", "gpt-5-5", "GPT-5.5", OPENAI_PROVIDER, "gpt-5.5"),
    DemoModel("openai", "gpt-5-4", "GPT-5.4", OPENAI_PROVIDER, "gpt-5.4"),
)
AZURE_SYNCED_PRICES = {
    "claude-haiku-5-5": (0.1, 0.5, 0.01, 0.125),
    "claude-sonnet-5-5": (2.0, 10.0, 0.2, 2.5),
    "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5),
}


def virtual_model_request(model: DemoModel) -> dict:
    return {
        "family": model.family,
        "name": model.name,
        "display_name": model.display_name,
        "description": f"{model.display_name} on the ClearRoute Azure Foundry resource",
        "strategy": "priority",
        "enabled": True,
        "routes": [
            {
                "provider": model.provider,
                "model_id": model.provider_model_id,
                "priority": 1,
                "weight": 100,
                "enabled": True,
            }
        ],
    }


def missing_virtual_models(existing: list[dict]) -> list[DemoModel]:
    registered = {(m.get("family"), m.get("name")) for m in existing}
    return [m for m in DEMO_MODELS if (m.family, m.name) not in registered]


def needs_retarget(existing: dict, model: DemoModel) -> bool:
    return any(route.get("provider") != model.provider for route in existing.get("routes", []))


def retargeted(model: DemoModel) -> dict:
    return virtual_model_request(model)


def priced_by_override(model: DemoModel) -> bool:
    return model.provider.startswith("compatible:")


def price_override_request(model: DemoModel) -> dict:
    input_cost, output_cost, cache_read, cache_write = AZURE_SYNCED_PRICES[model.provider_model_id]
    return {
        "input_cost_per_1m": input_cost,
        "output_cost_per_1m": output_cost,
        "cache_read_cost_per_1m": cache_read,
        "cache_write_cost_per_1m": cache_write,
    }
