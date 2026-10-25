import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_script_writes_the_provider_secret(tmp_path):
    env = tmp_path / ".env"
    env.write_text("AILABS_FOUNDRY_API_KEY=a\nAILABS_FOUNDRY_RESOURCE=r1\n")
    out = tmp_path / "secrets.yaml"
    subprocess.run(
        [sys.executable, "scripts/render-secrets.py", "--env", str(env), "--out", str(out)],
        check=True,
        cwd=ROOT,
    )
    text = out.read_text()
    assert text.count("kind: Secret") == 1
    assert "name: azure-ailabs" in text
    assert "namespace: kora-system" in text
    assert 'runkora.io/inference-provider: "true"' in text
    assert "apiKey: a" in text
