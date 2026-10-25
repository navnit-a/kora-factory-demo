from dataclasses import FrozenInstanceError
from typing import get_args

import pytest

from factory_tools.lists import (
    BOARD_LISTS,
    LANES,
    ListName,
    actor_label,
    canonical_name,
    display_name,
    lane_display_names,
)

DISPLAY_NAMES = (
    "💡 Ideas · product owner shapes",
    "📋 Backlog · delivery lead orders",
    "🟡 Ready · next for the developer",
    "🛠 In Progress · senior developer builds",
    "🔍 Review · code reviewer reads",
    "🧪 Testing · tester proves",
    "✅ Done · shipped",
    "⛔ Blocked · needs a human",
    "🛰 Agent ops · watching the agents",
)


def test_board_lists_are_the_nine_in_board_order():
    assert BOARD_LISTS == (
        "Ideas",
        "Backlog",
        "Ready",
        "In Progress",
        "Review",
        "Testing",
        "Done",
        "Blocked",
        "Agent ops",
    )


def test_list_name_literal_agrees_with_the_lanes():
    assert get_args(ListName) == BOARD_LISTS
    assert tuple(lane.name for lane in LANES) == BOARD_LISTS


def test_lanes_carry_the_exact_display_names_in_board_order():
    assert lane_display_names() == DISPLAY_NAMES
    assert all(" · " in name for name in DISPLAY_NAMES)
    assert display_name("In Progress") == "🛠 In Progress · senior developer builds"


def test_lanes_name_their_actor():
    assert {name: actor_label(name) for name in BOARD_LISTS} == {
        "Ideas": "💡 Product owner",
        "Backlog": "📋 Delivery lead",
        "Ready": "📋 Delivery lead",
        "In Progress": "🤖 Senior developer",
        "Review": "🔍 Code reviewer",
        "Testing": "🧪 Tester",
        "Done": None,
        "Blocked": "🙋 Needs a human",
        "Agent ops": "🛰 Agent ops",
    }


def test_lanes_are_frozen():
    with pytest.raises(FrozenInstanceError):
        LANES[0].name = "Other"


def test_unknown_lane_is_refused_naming_the_lanes():
    with pytest.raises(ValueError, match="No lane named 'Code review'.*Ideas, Backlog"):
        display_name("Code review")
    with pytest.raises(ValueError, match="No lane named 'Shipped'"):
        actor_label("Shipped")


def test_canonical_name_strips_icon_and_actor():
    assert tuple(canonical_name(name) for name in DISPLAY_NAMES) == BOARD_LISTS
    assert canonical_name("  🛠️ in progress · whoever builds  ") == "In Progress"
    assert canonical_name("✅✅ DONE · shipped · twice") == "Done"


def test_canonical_name_accepts_plain_names():
    assert tuple(canonical_name(name) for name in BOARD_LISTS) == BOARD_LISTS
    assert canonical_name("in progress") == "In Progress"
    assert canonical_name(" Blocked ") == "Blocked"


def test_agent_ops_lane_comes_last_and_matches_its_display_name():
    assert LANES[-1].name == "Agent ops"
    assert display_name("Agent ops") == "🛰 Agent ops · watching the agents"
    assert canonical_name("🛰 Agent ops · watching the agents") == "Agent ops"
    assert canonical_name("🛰️ agent OPS") == "Agent ops"
    assert canonical_name("Agent ops watch log") is None


@pytest.mark.parametrize(
    "raw", ["", "💡", "Code review", "Ideas and more", "🔍 Reviews · code reviewer", "Done·shipped"]
)
def test_canonical_name_rejects_unknown(raw):
    assert canonical_name(raw) is None
