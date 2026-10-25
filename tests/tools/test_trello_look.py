from typing import get_args

from factory_tools.lists import BOARD_LISTS
from factory_tools.trello.look import (
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
    type_label,
)


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
    assert unblocked == ("Bug",)
    kept = labels_after_move(("Bug", "Depends on"), "Ready", "Moving it back")
    assert kept == ("Bug", "Depends on")
    assert labels_after_move(("Depends on",), "Blocked", "Unblocked: no") == ("Depends on",)
    current = ("Story",)
    labels_after_move(current, "Done", "x")
    assert current == ("Story",)


def test_labels_after_move_drops_idea_outside_ideas():
    assert labels_after_move(("Idea", "Fixture"), "Backlog", "A story") == ("Fixture",)
    assert labels_after_move(("Idea",), "Blocked", "No clear value") == ()
    assert labels_after_move(("Idea", "Proposed via Telegram"), "Ideas", "") == (
        "Idea",
        "Proposed via Telegram",
    )
