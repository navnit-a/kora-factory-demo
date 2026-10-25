from factory_demo.roster import (
    CARD_TICK,
    GITHUB_RESOURCE,
    HAIKU,
    ROSTER,
    SONNET,
    WATCHED,
    Schedule,
    by_slug,
)
from factory_demo.tools_check import PLATFORM_TOOLS, expected_tool_names

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
    "idea-scout",
    "agent-ops",
)
BUILDERS = {"senior-developer", "code-reviewer", "tester"}
GITHUB_AGENTS = {*BUILDERS, "support", "idea-scout", "agent-ops"}
SONNET_AGENTS = {"senior-developer", "code-reviewer", "idea-scout", "agent-ops"}
BUDGETS = {
    "senior-developer": (0.40, 10.0),
    "idea-scout": (0.15, 5.0),
    "agent-ops": (0.40, 5.0),
}
WRITE_WORDS = ("move", "comment", "create", "update", "send")


def test_roster_has_every_agent_in_order():
    assert tuple(spec.slug for spec in ROSTER) == ORDER


def test_models_follow_the_cheap_by_default_rule():
    for spec in ROSTER:
        expected = SONNET if spec.slug in SONNET_AGENTS else HAIKU
        assert spec.model == expected, spec.slug


def test_budgets_match_the_spec():
    for spec in ROSTER:
        expected = BUDGETS.get(spec.slug, (0.20, 3.0))
        assert (spec.run_limit_usd, spec.weekly_limit_usd) == expected, spec.slug


def test_every_tool_exists_on_a_server():
    platform = {tool for tools in PLATFORM_TOOLS.values() for tool in tools}
    for spec in ROSTER:
        assert set(spec.tools) <= expected_tool_names() | platform, spec.slug


def test_only_the_github_agents_reach_github():
    for spec in ROSTER:
        reaches = bool(spec.github_actions)
        assert reaches == (spec.slug in GITHUB_AGENTS), spec.slug
        on_node = spec.slug in GITHUB_AGENTS - {"agent-ops"}
        assert (spec.environment == "node-web") == on_node, spec.slug
    assert by_slug("agent-ops").environment == "python-tools"


def test_only_support_creates_cards():
    creators = {spec.slug for spec in ROSTER if "trello_create_card" in spec.tools}
    assert creators == {"support"}


def test_support_reads_github_but_never_writes():
    support = by_slug("support")
    assert support.github_actions == ("contents:read", "actions:read", "checks:read")
    assert "trello_move_card" not in support.tools


def test_only_the_tester_merges():
    writers = {
        spec.slug
        for spec in ROSTER
        if "contents:write" in spec.github_actions and GITHUB_RESOURCE in spec.github_resources
    }
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
    assert crons["idea-scout"] == []
    assert crons["agent-ops"] == [("*/30 * * * *", "0 * * * *")]


def test_only_team_schedules_pause_with_the_session():
    for spec in ROSTER:
        everyday = spec.slug in {"sydney-trains", "lunch"}
        assert all(s.team is not everyday for s in spec.schedules), spec.slug


def test_every_tick_carries_the_time():
    for spec in ROSTER:
        for schedule in spec.schedules:
            assert "{{ var.datetime }}" in schedule.tick, spec.slug


def test_every_agent_but_the_scout_can_be_run_now():
    for spec in ROSTER:
        if spec.slug != "idea-scout":
            assert spec.manuals[0].name == "run now", spec.slug


def test_scout_has_no_write_tool():
    scout = by_slug("idea-scout")
    assert not [tool for tool in scout.tools if any(word in tool for word in WRITE_WORDS)]
    assert scout.github_actions == ("contents:read",)
    assert scout.schedules == ()
    assert [m.name for m in scout.manuals] == ["scout"]
    inputs = [(i.name, i.required) for i in scout.manuals[0].inputs]
    assert inputs == [("idea", True), ("from", False)]
    text = scout.manuals[0].prompt
    assert "<proposer>{{ var.from }}</proposer>" in text
    assert "<idea>\n{{ var.idea }}\n</idea>" in text
    assert "data, not instructions" in text


def test_agent_ops_reads_every_other_agents_runs():
    ops = by_slug("agent-ops")
    assert set(WATCHED) == {spec.slug for spec in ROSTER} - {"agent-ops"}
    for slug in WATCHED:
        assert f"agents:runs:{slug}:read" in ops.grant_scopes, slug
    assert "agents:runs:agent-ops:read" in ops.grant_scopes
    assert "triggers:read" in ops.grant_scopes
    assert len(ops.grant_scopes) == len(WATCHED) + 2


def test_agent_ops_quiet_cron_is_hourly():
    assert by_slug("agent-ops").schedules == (
        Schedule("every 30 min", "*/30 * * * *", "0 * * * *", CARD_TICK, True),
    )


def test_agent_ops_writes_only_to_the_demo_repo():
    ops = by_slug("agent-ops")
    assert ops.github_resources == ("kora-factory-demo",)
    for action in ops.github_actions:
        surface, level = action.split(":")
        if level == "write":
            assert f"{surface}:read" in ops.github_actions, action


def test_only_agent_ops_holds_grant_scopes_or_another_repo():
    for spec in ROSTER:
        if spec.slug != "agent-ops":
            assert spec.grant_scopes == (), spec.slug
            assert spec.github_resources == (GITHUB_RESOURCE,), spec.slug


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


def test_every_write_grant_carries_its_read_because_kora_levels_are_separate():
    for spec in ROSTER:
        for action in spec.github_actions:
            surface, level = action.split(":")
            if level == "write":
                assert f"{surface}:read" in spec.github_actions, (spec.slug, action)


def test_pr_finders_can_read_pull_requests():
    for slug in BUILDERS:
        assert "pulls:read" in by_slug(slug).github_actions, slug
