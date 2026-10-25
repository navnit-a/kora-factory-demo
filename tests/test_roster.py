from collections import Counter

import pytest

from factory_demo.roster import (
    CARD_TICK,
    GITHUB_DATA,
    GITHUB_RESOURCE,
    HAIKU,
    PYTHON_TOOLS,
    ROSTER,
    SONNET,
    WATCHED,
    Schedule,
    by_slug,
    every,
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
DATA_AGENTS = {"sydney-trains", "lunch"}
GITHUB_AGENTS = {*BUILDERS, *DATA_AGENTS, "support", "idea-scout", "agent-ops"}
SANDBOXED = {*DATA_AGENTS, "agent-ops"}
SONNET_AGENTS = {"senior-developer", "code-reviewer", "idea-scout", "agent-ops"}
BUDGETS = {
    "senior-developer": (0.40, 10.0),
    "idea-scout": (0.15, 5.0),
    "agent-ops": (0.40, 5.0),
    "sydney-trains": (0.30, 3.0),
    "lunch": (0.30, 3.0),
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
        on_node = spec.slug in GITHUB_AGENTS - SANDBOXED
        assert (spec.environment == "node-web") == on_node, spec.slug
        assert (spec.environment == "python-tools") == (spec.slug in SANDBOXED), spec.slug


def test_data_agents_hold_a_planner_write_grant_and_a_sandbox():
    for slug in DATA_AGENTS:
        spec = by_slug(slug)
        assert spec.github_actions == GITHUB_DATA
        assert not {"checks:read", "actions:read"} & set(spec.github_actions)
        assert spec.environment == PYTHON_TOOLS
        assert spec.github_resources == (GITHUB_RESOURCE,)


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
    assert writers == {"senior-developer", "tester", *DATA_AGENTS}
    assert "contents:write" not in by_slug("code-reviewer").github_actions


def test_team_cadences():
    crons = {
        spec.slug: [(s.cron_recording, s.cron_quiet) for s in spec.schedules] for spec in ROSTER
    }
    assert crons["product-owner"] == [("3-59/10 * * * *", "3-59/10 * * * *")]
    assert crons["delivery-lead"] == [
        ("4-59/10 * * * *", "4-59/10 * * * *"),
        ("0 9 * * 1-5", "0 9 * * 1-5"),
    ]
    assert crons["scrum-master"] == [("6-59/15 * * * *", "6-59/15 * * * *")]
    assert crons["senior-developer"] == [("*/5 * * * *", "*/15 * * * *")]
    assert crons["code-reviewer"] == [("1-59/5 * * * *", "1-59/15 * * * *")]
    assert crons["tester"] == [("2-59/5 * * * *", "2-59/15 * * * *")]
    assert crons["support"] == [("8-59/15 * * * *", "8-59/15 * * * *")]
    assert crons["sydney-trains"] == [("0 7 * * 1-5", "0 7 * * 1-5")]
    assert crons["lunch"] == [("30 11 * * 1-5", "30 11 * * 1-5")]
    assert crons["idea-scout"] == []
    assert crons["agent-ops"] == [("12-59/30 * * * *", "12 * * * *")]


def test_every_offsets_the_minute():
    schedule = every(5, 15, offset=2)
    assert schedule.cron_recording == "2-59/5 * * * *"
    assert schedule.cron_quiet == "2-59/15 * * * *"
    assert every(10).cron_recording == "*/10 * * * *"
    assert every(10, offset=0).cron_quiet == "*/10 * * * *"


def test_every_rejects_an_offset_beyond_the_interval():
    with pytest.raises(ValueError, match="offset"):
        every(5, offset=5)
    with pytest.raises(ValueError, match="offset"):
        every(10, 15, offset=12)


def minutes_of(cron: str) -> tuple[int, ...]:
    field = cron.split()[0]
    span, _, step = field.partition("/")
    start = 0 if span == "*" else int(span.split("-")[0])
    return tuple(range(start, 60, int(step))) if step else (start,)


def test_no_two_team_agents_start_on_the_same_minute_at_recording_cadence():
    starts = tuple(
        (minute, spec.slug)
        for spec in ROSTER
        for schedule in spec.schedules
        if schedule.team and "/" in schedule.cron_recording.split()[0]
        for minute in minutes_of(schedule.cron_recording)
    )
    per_minute = Counter(minute for minute, _ in starts)
    assert max(per_minute.values()) <= 2, per_minute
    for minute in range(60):
        slugs = {slug for at, slug in starts if at == minute}
        assert not slugs >= BUILDERS, minute


def test_every_schedule_pauses_with_the_session():
    for spec in ROSTER:
        assert all(s.team for s in spec.schedules), spec.slug


def test_write_capable_agents_have_only_team_schedules():
    for spec in ROSTER:
        if spec.github_actions:
            assert all(s.team for s in spec.schedules), spec.slug


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


GENERIC_TRELLO_WRITES = (
    "trello_move_card",
    "trello_comment_card",
    "trello_create_card",
    "trello_update_card_description",
    "trello_add_label",
    "trello_add_checklist",
    "trello_check_item",
    "trello_set_priority",
)


def test_agent_ops_holds_only_narrow_write_tools():
    ops = by_slug("agent-ops")
    assert ops.tools == (
        "trello_list_cards",
        "trello_get_card",
        "trello_write_watch_log",
        "trello_mark_diagnosed",
        "telegram_send_message",
        *PLATFORM_TOOLS["kora"],
    )
    assert not set(GENERIC_TRELLO_WRITES) & set(ops.tools)
    assert ops.grant_scopes == (
        *(f"agents:runs:{slug}:read" for slug in WATCHED),
        "agents:runs:agent-ops:read",
        "triggers:read",
    )


def test_agent_ops_quiet_cron_is_hourly():
    assert by_slug("agent-ops").schedules == (
        Schedule("every 30 min", "12-59/30 * * * *", "12 * * * *", CARD_TICK, True),
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
        "latitude": "-33.8781",
        "longitude": "151.2077",
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


BOARD_TOOLS = {
    "trello_add_checklist": {"product-owner"},
    "trello_add_label": {"product-owner", "delivery-lead", "support"},
    "trello_update_card_description": {"product-owner"},
    "trello_write_watch_log": {"agent-ops"},
    "trello_mark_diagnosed": {"agent-ops"},
    "trello_check_item": {"tester"},
    "trello_set_priority": {"delivery-lead", "support"},
}


def test_board_language_tools_go_only_to_the_roles_that_use_them():
    for tool, holders in BOARD_TOOLS.items():
        assert {spec.slug for spec in ROSTER if tool in spec.tools} == holders, tool
