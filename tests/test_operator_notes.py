from datetime import UTC, datetime, timedelta, timezone

from factory_demo.operator_notes import operator_notes, post_operator_notes
from factory_demo.practices import OPERATOR_PREFIX
from factory_demo.prompts.scrum_master import PROMPT
from tests.fake_board import FakeBoard, card

WHEN = datetime(2026, 10, 25, 18, 7, tzinfo=UTC)
PAUSED = "Operator: the team is paused from 18:07; the idle clock stops."
RESUMED = "Operator: the team resumed at 18:07; the idle clock restarts now."


def test_operator_prefix_is_the_agreed_prefix():
    assert OPERATOR_PREFIX == "Operator:"
    assert f"comment starting `{OPERATOR_PREFIX}`" in " ".join(PROMPT.split())


def test_operator_notes_name_every_in_flight_card():
    lanes = {
        "In Progress": [{"id": "c1"}],
        "Review": [{"id": "c2"}, {"id": "c3"}],
        "Testing": [{"id": "c4"}],
        "Done": [{"id": "c5"}],
    }
    assert operator_notes(lanes, "pause", WHEN) == (
        ("c1", PAUSED),
        ("c2", PAUSED),
        ("c3", PAUSED),
        ("c4", PAUSED),
    )
    assert operator_notes({"Review": [{"id": "c2"}]}, "resume", WHEN) == (("c2", RESUMED),)


def test_operator_notes_use_utc_time():
    sydney = WHEN.astimezone(timezone(timedelta(hours=11)))
    assert operator_notes({"Testing": [{"id": "c4"}]}, "pause", sydney) == (("c4", PAUSED),)


def test_operator_notes_are_empty_when_nothing_is_in_flight():
    assert operator_notes({"In Progress": [], "Review": [], "Testing": []}, "pause", WHEN) == ()


async def test_post_operator_notes_comments_on_the_three_lanes_only():
    board = FakeBoard(
        {},
        {
            "c1": card("In Progress", "Agenda"),
            "c2": card("Review", "Filter"),
            "c3": card("Done", "Hero"),
            "c4": card("Ready", "Footer"),
        },
    )
    posted = await post_operator_notes(board, "resume", WHEN)
    assert posted == (("c1", RESUMED), ("c2", RESUMED))
    assert board.cards["c1"]["comments"] == (RESUMED,)
    assert board.cards["c2"]["comments"] == (RESUMED,)
    assert board.cards["c3"]["comments"] == ()
