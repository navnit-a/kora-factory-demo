from itertools import product
from typing import get_args

import pytest

from factory_tools.lists import BOARD_LISTS, display_name
from factory_tools.trello.look import (
    ACTOR_LABEL_NAMES,
    ACTOR_LABELS,
    CHECKLIST_NAME,
    LABELS,
    LANE_LOOK,
    LANE_STICKER_POS,
    LANE_STICKERS,
    STAR,
    STAR_POS,
    LabelName,
    LaneLook,
    labels_after_move,
    labels_on_create,
    mover,
    signed_reason,
    type_label,
)

ACTORS = {
    "💡 Product owner": "sky_dark",
    "📋 Delivery lead": "yellow_dark",
    "🤖 Senior developer": "purple_dark",
    "🔍 Code reviewer": "orange_dark",
    "🧪 Tester": "lime_dark",
    "🙋 Needs a human": "red_dark",
}


def test_lane_look_covers_every_list():
    assert set(LANE_LOOK) == set(BOARD_LISTS)
    expected = {
        "Ideas": LaneLook(None, None),
        "Backlog": LaneLook(None, None),
        "Ready": LaneLook("yellow", None),
        "In Progress": LaneLook("purple", None),
        "Review": LaneLook("orange", "rocketship"),
        "Testing": LaneLook("lime", "thumbsup"),
        "Done": LaneLook("green", "check"),
        "Blocked": LaneLook("red", "warning"),
    }
    assert expected == LANE_LOOK
    assert {look.sticker for look in LANE_LOOK.values()} - {None} == LANE_STICKERS
    assert STAR == "star" and STAR not in LANE_STICKERS


def test_palette_positions_and_checklist_name_match_the_plan():
    palette = {
        "Idea": "sky",
        "Story": "blue",
        "Bug": "red",
        "Spike": "purple",
        "High severity": "red",
        "Depends on": "orange",
        "Shipped": "green",
        "Proposed via Telegram": "pink",
        "Fixture": "black",
        **ACTORS,
    }
    assert palette == LABELS
    assert set(get_args(LabelName)) == set(LABELS)
    assert LANE_STICKER_POS == {"top": -10, "left": 70, "zIndex": 1}
    assert STAR_POS == {"top": -10, "left": 0, "zIndex": 2}
    assert CHECKLIST_NAME == "Acceptance criteria"


def test_type_label_prefers_the_prefix_over_the_lane():
    assert type_label("Bug: session times show in UTC [fixture]", "Ideas") == "Bug"
    assert type_label("Bug: crash on load", "Backlog") == "Bug"
    assert type_label("[fixture] Star a session", "Backlog") == "Fixture"
    assert type_label("Count the sessions [fixture]", "Ideas") == "Fixture"
    assert type_label("Spike: try a map", "Ideas") == "Spike"
    assert type_label("Dark mode", "Ideas") == "Idea"
    assert type_label("Dark mode", "Backlog") == "Story"
    assert type_label("Dark mode", "Ready") == "Story"


def test_labels_after_move_adds_shipped_and_drops_depends_on():
    assert labels_after_move(("Story",), "Done", "Tests pass") == ("Story", "Shipped")
    assert labels_after_move(("Story", "Shipped"), "Done", "again") == ("Story", "Shipped")
    unblocked = labels_after_move(("Bug", "Depends on"), "Ready", "Unblocked: API is back")
    assert unblocked == ("Bug", "📋 Delivery lead")
    kept = labels_after_move(("Bug", "Depends on"), "Ready", "Moving it back")
    assert kept == ("Bug", "Depends on", "📋 Delivery lead")
    blocked = labels_after_move(("Depends on",), "Blocked", "Unblocked: no")
    assert blocked == ("Depends on", "🙋 Needs a human")
    current = ("Story",)
    labels_after_move(current, "Done", "x")
    assert current == ("Story",)


def test_labels_after_move_drops_idea_outside_ideas():
    assert labels_after_move(("Idea", "Fixture"), "Backlog", "A story") == (
        "Fixture",
        "📋 Delivery lead",
    )
    assert labels_after_move(("Idea",), "Blocked", "No clear value") == ("🙋 Needs a human",)
    assert labels_after_move(("Idea", "Proposed via Telegram"), "Ideas", "") == (
        "Idea",
        "Proposed via Telegram",
        "💡 Product owner",
    )


def test_actor_labels_cover_every_lane():
    assert ACTOR_LABELS == {
        "Ideas": "💡 Product owner",
        "Backlog": "📋 Delivery lead",
        "Ready": "📋 Delivery lead",
        "In Progress": "🤖 Senior developer",
        "Review": "🔍 Code reviewer",
        "Testing": "🧪 Tester",
        "Done": None,
        "Blocked": "🙋 Needs a human",
    }
    assert set(ACTOR_LABELS) == set(BOARD_LISTS)
    assert frozenset(ACTORS) == ACTOR_LABEL_NAMES


def test_actor_labels_are_coloured_so_trello_shows_them():
    assert {name: LABELS[name] for name in ACTOR_LABEL_NAMES} == ACTORS
    assert all(LABELS[name] for name in ACTOR_LABEL_NAMES)


def test_move_swaps_actor_labels():
    current = ("Story", "🤖 Senior developer", "High severity")
    assert labels_after_move(current, "Review", "PR #4 opened") == (
        "Story",
        "High severity",
        "🔍 Code reviewer",
    )
    stale = ("Bug", "🧪 Tester", "💡 Product owner")
    assert labels_after_move(stale, "Ready", "Back to the queue") == ("Bug", "📋 Delivery lead")
    assert labels_after_move(("📋 Delivery lead",), "Ready", "again") == ("📋 Delivery lead",)


def test_done_removes_actor_labels():
    current = ("Story", "🧪 Tester", "🙋 Needs a human")
    assert labels_after_move(current, "Done", "Tests pass") == ("Story", "Shipped")


def test_create_carries_the_lanes_actor_label():
    assert labels_on_create("Dark mode", "Ideas") == ("Idea", "💡 Product owner")
    assert labels_on_create("Bug: crash [fixture]", "Backlog") == (
        "Bug",
        "Fixture",
        "📋 Delivery lead",
    )
    assert labels_on_create("Ship it", "Done") == ("Story",)


def test_signed_reason_formats_mover_destination_and_reason():
    assert signed_reason("In Progress", "Review", "PR https://github.com/x/y/pull/4") == (
        "🤖 Senior developer → 🔍 Review · code reviewer reads: PR https://github.com/x/y/pull/4"
    )
    assert signed_reason("Testing", "Done", "Tests pass") == (
        "🧪 Tester → ✅ Done · shipped: Tests pass"
    )
    assert signed_reason("Done", "In Progress", "Regression found") == (
        "✅ Done · shipped → 🛠 In Progress · senior developer builds: Regression found"
    )
    assert signed_reason("Blocked", "Ready", "Unblocked: the API is back") == (
        "📋 Delivery lead → 🟡 Ready · next for the developer: Unblocked: the API is back"
    )
    assert signed_reason("Ready", "In Progress", "Starting: the header count") == (
        "🤖 Senior developer → 🛠 In Progress · senior developer builds: Starting: the header count"
    )
    assert signed_reason(None, "Backlog", "Filed by support") == "Filed by support"


@pytest.mark.parametrize(
    ("from_list", "to_list", "expected"),
    [
        ("Ready", "In Progress", "🤖 Senior developer"),
        ("Backlog", "Ready", "📋 Delivery lead"),
        ("Blocked", "Ready", "📋 Delivery lead"),
        ("Ideas", "Ready", "📋 Delivery lead"),
        ("In Progress", "Review", "🤖 Senior developer"),
        ("Review", "Testing", "🔍 Code reviewer"),
        ("Testing", "Done", "🧪 Tester"),
        ("Review", "In Progress", "🔍 Code reviewer"),
        ("Testing", "In Progress", "🧪 Tester"),
        ("Ideas", "Backlog", "💡 Product owner"),
        ("In Progress", "Blocked", "🛠 In Progress · senior developer builds"),
        ("Review", "Blocked", "🔍 Review · code reviewer reads"),
        ("Done", "In Progress", "✅ Done · shipped"),
        ("Done", "Backlog", "✅ Done · shipped"),
    ],
)
def test_signed_reason_names_the_true_mover(from_list, to_list, expected):
    assert mover(from_list, to_list) == expected
    assert signed_reason(from_list, to_list, "why") == (
        f"{expected} → {display_name(to_list)}: why"
    )


def test_signed_move_comment_keeps_bookkeeping_prefixes_recognisable():
    prefixes = ("Depends on:", "Unblocked:", "Agent ops:")
    for from_list, to_list in product(BOARD_LISTS, BOARD_LISTS):
        signed = signed_reason(from_list, to_list, "Unblocked: the theme card shipped")
        assert not signed.startswith(prefixes)
        assert signed.endswith(f"{display_name(to_list)}: Unblocked: the theme card shipped")
    assert signed_reason(None, "Ready", "Unblocked: shipped").startswith("Unblocked:")
