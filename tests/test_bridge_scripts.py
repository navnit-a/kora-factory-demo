import asyncio
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path

import httpx
import pytest
import respx

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
        self.token = "dev-access"

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
    assert module.create(kora, env, lambda: nullcontext(kora)) == 0
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
    opened: tuple[str, ...] = ()

    def identity():
        nonlocal opened
        opened = (*opened, "identity")
        return nullcontext(kora)

    assert module.create(kora, env, identity) == 1
    assert kora.tokens == ()
    assert opened == ()
    assert env.read_text() == "A=1\n"
    assert "Idea scout: scout" in capsys.readouterr().err


class ForwardProcess:
    def __init__(self) -> None:
        self.stdout = io.StringIO("Forwarding from 127.0.0.1:50999 -> 80\n")
        self.args: list[str] = []
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


@respx.mock
def test_create_bridge_token_mints_through_the_identity_forward(tmp_path, capsys):
    module = script("create-bridge-token.py")
    env = tmp_path / ".env"
    env.write_text("A=1\n")
    forward = ForwardProcess()

    def popen(args, **_):
        forward.args = args
        return forward

    route = respx.post("http://127.0.0.1:50999/api/v1/identity/tokens").mock(
        return_value=httpx.Response(
            201, json={"id": "p-1", "token": SECRET, "expires_at": "2027-01-23T10:00:00Z"}
        )
    )
    kora = TokenKora([{"id": "t-9", "name": "Idea scout: scout"}])

    def identity():
        return module.identity_forward(kora.token, popen=popen)

    assert module.create(kora, env, identity) == 0
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer dev-access"
    assert json.loads(request.content)["scopes"][0] == "trigger:t-9:fire"
    assert kora.tokens == ()
    assert "svc/kora-identity" in forward.args
    assert forward.terminated
    assert f"KORA_BRIDGE_TOKEN={SECRET}" in env.read_text()
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err
    assert "about a minute" in out.out


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


@pytest.mark.parametrize("idea", ["too short", "Rate each talk <b>bold</b> please"])
def test_ideas_bridge_once_refuses_bad_idea_text(monkeypatch, capsys, idea):
    module = script("ideas-bridge.py")
    monkeypatch.setenv("KORA_BRIDGE_TOKEN", "kora_x")
    monkeypatch.setenv("KORA_SCOUT_TRIGGER_ID", "t-9")
    built: tuple[str, ...] = ()

    def runner_from(token: str, trigger_id: str):
        nonlocal built
        built = (*built, token)

    monkeypatch.setattr(module, "scout_runner", runner_from)
    assert module.main(["--once", idea]) == 2
    assert built == ()
    assert replies.bad_text() in capsys.readouterr().err


def bridge_block(name: str) -> str:
    text = (ROOT / "scripts" / name).read_text()
    match = re.search(r"^BRIDGE_PID_FILE=.*?^fi$", text, re.S | re.M)
    assert match, f"no bridge block in {name}"
    return f"set -euo pipefail\n{match.group(0)}\n"


def stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_until(check, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return False


def run_block(name: str, cwd: Path, path: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": path}
    return subprocess.run(
        ["bash", "-c", bridge_block(name)], cwd=cwd, env=env, capture_output=True, text=True
    )


def test_session_scripts_start_the_bridge_in_its_own_group_and_stop_all_of_it(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    setsid = "import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])"
    stub(bin_dir, "setsid", f'exec "{sys.executable}" -c "{setsid}" "$@"')
    stub(bin_dir, "uv", "sleep 60 &\necho $! > child.pid\nwait")
    (tmp_path / ".env").write_text("KORA_BRIDGE_TOKEN=kora_x\n")
    path = f"{bin_dir}:{os.environ['PATH']}"
    started = run_block("session-start.sh", tmp_path, path)
    assert started.returncode == 0, started.stderr
    pid = int((tmp_path / "deploy/generated/bridge.pid").read_text())
    assert wait_until(lambda: (tmp_path / "child.pid").exists())
    child = int((tmp_path / "child.pid").read_text())
    try:
        assert os.getpgid(pid) == pid
        stopped = run_block("session-stop.sh", tmp_path, path)
        assert stopped.returncode == 0, stopped.stderr
        assert wait_until(lambda: not alive(child))
        assert wait_until(lambda: not alive(pid))
        assert not (tmp_path / "deploy/generated/bridge.pid").exists()
    finally:
        for leftover in (pid, child):
            if alive(leftover):
                os.kill(leftover, signal.SIGKILL)


def test_session_start_without_setsid_still_gives_the_bridge_its_own_group(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "nohup", "mkdir", "grep", "cat", "sleep", "ps", "tr", "rm"):
        (bin_dir / tool).symlink_to(shutil.which(tool))
    stub(bin_dir, "uv", "sleep 60 &\necho $! > child.pid\nwait")
    (tmp_path / ".env").write_text("KORA_BRIDGE_TOKEN=kora_x\n")
    started = run_block("session-start.sh", tmp_path, str(bin_dir))
    assert started.returncode == 0, started.stderr
    pid = int((tmp_path / "deploy/generated/bridge.pid").read_text())
    assert wait_until(lambda: (tmp_path / "child.pid").exists())
    child = int((tmp_path / "child.pid").read_text())
    try:
        assert os.getpgid(pid) == pid
        stopped = run_block("session-stop.sh", tmp_path, str(bin_dir))
        assert stopped.returncode == 0, stopped.stderr
        assert wait_until(lambda: not alive(child))
        assert wait_until(lambda: not alive(pid))
    finally:
        for leftover in (pid, child):
            if alive(leftover):
                os.kill(leftover, signal.SIGKILL)


def test_session_stop_ignores_a_bridge_that_already_exited(tmp_path):
    gone = subprocess.Popen(["true"])
    gone.wait()
    pid_file = tmp_path / "deploy/generated/bridge.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text(f"{gone.pid}\n")
    stopped = run_block("session-stop.sh", tmp_path, os.environ["PATH"])
    assert stopped.returncode == 0, stopped.stderr
    assert not pid_file.exists()


def test_session_stop_kills_only_the_bridge_when_it_shares_our_group(tmp_path):
    bridge = subprocess.Popen(["sleep", "60"])
    pid_file = tmp_path / "deploy/generated/bridge.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text(f"{bridge.pid}\n")
    try:
        stopped = run_block("session-stop.sh", tmp_path, os.environ["PATH"])
        assert stopped.returncode == 0, stopped.stderr
        assert bridge.wait(timeout=5) == -signal.SIGTERM
        assert not pid_file.exists()
    finally:
        if bridge.poll() is None:
            bridge.kill()


def test_ideas_bridge_serve_labels_cards_through_trello(monkeypatch):
    module = script("ideas-bridge.py")
    for name in ("TELEGRAM_BOT_TOKEN", "TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID"):
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("KORA_BRIDGE_TOKEN", "kora_x")
    monkeypatch.setenv("KORA_SCOUT_TRIGGER_ID", "t-9")
    monkeypatch.setattr(module, "scout_runner", lambda token, trigger_id: object())
    built: tuple = ()

    class Captured:
        def __init__(self, *args) -> None:
            nonlocal built
            built = args

        async def run_forever(self, state) -> None:
            return None

    monkeypatch.setattr(module, "Bridge", Captured)
    asyncio.run(module.serve())
    label_card = built[3]
    assert label_card.__name__ == "add_label"
    assert isinstance(label_card.__self__, module.TrelloClient)
