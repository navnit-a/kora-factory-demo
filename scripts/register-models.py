import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.cli import run_cli  # noqa: E402
from factory_demo.kora_api import load_client  # noqa: E402
from factory_demo.registration import register_models, unpriced_models  # noqa: E402


def main() -> int:
    client = load_client()
    for line in register_models(client) or ["all demo virtual models already registered"]:
        print(line)
    print("gateway lists:", ", ".join(sorted(m.get("id", "") for m in client.list_models())))
    missing = unpriced_models(client.list_pricing())
    if missing:
        print("no price yet for:", ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
