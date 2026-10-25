import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.environments import NODE_WEB, environment_request  # noqa: E402
from factory_demo.kora_api import load_client  # noqa: E402


def main() -> int:
    client = load_client()
    existing = [e for e in client.list_environments() if e.get("slug") == NODE_WEB.slug]
    if existing:
        print(f"environment {NODE_WEB.slug} already exists ({existing[0].get('id')})")
        return 0
    created = client.create_environment(environment_request(NODE_WEB))
    print(f"created environment {created.get('slug')} ({created.get('id')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
