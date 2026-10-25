import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.cli import run_cli  # noqa: E402
from factory_demo.environments import ENVIRONMENTS, EnvironmentSpec, environment_request  # noqa: E402
from factory_demo.kora_api import KoraClient, load_client  # noqa: E402


def ensure_environment(client: KoraClient, spec: EnvironmentSpec) -> str:
    existing = [e for e in client.list_environments() if e.get("slug") == spec.slug]
    if existing:
        return f"environment {spec.slug} already exists ({existing[0].get('id')})"
    created = client.create_environment(environment_request(spec))
    return f"created environment {created.get('slug')} ({created.get('id')})"


def main() -> int:
    client = load_client()
    for spec in ENVIRONMENTS:
        print(ensure_environment(client, spec))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
