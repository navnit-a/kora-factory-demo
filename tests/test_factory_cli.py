from contextlib import contextmanager
from functools import partial

import httpx
import respx

from factory_demo.factory import deploy_factory, set_team_schedules
from factory_demo.factory_cli import deploy_command, factory_command, leave_operator_notes
from tests.fake_kora import FakeKora

TEAM_SCHEDULES = (
    "Product owner: every 10 min",
    "Delivery lead: every 10 min",
    "Delivery lead: stand-up",
    "Scrum master: every 15 min",
)


def no_notes(action):
    return None


def enabled(kora: FakeKora) -> dict[str, bool]:
    return {t["name"]: t["enabled"] for t in kora.triggers if t["name"] in TEAM_SCHEDULES}


def recording_notes(kora: FakeKora, calls: list):
    def notes(action):
        calls.append((action, enabled(kora)))

    return notes


def test_status_prints_each_schedule(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=True)
    assert factory_command(["status"], kora, no_notes) == 0
    out = capsys.readouterr().out
    assert "paused   3-59/10 * * * *  Product owner: every 10 min" in out
    assert "running  0 7 * * 1-5      Sydney trains: 07:00 weekdays" in out


def test_resume_uses_the_cadence_flag(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=True)
    assert factory_command(["resume", "--cadence", "recording"], kora, no_notes) == 0
    developer = next(t for t in kora.triggers if t["name"] == "Senior developer: every 5 min")
    assert developer["enabled"] is True
    assert developer["schedule_config"]["cron_expression"] == "*/5 * * * *"


def test_pause_fails_loudly_and_names_what_kept_running(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    set_team_schedules(kora, True, "quiet")
    kora.fail_patch_for = "Delivery lead: stand-up"
    assert factory_command(["pause"], kora, no_notes) == 1
    err = capsys.readouterr().err
    assert "Delivery lead: stand-up" in err
    assert "still running" in err


def test_deploy_command_reports_and_sets_the_cap(capsys):
    kora = FakeKora()
    policy = FakeKora()

    @contextmanager
    def policy_client():
        yield policy

    assert deploy_command([], kora, policy_client, wait=lambda _: None) == 0
    out = capsys.readouterr().out
    assert "created 11" in out
    assert "skipped: Senior developer" in out
    assert "tenant cap 60.0 USD weekly" in out
    assert policy.cap == {"limit_usd": 60.0, "reset_cadence": "weekly"}


def test_pause_posts_operator_notes_only_when_it_succeeded(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    set_team_schedules(kora, True, "quiet")
    calls: list = []
    kora.fail_patch_for = "Delivery lead: stand-up"
    assert factory_command(["pause"], kora, recording_notes(kora, calls)) == 1
    assert calls == []
    kora.fail_patch_for = None
    assert factory_command(["pause"], kora, recording_notes(kora, calls)) == 0
    assert calls == [("pause", dict.fromkeys(TEAM_SCHEDULES, False))]


def test_resume_posts_operator_notes_before_enabling(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    calls: list = []
    assert factory_command(["resume"], kora, recording_notes(kora, calls)) == 0
    assert calls == [("resume", dict.fromkeys(TEAM_SCHEDULES, False))]
    assert enabled(kora) == dict.fromkeys(TEAM_SCHEDULES, True)


@respx.mock
def test_missing_trello_env_skips_notes_with_one_line(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("KORA_BRIDGE_TOKEN=x\nTRELLO_API_KEY=k\n")
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    set_team_schedules(kora, True, "quiet")
    assert factory_command(["pause"], kora, partial(leave_operator_notes, env_path=env)) == 0
    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        "operator notes skipped: set TRELLO_TOKEN, TRELLO_BOARD_ID in .env"
    ]
    assert captured.out == "team schedules paused (quiet)\n"
    assert enabled(kora) == dict.fromkeys(TEAM_SCHEDULES, False)
    assert not respx.calls


@respx.mock
def test_missing_env_file_skips_notes_with_one_line(tmp_path, capsys):
    leave_operator_notes("resume", env_path=tmp_path / ".env")
    assert capsys.readouterr().err.splitlines() == [
        "operator notes skipped: set TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_ID in .env"
    ]
    assert not respx.calls


@respx.mock
def test_a_trello_failure_is_one_line_and_the_pause_stands(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("TRELLO_API_KEY=k\nTRELLO_TOKEN=t\nTRELLO_BOARD_ID=b\n")
    respx.route(host="api.trello.com").mock(return_value=httpx.Response(401, text="invalid"))
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    assert factory_command(["pause"], kora, partial(leave_operator_notes, env_path=env)) == 0
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 1
    assert err[0].startswith("operator notes not posted: Trello returned HTTP 401")
