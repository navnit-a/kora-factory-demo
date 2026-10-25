import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.catalog import (  # noqa: E402
    DEMO_MODELS,
    PROVIDER,
    missing_virtual_models,
    needs_retarget,
    price_override_request,
    retargeted,
    virtual_model_request,
)
from factory_demo.kora_api import KoraClient, load_client  # noqa: E402


def create_missing(client: KoraClient) -> None:
    for name, display_name in missing_virtual_models(client.list_virtual_models()):
        client.create_virtual_model(virtual_model_request(name, display_name))
        print(f"created anthropic/{name}")


def retarget_stale(client: KoraClient) -> None:
    demo = {name for name, _ in DEMO_MODELS}
    for model in client.list_virtual_models():
        if model.get("name") in demo and needs_retarget(model):
            client.update_virtual_model(model["id"], retargeted(model))
            print(f"routed anthropic/{model['name']} to {PROVIDER}")


def set_prices(client: KoraClient) -> None:
    for name, _ in DEMO_MODELS:
        client.set_price_override(PROVIDER, name, price_override_request(name))
        print(f"price override set for {PROVIDER}/{name}")


def main() -> int:
    client = load_client()
    create_missing(client)
    retarget_stale(client)
    set_prices(client)
    listed = sorted(m.get("id", "") for m in client.list_models())
    print("gateway lists:", ", ".join(listed) or "nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
