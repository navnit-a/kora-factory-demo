import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.github_app import connection_manifest  # noqa: E402
from factory_demo.secrets import read_env, render_secret  # noqa: E402

PROVIDER_LABEL = {"runkora.io/inference-provider": "true"}
TENANT = "kora-tenant-example"
TOOL_SECRETS = {
    "tools-trello": ("TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID"),
    "tools-telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL"),
    "tools-transport": ("TFNSW_API_KEY",),
}
SECRETS = (
    ("azure-ailabs", "kora-system", {"apiKey": "AILABS_FOUNDRY_API_KEY"}, PROVIDER_LABEL),
    *((name, TENANT, {k: k for k in keys}, {}) for name, keys in TOOL_SECRETS.items()),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--out", default="deploy/generated/secrets.yaml")
    parser.add_argument("--github-key", default="deploy/generated/github-app.pem")
    parser.add_argument("--connection-out", default="deploy/generated/github-connection.yaml")
    args = parser.parse_args()
    env = read_env(args.env)
    manifests = [
        render_secret(name, namespace, env, keys, labels)
        for name, namespace, keys, labels in SECRETS
    ]
    key = Path(args.github_key)
    if key.exists() and env.get("GITHUB_APP_ID") and env.get("GITHUB_APP_INSTALLATION_ID"):
        key_env = {"GITHUB_APP_PEM": key.read_text()}
        manifests = [
            *manifests,
            render_secret("github-app-key", TENANT, key_env, {"key.pem": "GITHUB_APP_PEM"}),
        ]
        connection = Path(args.connection_out)
        connection.parent.mkdir(parents=True, exist_ok=True)
        connection.write_text(
            connection_manifest(env["GITHUB_APP_ID"], env["GITHUB_APP_INSTALLATION_ID"])
        )
        print(f"wrote the GitHub connection to {connection}")
    else:
        print("GitHub App not connected yet: run scripts/create-github-app.py; skipping its key")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("---\n".join(manifests))
    print(f"wrote {len(manifests)} secret(s) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
