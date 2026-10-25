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
