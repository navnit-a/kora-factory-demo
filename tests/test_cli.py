import pytest

from factory_demo.cli import run_cli
from factory_demo.kora_api import KoraAuthError


def test_run_cli_passes_the_exit_code_through():
    assert run_cli(lambda: 0) == 0
    assert run_cli(lambda: 1) == 1


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (KoraAuthError("kora token rejected: run 'make auth-refresh'"), "make auth-refresh"),
        (FileNotFoundError(2, "No such file", "/tmp/kora_credentials.json"), "make auth"),
        (
            PermissionError("/tmp/kora_credentials.json must be owned by you and chmod 600"),
            "chmod 600",
        ),
    ],
)
def test_run_cli_turns_sign_in_problems_into_one_line_and_exit_2(error, expected, capsys):
    def failing() -> int:
        raise error

    assert run_cli(failing) == 2
    err = capsys.readouterr().err
    assert expected in err
    assert "Traceback" not in err
    assert err.count("\n") == 1
