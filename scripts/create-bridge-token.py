import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factory_demo.github_app import with_env_values, write_env_atomic  # noqa: E402
from factory_demo.kora_api import KoraClient, load_client  # noqa: E402

ENV_FILE = ROOT / ".env"
TRIGGER_NAME = "Idea scout: scout"
TOKEN_NAME = "ideas-bridge"
TOKEN_DAYS = 90


def scopes(trigger_id: str) -> list[str]:
    return [f"trigger:{trigger_id}:fire", "triggers:read", "agents:runs:idea-scout:read"]


def create(kora: KoraClient, env_file: Path) -> int:
    matches = [t for t in kora.list_triggers() if t.get("name") == TRIGGER_NAME]
    if not matches:
        print(f"no trigger {TRIGGER_NAME!r}; run scripts/deploy-factory.py first", file=sys.stderr)
        return 1
    trigger_id = matches[0]["id"]
    reply = kora.create_token(TOKEN_NAME, scopes(trigger_id), TOKEN_DAYS)
    token = reply.get("token")
    if not isinstance(token, str) or not token:
        print(
            "kora created the token but sent no token value; revoke it and retry", file=sys.stderr
        )
        return 1
    values = {"KORA_BRIDGE_TOKEN": token, "KORA_SCOUT_TRIGGER_ID": trigger_id}
    write_env_atomic(env_file, with_env_values(env_file.read_text(), values))
    expires = reply.get("expires_at", "unknown")
    print(f"bridge token written to {env_file.name}; expires {expires}; scout trigger {trigger_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(create(load_client(), ENV_FILE))
