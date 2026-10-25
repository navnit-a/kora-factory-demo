from contextlib import contextmanager

from factory_demo.factory import deploy_factory, set_team_schedules
from factory_demo.factory_cli import deploy_command, factory_command
from tests.fake_kora import FakeKora


def test_status_prints_each_schedule(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    assert factory_command(["status"], kora) == 0
    out = capsys.readouterr().out
    assert "paused   3-59/10 * * * *  Product owner: every 10 min" in out
    assert "running  0 7 * * 1-5      Sydney trains: 07:00 weekdays" in out


def test_resume_uses_the_cadence_flag(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=True)
    assert factory_command(["resume", "--cadence", "recording"], kora) == 0
    developer = next(t for t in kora.triggers if t["name"] == "Senior developer: every 5 min")
    assert developer["enabled"] is True
    assert developer["schedule_config"]["cron_expression"] == "*/5 * * * *"


def test_pause_fails_loudly_and_names_what_kept_running(capsys):
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    set_team_schedules(kora, True, "quiet")
    kora.fail_patch_for = "Delivery lead: stand-up"
    assert factory_command(["pause"], kora) == 1
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
    assert "created 17" in out
    assert "skipped: Senior developer" in out
    assert "tenant cap 60.0 USD weekly" in out
    assert policy.cap == {"limit_usd": 60.0, "reset_cadence": "weekly"}
