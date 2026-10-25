import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.cli import run_cli  # noqa: E402
from factory_demo.kora_api import load_client  # noqa: E402
from factory_demo.smoke_runner import budget_stop, ensure_agent, smoke, wait_until_active  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-stop", action="store_true")
    args = parser.parse_args()
    client = load_client()
    agent = wait_until_active(client, ensure_agent(client)["id"])
    return budget_stop(client, agent["id"]) if args.budget_stop else smoke(client, agent["id"])


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
