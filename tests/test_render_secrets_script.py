import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_KEYS = (
    "TRELLO_API_KEY",
    "TRELLO_TOKEN",
    "TRELLO_BOARD_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_CHANNEL",
    "TFNSW_API_KEY",
)


def test_script_writes_the_provider_secret(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "AILABS_FOUNDRY_API_KEY=a\nAILABS_FOUNDRY_RESOURCE=r1\n"
        + "".join(f"{k}=x\n" for k in TOOL_KEYS)
    )
    out = tmp_path / "secrets.yaml"
    subprocess.run(
        [sys.executable, "scripts/render-secrets.py", "--env", str(env), "--out", str(out)],
        check=True,
        cwd=ROOT,
    )
    text = out.read_text()
    assert text.count("kind: Secret") == 4
    assert "name: azure-ailabs" in text
    assert "namespace: kora-system" in text
    assert 'runkora.io/inference-provider: "true"' in text
    assert 'apiKey: "a"' in text


def test_each_tool_server_gets_only_the_keys_it_uses(tmp_path):
    import yaml

    env = tmp_path / ".env"
    env.write_text("AILABS_FOUNDRY_API_KEY=a\n" + "".join(f"{n}=v-{n}\n" for n in TOOL_KEYS))
    out = tmp_path / "secrets.yaml"
    subprocess.run(
        [sys.executable, "scripts/render-secrets.py", "--env", str(env), "--out", str(out)],
        check=True,
        cwd=ROOT,
    )
    docs = {d["metadata"]["name"]: d for d in yaml.safe_load_all(out.read_text()) if d}
    assert set(docs) == {"azure-ailabs", "tools-trello", "tools-telegram", "tools-transport"}
    assert all(
        docs[n]["metadata"]["namespace"] == "kora-tenant-example"
        for n in docs
        if n != "azure-ailabs"
    )
    assert set(docs["tools-trello"]["stringData"]) == {
        "TRELLO_API_KEY",
        "TRELLO_TOKEN",
        "TRELLO_BOARD_ID",
    }
    assert set(docs["tools-telegram"]["stringData"]) == {
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_CHANNEL",
    }
    assert docs["tools-transport"]["stringData"] == {"TFNSW_API_KEY": "v-TFNSW_API_KEY"}


def _env_file(tmp_path, extra: str = "") -> Path:
    env = tmp_path / ".env"
    env.write_text(
        "AILABS_FOUNDRY_API_KEY=a\nAILABS_FOUNDRY_RESOURCE=r1\n"
        + "".join(f"{k}=x\n" for k in TOOL_KEYS)
        + extra
    )
    return env


def _render(tmp_path, env: Path, key: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "scripts/render-secrets.py",
            "--env",
            str(env),
            "--out",
            str(tmp_path / "secrets.yaml"),
            "--github-key",
            str(key),
            "--connection-out",
            str(tmp_path / "github-connection.yaml"),
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_github_key_rendered_from_file_when_present(tmp_path):
    import yaml

    key = tmp_path / "github-app.pem"
    key.write_text("-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n")
    env = _env_file(tmp_path, "GITHUB_APP_ID=42\nGITHUB_APP_INSTALLATION_ID=987\n")
    _render(tmp_path, env, key)
    docs = list(yaml.safe_load_all((tmp_path / "secrets.yaml").read_text()))
    github = next(d for d in docs if d["metadata"]["name"] == "github-app-key")
    assert github["metadata"]["namespace"] == "kora-tenant-example"
    assert github["stringData"]["key.pem"] == key.read_text()
    connection = yaml.safe_load((tmp_path / "github-connection.yaml").read_text())
    assert connection["spec"]["config"] == {
        "app_id": "42",
        "installation_id": 987,
        "owner": "navnit-a",
    }


def test_github_key_skipped_when_absent(tmp_path):
    env = _env_file(tmp_path)
    result = _render(tmp_path, env, tmp_path / "missing.pem")
    assert (tmp_path / "secrets.yaml").read_text().count("kind: Secret") == 4
    assert "GitHub App not connected yet" in result.stdout
    assert not (tmp_path / "github-connection.yaml").exists()
