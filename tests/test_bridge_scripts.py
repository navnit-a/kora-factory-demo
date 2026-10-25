import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from factory_bridge import replies
from factory_bridge.scout_result import parse_scout

ROOT = Path(__file__).resolve().parents[1]
SECRET = "kora_secret-token-value"
SCOUT_ANSWER = (
    "<title>Rate talks</title><story>As an attendee, I want to rate talks.</story>"
    "<criteria>- Given a talk, When I rate it, Then I see the average.</criteria>"
    "<verdict>buildable</verdict><dependencies>none</dependencies><reason>Small.</reason>"
)


def script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TokenKora:
    def __init__(self, triggers: list[dict]) -> None:
        self.triggers = triggers
        self.tokens: tuple[tuple[str, tuple[str, ...], int], ...] = ()

    def list_triggers(self) -> list[dict]:
        return self.triggers

    def create_token(self, name: str, scopes: list[str], expires_in_days: int) -> dict:
        self.tokens = (*self.tokens, (name, tuple(scopes), expires_in_days))
        return {"id": "p-1", "token": SECRET, "expires_at": "2027-01-23T10:00:00Z"}


def test_create_bridge_token_writes_env_atomically_and_prints_no_token(
    tmp_path, monkeypatch, capsys
):
    module = script("create-bridge-token.py")
    env = tmp_path / ".env"
    env.write_text("TRELLO_TOKEN=t\nKORA_BRIDGE_TOKEN=old\n")
    writes: tuple[Path, ...] = ()
    real_write = module.write_env_atomic

    def spy(path: Path, text: str) -> None:
        nonlocal writes
        writes = (*writes, path)
        real_write(path, text)

    monkeypatch.setattr(module, "write_env_atomic", spy)
    kora = TokenKora(
        [{"id": "t-0", "name": "Idea scout: run now"}, {"id": "t-9", "name": "Idea scout: scout"}]
    )
    assert module.create(kora, env) == 0
    assert kora.tokens == (
        ("ideas-bridge", ("trigger:t-9:fire", "triggers:read", "agents:runs:idea-scout:read"), 90),
    )
    assert writes == (env,)
    assert env.read_text() == (
        f"TRELLO_TOKEN=t\nKORA_BRIDGE_TOKEN={SECRET}\nKORA_SCOUT_TRIGGER_ID=t-9\n"
    )
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err
    assert "2027-01-23" in out.out and "t-9" in out.out


def test_create_bridge_token_needs_the_scout_trigger(tmp_path, capsys):
    module = script("create-bridge-token.py")
    env = tmp_path / ".env"
    env.write_text("A=1\n")
    kora = TokenKora([{"id": "t-0", "name": "Idea scout: run now"}])
    assert module.create(kora, env) == 1
    assert kora.tokens == ()
    assert env.read_text() == "A=1\n"
    assert "Idea scout: scout" in capsys.readouterr().err


def test_ideas_allow_appends_to_the_allowlist(tmp_path, capsys):
    module = script("ideas-allow.py")
    path = tmp_path / "generated" / "ideas-allowlist"
    assert module.main(["12345", "Ana", "Silva"], path) == 0
    assert module.main(["678"], path) == 0
    assert path.read_text() == "12345 Ana Silva\n678\n"
    assert "12345" in capsys.readouterr().out


def test_ideas_allow_rejects_a_non_numeric_id(tmp_path):
    module = script("ideas-allow.py")
    with pytest.raises(SystemExit) as stopped:
        module.main(["@ana"], tmp_path / "ideas-allowlist")
    assert stopped.value.code == 2


def test_ideas_bridge_lists_every_missing_env_name():
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "")}
    done = subprocess.run(
        [sys.executable, "scripts/ideas-bridge.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 2
    for name in (
        "TELEGRAM_BOT_TOKEN",
        "KORA_BRIDGE_TOKEN",
        "KORA_SCOUT_TRIGGER_ID",
        "TRELLO_API_KEY",
        "TRELLO_TOKEN",
        "TRELLO_BOARD_ID",
    ):
        assert name in done.stderr
    assert done.stderr.count("\n") == 1


def test_ideas_bridge_once_needs_only_kora(monkeypatch, capsys):
    module = script("ideas-bridge.py")
    for name in ("TELEGRAM_BOT_TOKEN", "TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KORA_BRIDGE_TOKEN", "kora_x")
    monkeypatch.setenv("KORA_SCOUT_TRIGGER_ID", "t-9")
    calls: tuple[tuple[str, str], ...] = ()

    class Runner:
        def run(self, idea: str, from_name: str) -> str:
            nonlocal calls
            calls = (*calls, (idea, from_name))
            return SCOUT_ANSWER

    built: tuple[tuple[str, str], ...] = ()

    def runner_from(token: str, trigger_id: str) -> Runner:
        nonlocal built
        built = (*built, (token, trigger_id))
        return Runner()

    monkeypatch.setattr(module, "scout_runner", runner_from)
    assert module.main(["--once", "Rate each talk out of five", "--from", "Ana"]) == 0
    assert built == (("kora_x", "t-9"),)
    assert calls == (("Rate each talk out of five", "Ana"),)
    assert capsys.readouterr().out.strip() == replies.proposal(parse_scout(SCOUT_ANSWER))


def test_ideas_bridge_once_lists_missing_kora_env(monkeypatch, capsys):
    module = script("ideas-bridge.py")
    monkeypatch.delenv("KORA_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("KORA_SCOUT_TRIGGER_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    assert module.main(["--once", "Rate each talk out of five"]) == 2
    err = capsys.readouterr().err
    assert "KORA_BRIDGE_TOKEN" in err and "TELEGRAM_BOT_TOKEN" not in err
