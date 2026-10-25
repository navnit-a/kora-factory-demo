from factory_demo.roster import HAIKU, ROSTER, SONNET, by_slug
from factory_demo.tools_check import expected_tool_names

ORDER = (
    "product-owner",
    "delivery-lead",
    "scrum-master",
    "senior-developer",
    "code-reviewer",
    "tester",
    "support",
    "sydney-trains",
    "lunch",
)
BUILDERS = {"senior-developer", "code-reviewer", "tester"}
GITHUB_AGENTS = {*BUILDERS, "support"}


def test_roster_has_the_eight_agents_in_order():
    assert tuple(spec.slug for spec in ROSTER) == ORDER


def test_models_follow_the_cheap_by_default_rule():
    for spec in ROSTER:
        expected = SONNET if spec.slug in {"senior-developer", "code-reviewer"} else HAIKU
        assert spec.model == expected, spec.slug


def test_budgets_match_the_spec():
    for spec in ROSTER:
        if spec.slug == "senior-developer":
            assert (spec.run_limit_usd, spec.weekly_limit_usd) == (0.40, 10.0)
        else:
            assert (spec.run_limit_usd, spec.weekly_limit_usd) == (0.20, 3.0), spec.slug


def test_every_tool_exists_on_a_server():
    for spec in ROSTER:
        assert set(spec.tools) <= expected_tool_names(), spec.slug


def test_only_developer_reviewer_tester_reach_github():
    for spec in ROSTER:
        reaches = bool(spec.github_actions)
        assert reaches == (spec.slug in GITHUB_AGENTS), spec.slug
        assert (spec.environment == "node-web") == (spec.slug in GITHUB_AGENTS), spec.slug


def test_only_support_creates_cards():
    creators = {spec.slug for spec in ROSTER if "trello_create_card" in spec.tools}
    assert creators == {"support"}


def test_support_reads_github_but_never_writes():
    support = by_slug("support")
    assert support.github_actions == ("contents:read", "actions:read", "checks:read")
    assert "trello_move_card" not in support.tools


def test_only_the_tester_merges():
    writers = {spec.slug for spec in ROSTER if "contents:write" in spec.github_actions}
    assert writers == {"senior-developer", "tester"}
    assert "contents:write" not in by_slug("code-reviewer").github_actions


def test_team_cadences():
    crons = {
        spec.slug: [(s.cron_recording, s.cron_quiet) for s in spec.schedules] for spec in ROSTER
    }
    assert crons["product-owner"] == [("*/10 * * * *", "*/10 * * * *")]
    assert crons["delivery-lead"] == [
        ("*/10 * * * *", "*/10 * * * *"),
        ("0 9 * * 1-5", "0 9 * * 1-5"),
    ]
    assert crons["scrum-master"] == [("*/15 * * * *", "*/15 * * * *")]
    for slug in BUILDERS:
        assert crons[slug] == [("*/5 * * * *", "*/15 * * * *")]
    assert crons["support"] == [("*/15 * * * *", "*/15 * * * *")]
    assert crons["sydney-trains"] == [("0 7 * * 1-5", "0 7 * * 1-5")]
    assert crons["lunch"] == [("30 11 * * 1-5", "30 11 * * 1-5")]


def test_only_team_schedules_pause_with_the_session():
    for spec in ROSTER:
        everyday = spec.slug in {"sydney-trains", "lunch"}
        assert all(s.team is not everyday for s in spec.schedules), spec.slug


def test_every_tick_carries_the_time():
    for spec in ROSTER:
        for schedule in spec.schedules:
            assert "{{ var.datetime }}" in schedule.tick, spec.slug


def test_every_agent_can_be_run_now():
    for spec in ROSTER:
        assert spec.manuals[0].name == "run now", spec.slug


def test_scrum_master_run_now_asks_for_the_time():
    manual = by_slug("scrum-master").manuals[0]
    assert "{{ var.now }}" in manual.prompt
    assert [(i.name, i.required) for i in manual.inputs] == [("now", True)]


def test_lunch_run_now_defaults_to_the_venue():
    manual = by_slug("lunch").manuals[0]
    inputs = {i.name: i.default for i in manual.inputs}
    assert inputs == {
        "place": "Sydney Masonic Centre",
        "latitude": "-33.8776",
        "longitude": "151.2048",
    }
    for name in inputs:
        assert "{{ var." + name + " }}" in manual.prompt


def test_delivery_lead_can_post_the_stand_up_on_demand():
    names = [m.name for m in by_slug("delivery-lead").manuals]
    assert names == ["run now", "stand-up now"]
