import httpx
import pytest

from factory_demo.factory import (
    TENANT_CAP_USD,
    deploy_factory,
    ensure_tenant_cap,
    factory_status,
    set_team_schedules,
)
from factory_demo.roster import ROSTER
from tests.fake_kora import FakeKora

NON_GITHUB = {"product-owner", "delivery-lead", "scrum-master", "sydney-trains", "lunch"}


def by_name(kora: FakeKora) -> dict[str, dict]:
    return {t["name"]: t for t in kora.triggers}


def test_first_deploy_creates_agents_and_triggers_paused():
    kora = FakeKora()
    report = deploy_factory(kora, "quiet", include_github=False)
    assert {a["slug"] for a in kora.agents} == NON_GITHUB
    triggers = by_name(kora)
    assert set(triggers) == {
        "Product owner: every 10 min",
        "Product owner: run now",
        "Delivery lead: every 10 min",
        "Delivery lead: stand-up",
        "Delivery lead: run now",
        "Delivery lead: stand-up now",
        "Scrum master: every 15 min",
        "Scrum master: run now",
        "Sydney trains: 07:00 weekdays",
        "Sydney trains: run now",
        "Lunch: 11:30 weekdays",
        "Lunch: run now",
    }
    assert triggers["Product owner: every 10 min"]["enabled"] is False
    assert triggers["Delivery lead: stand-up"]["enabled"] is False
    assert triggers["Sydney trains: 07:00 weekdays"]["enabled"] is True
    assert triggers["Lunch: run now"]["enabled"] is True
    assert len(report.created) == len(NON_GITHUB) + 12
    assert report.updated == ()


def test_deploy_twice_updates_in_place_and_keeps_paused():
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    patches_before = len(kora.patches)
    report = deploy_factory(kora, "quiet", include_github=False)
    assert report.created == ()
    assert len(report.updated) == len(NON_GITHUB) + 12
    assert len(kora.agents) == len(NON_GITHUB)
    assert len(kora.triggers) == 12
    later = kora.patches[patches_before:]
    assert all("enabled" not in patch for _, patch in later)
    assert by_name(kora)["Product owner: every 10 min"]["enabled"] is False


def test_redeploy_keeps_the_cadence_of_existing_schedules():
    kora = FakeKora()
    deploy_factory(kora, "recording", include_github=True)
    deploy_factory(kora, "quiet", include_github=True)
    triggers = by_name(kora)
    recording = {
        f"{spec.name}: {schedule.name}": schedule.cron_recording
        for spec in ROSTER
        for schedule in spec.schedules
    }
    assert {name: triggers[name]["schedule_config"]["cron_expression"] for name in recording} == (
        recording
    )


def test_deploy_refuses_when_an_agents_environment_is_missing():
    kora = FakeKora(environments=())
    with pytest.raises(LookupError, match="node-web"):
        deploy_factory(kora, "quiet", include_github=True)
    assert kora.agents == ()
    assert kora.triggers == ()


def test_github_agents_are_skipped_until_asked():
    kora = FakeKora()
    report = deploy_factory(kora, "quiet", include_github=False)
    assert len(report.skipped) == 4
    assert all("--with-github" in line for line in report.skipped)
    deploy_factory(kora, "quiet", include_github=True)
    assert {"senior-developer", "code-reviewer", "tester", "support"} <= {
        a["slug"] for a in kora.agents
    }


def test_deploy_waits_for_each_agent_before_its_triggers():
    kora = FakeKora()
    seen = []

    def wait(agent_id):
        seen.append((agent_id, len(kora.triggers)))

    deploy_factory(kora, "quiet", include_github=False, wait=wait)
    assert seen[0] == ("at-product-owner", 0)
    assert len(seen) == len(NON_GITHUB)


def test_resume_switches_cadence_and_enables_team_schedules_only():
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=True)
    assert set_team_schedules(kora, True, "recording") == ()
    triggers = by_name(kora)
    developer = triggers["Senior developer: every 5 min"]
    assert developer["enabled"] is True
    assert developer["schedule_config"]["cron_expression"] == "*/5 * * * *"
    trains_patches = [
        p for tid, p in kora.patches if tid == triggers["Sydney trains: 07:00 weekdays"]["id"]
    ]
    assert trains_patches == []
    assert set_team_schedules(kora, False, "quiet") == ()
    assert by_name(kora)["Senior developer: every 5 min"]["enabled"] is False
    assert by_name(kora)["Senior developer: every 5 min"]["schedule_config"]["cron_expression"] == (
        "*/15 * * * *"
    )


def test_pause_skips_schedules_not_deployed_yet():
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    assert set_team_schedules(kora, False, "quiet") == ()


def test_pause_reports_triggers_it_could_not_pause():
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    set_team_schedules(kora, True, "quiet")
    kora.fail_patch_for = "Scrum master: every 15 min"
    failed = set_team_schedules(kora, False, "quiet")
    assert failed == ("Scrum master: every 15 min",)
    assert by_name(kora)["Product owner: every 10 min"]["enabled"] is False


def test_pause_reports_http_failures_too():
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)

    def broken(trigger_id, patch):
        raise httpx.ConnectError("refused")

    kora.update_trigger = broken
    assert len(set_team_schedules(kora, False, "quiet")) == 4


def test_status_lists_schedules_with_cron_and_state():
    kora = FakeKora()
    deploy_factory(kora, "quiet", include_github=False)
    rows = factory_status(kora)
    assert ("Product owner: every 10 min", "*/10 * * * *", False) in rows
    assert ("Lunch: 11:30 weekdays", "30 11 * * 1-5", True) in rows
    assert all(not name.endswith("run now") for name, _, _ in rows)


def test_tenant_cap_set_when_missing_and_left_when_equal():
    kora = FakeKora()
    assert ensure_tenant_cap(kora) == {"limit_usd": TENANT_CAP_USD, "reset_cadence": "weekly"}
    assert kora.cap_sets == 1
    ensure_tenant_cap(kora)
    assert kora.cap_sets == 1
    other = FakeKora(cap={"limit_usd": 100.0, "reset_cadence": "monthly"})
    ensure_tenant_cap(other)
    assert other.cap == {"limit_usd": 60.0, "reset_cadence": "weekly"}
