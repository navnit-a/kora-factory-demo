import io

import pytest

from factory_demo.factory_cli import forward_port, identity_forward, policy_forward


class FakeForward:
    def __init__(self, output: str, exit_code: int | None):
        self.stdout = io.StringIO(output)
        self.exit_code = exit_code
        self.args: list[str] = []
        self.terminated = False

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def test_forward_port_reads_kubectl_output():
    assert forward_port("Forwarding from 127.0.0.1:54321 -> 80\n") == 54321
    assert forward_port("Handling connection for 54321\n") is None


def test_policy_forward_uses_the_port_kubectl_chose_on_loopback():
    fake = FakeForward("Forwarding from 127.0.0.1:50123 -> 80\n", None)

    def popen(args, **_):
        fake.args = args
        return fake

    with policy_forward("tok", popen=popen) as client:
        assert client.base_url == "http://127.0.0.1:50123"
    assert "--address" in fake.args
    assert "127.0.0.1" in fake.args
    assert ":80" in fake.args
    assert "svc/kora-policy-service" in fake.args
    assert fake.terminated


def test_identity_forward_reaches_the_identity_service():
    fake = FakeForward("Forwarding from 127.0.0.1:50124 -> 80\n", None)

    def popen(args, **_):
        fake.args = args
        return fake

    with identity_forward("tok", popen=popen) as client:
        assert client.base_url == "http://127.0.0.1:50124"
    assert "svc/kora-identity" in fake.args
    assert fake.args[1:3] == ["-n", "kora-system"]
    assert fake.terminated


def test_policy_forward_fails_when_kubectl_exits():
    fake = FakeForward("error: unable to forward\n", 1)
    with (
        pytest.raises(RuntimeError, match="kubectl port-forward exited"),
        policy_forward("tok", popen=lambda args, **_: fake),
    ):
        pass
    assert fake.terminated
