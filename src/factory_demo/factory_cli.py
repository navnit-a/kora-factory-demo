import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

from factory_demo.factory import (
    deploy_factory,
    ensure_tenant_cap,
    factory_status,
    set_team_schedules,
)
from factory_demo.kora_api import KoraClient
from factory_demo.smoke_runner import wait_until_active

LOOPBACK = "127.0.0.1"
POLICY_SERVICE = "svc/kora-policy-service"
IDENTITY_SERVICE = "svc/kora-identity"
FORWARDING = re.compile(r"Forwarding from 127\.0\.0\.1:(\d+) ->")
MAX_FORWARD_LINES = 5


def factory_command(argv: list[str], client: KoraClient) -> int:
    parser = argparse.ArgumentParser(prog="factory.py")
    parser.add_argument("action", choices=("pause", "resume", "status"))
    parser.add_argument("--cadence", choices=("recording", "quiet"), default="quiet")
    args = parser.parse_args(argv)
    if args.action == "status":
        for name, cron, enabled in factory_status(client):
            print(f"{'running' if enabled else 'paused':<8} {cron:<14} {name}")
        return 0
    failed = set_team_schedules(client, args.action == "resume", args.cadence)
    if failed:
        state = "still running" if args.action == "pause" else "still paused"
        print(f"{args.action} failed; {state}: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"team schedules {'resumed' if args.action == 'resume' else 'paused'} ({args.cadence})")
    return 0


def deploy_command(
    argv: list[str],
    client: KoraClient,
    policy_client: Callable[[], AbstractContextManager[KoraClient]],
    wait: Callable[[str], object] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="deploy-factory.py")
    parser.add_argument("--cadence", choices=("recording", "quiet"), default="quiet")
    parser.add_argument("--with-github", action="store_true")
    args = parser.parse_args(argv)
    waiter = wait or (lambda agent_id: wait_until_active(client, agent_id))
    report = deploy_factory(client, args.cadence, args.with_github, waiter)
    print(f"created {len(report.created)}, updated {len(report.updated)}")
    for line in report.skipped:
        print(f"skipped: {line}")
    with policy_client() as policy:
        cap = ensure_tenant_cap(policy)
    print(f"tenant cap {cap['limit_usd']} USD {cap['reset_cadence']}")
    return 0


def policy_forward(
    token: str, popen: Callable[..., Any] = subprocess.Popen
) -> AbstractContextManager[KoraClient]:
    return service_forward(POLICY_SERVICE, token, popen)


def identity_forward(
    token: str, popen: Callable[..., Any] = subprocess.Popen
) -> AbstractContextManager[KoraClient]:
    return service_forward(IDENTITY_SERVICE, token, popen)


@contextmanager
def service_forward(
    service: str, token: str, popen: Callable[..., Any] = subprocess.Popen
) -> Iterator[KoraClient]:
    forward = popen(
        [
            "kubectl",
            "-n",
            "kora-system",
            "port-forward",
            "--address",
            LOOPBACK,
            service,
            ":80",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        port = _await_port(forward)
        yield KoraClient(f"http://{LOOPBACK}:{port}", token)
    finally:
        forward.terminate()
        forward.wait(timeout=10)


def forward_port(line: str) -> int | None:
    match = FORWARDING.search(line)
    return int(match.group(1)) if match else None


def _await_port(forward: Any) -> int:
    seen: list[str] = []
    for _ in range(MAX_FORWARD_LINES):
        line = forward.stdout.readline()
        port = forward_port(line)
        if port is not None:
            return port
        seen = [*seen, line.strip()]
        if not line and forward.poll() is not None:
            break
    detail = " ".join(s for s in seen if s) or "no output"
    raise RuntimeError(f"kubectl port-forward exited before forwarding: {detail}")
