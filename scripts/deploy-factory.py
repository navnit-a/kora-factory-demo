import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.cli import run_cli  # noqa: E402
from factory_demo.factory_cli import deploy_command, policy_forward  # noqa: E402
from factory_demo.kora_api import load_client  # noqa: E402


def main() -> int:
    client = load_client()
    return deploy_command(sys.argv[1:], client, lambda: policy_forward(client.token))


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
