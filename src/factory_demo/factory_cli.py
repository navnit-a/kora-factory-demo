import argparse
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from factory_demo.factory import (
    deploy_factory,
    ensure_tenant_cap,
    factory_status,
    set_team_schedules,
)
from factory_demo.kora_api import KoraClient
from factory_demo.smoke_runner import wait_until_active

POLICY_PORT = 6091
POLICY_SERVICE = "svc/kora-policy-service"
PORT_WAIT_S = 20


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


@contextmanager
def policy_forward(token: str) -> Iterator[KoraClient]:
    forward = subprocess.Popen(
        ["kubectl", "-n", "kora-system", "port-forward", POLICY_SERVICE, f"{POLICY_PORT}:80"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(POLICY_PORT)
        yield KoraClient(f"http://localhost:{POLICY_PORT}", token)
    finally:
        forward.terminate()
        forward.wait(timeout=10)


def _wait_for_port(port: int) -> None:
    deadline = time.monotonic() + PORT_WAIT_S
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError(f"kubectl port-forward to {POLICY_SERVICE} did not open port {port}")
