from factory_demo.dress_board import (
    DressReport,
    criteria_from_description,
    dress,
    names_prerequisite,
    plan_labels,
    report_lines,
)
from tests.fake_board import FakeBoard, card

COLOURS = ("blue", "green", "orange", "purple", "red", "yellow")
UNNAMED = {f"l-{colour}": {"name": "", "color": colour} for colour in COLOURS}
PALETTE_PLAN = (
    ("create", "Idea", "sky"),
    ("rename", "Story", "blue"),
    ("rename", "Bug", "red"),
    ("rename", "Spike", "purple"),
    ("create", "High severity", "red"),
    ("rename", "Depends on", "orange"),
    ("rename", "Shipped", "green"),
    ("create", "Proposed via Telegram", "pink"),
    ("create", "Fixture", "black"),
    ("rename", "Ready", "yellow"),
)
DESCRIPTION = (
    "As an attendee I want to filter by track.\n\n"
    "Acceptance Criteria:\n"
    "- Picking a track shows only its sessions\n"
    "- Clearing the filter shows the full day\n\n"
    "Notes: keep it small."
)


def board() -> FakeBoard:
    return FakeBoard(
        UNNAMED,
        {
            "c-idea": card("Ideas", "Show what is on now and next"),
            "c-review": card(
                "Review",
                "Bug: wrong start time",
                stickers=("rocketship", "rocketship", "star"),
                description="## acceptance criteria\n- Times match the source",
            ),
            "c-done": card("Done", "Filter the schedule by track", description=DESCRIPTION),
            "c-blocked": card(
                "Blocked",
                "[fixture] probe the board",
                comments=("Blocked: the theme card is a prerequisite", "Started"),
            ),
            "c-progress": card(
                "In Progress",
                "Spike: try a tile grid",
                cover="purple",
                labels=("Spike",),
                checklist=("Grid renders",),
                description=DESCRIPTION,
            ),
            "c-backlog": card("Backlog", "Share my agenda", cover="yellow", stickers=("check",)),
        },
    )


def test_plan_labels_renames_colour_labels_and_creates_the_rest():
    assert plan_labels(UNNAMED) == PALETTE_PLAN


def test_plan_labels_keeps_named_labels_and_skips_ready_without_yellow():
    existing = {
        "a": {"name": "Bug", "color": "red"},
        "b": {"name": "", "color": "red"},
        "c": {"name": "Story", "color": "blue"},
    }
    plan = plan_labels(existing)
    assert ("keep", "Bug", "red") in plan
    assert ("keep", "Story", "blue") in plan
    assert ("create", "High severity", "red") in plan
    assert all(name != "Ready" for _, name, _ in plan)


def test_plan_labels_keeps_a_ready_label():
    plan = plan_labels({"y": {"name": "Ready", "color": "yellow"}})
    assert plan[-1] == ("keep", "Ready", "yellow")


def test_criteria_from_description_reads_the_bulleted_section():
    assert criteria_from_description(DESCRIPTION) == (
        "Picking a track shows only its sessions",
        "Clearing the filter shows the full day",
    )
    assert criteria_from_description("**Acceptance criteria**\n\n- One\n  - Two\n\nAfter\n- x") == (
        "One",
        "Two",
    )
    assert criteria_from_description("## Acceptance criteria\nTBD\n## Notes\n- not this") == ()
    assert criteria_from_description("- a bullet with no heading") == ()
    assert criteria_from_description("") == ()


def test_names_prerequisite_reads_the_last_comment_only_as_a_dependency():
    assert names_prerequisite("Depends on: the theme card")
    assert names_prerequisite("Blocked: waiting, this DEPENDS ON the data card")
    assert names_prerequisite("Blocked: the API key is a prerequisite")
    assert not names_prerequisite("Blocked: the build is red")
    assert not names_prerequisite("Unblocked: the prerequisite shipped")
    assert not names_prerequisite("")


async def test_dress_board_applies_the_look_to_every_card():
    trello = board()
    report = await dress(trello, dry_run=False)
    cards = trello.cards
    assert report == DressReport(PALETTE_PLAN, 5, 2)
    assert {label["name"] for label in trello.labels.values()} >= {"Story", "Ready", "Fixture"}
    assert cards["c-idea"]["labels"] == ("Idea",)
    assert cards["c-review"]["cover"] == "orange"
    assert cards["c-review"]["stickers"] == ("star", "rocketship")
    assert cards["c-review"]["labels"] == ("Bug",)
    assert cards["c-review"]["checklist"] == ("Times match the source",)
    assert cards["c-done"]["stickers"] == ("check",)
    assert cards["c-done"]["labels"] == ("Story", "Shipped")
    assert len(cards["c-done"]["checklist"]) == 2
    assert cards["c-blocked"]["cover"] == "red"
    assert cards["c-blocked"]["labels"] == ("Fixture", "Depends on")
    assert cards["c-progress"]["checklist"] == ("Grid renders",)
    assert cards["c-progress"]["labels"] == ("Spike",)
    assert cards["c-backlog"]["cover"] == "yellow"
    assert cards["c-backlog"]["stickers"] == ("check",)
    assert cards["c-backlog"]["labels"] == ("Story",)


async def test_dress_board_is_idempotent():
    trello = board()
    await dress(trello, dry_run=False)
    trello.writes = ()
    again = await dress(trello, dry_run=False)
    assert trello.writes == ()
    assert again.cards_dressed == 0 and again.checklists_added == 0
    assert all(action == "keep" for action, _, _ in again.labels)


async def test_dry_run_writes_nothing():
    trello = board()
    planned = await dress(trello, dry_run=True)
    assert trello.writes == ()
    assert planned == await dress(board(), dry_run=False)


def test_report_lines_name_each_label_action_and_the_counts():
    report = DressReport((("rename", "Story", "blue"), ("create", "Idea", "sky")), 3, 1)
    assert report_lines(report, dry_run=False) == (
        "rename label Story (blue)",
        "create label Idea (sky)",
        "3 card(s) dressed",
        "1 checklist(s) added",
    )
    assert report_lines(report, dry_run=True)[-1] == "dry run: nothing was written"
