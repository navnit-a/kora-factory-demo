from factory_demo.dress_board import (
    DressReport,
    criteria_from_description,
    dress,
    names_prerequisite,
    plan_labels,
    report_lines,
)
from factory_tools.lists import BOARD_LISTS, display_name
from factory_tools.trello.look import signed_reason
from tests.fake_board import FakeBoard, card

COLOURS = ("blue", "green", "orange", "purple", "red", "yellow")
UNNAMED = {f"l-{colour}": {"name": "", "color": colour} for colour in COLOURS}
SPIKE = {"l-spike": {"name": "Spike", "color": "purple"}}
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
    ("create", "💡 Product owner", "sky_dark"),
    ("create", "📋 Delivery lead", "yellow_dark"),
    ("create", "🤖 Senior developer", "purple_dark"),
    ("create", "🔍 Code reviewer", "orange_dark"),
    ("create", "🧪 Tester", "lime_dark"),
    ("create", "🙋 Needs a human", "red_dark"),
    ("create", "🛰 Agent ops", "blue_light"),
    ("rename", "Ready", "yellow"),
)
BOARD_PLAN = tuple(
    ("keep", "Spike", "purple") if name == "Spike" else (action, name, colour)
    for action, name, colour in PALETTE_PLAN
)
RENAMED_ALL = tuple((name, display_name(name)) for name in BOARD_LISTS)
WATCH_LOG = "🛰 Agent ops watch log"
WATCH_LOG_DESCRIPTION = "Agent ops writes what it checked and found here after every run."
DESCRIPTION = (
    "As an attendee I want to filter by track.\n\n"
    "Acceptance Criteria:\n"
    "- Picking a track shows only its sessions\n"
    "- Clearing the filter shows the full day\n\n"
    "Notes: keep it small."
)


def board() -> FakeBoard:
    return FakeBoard(
        {**UNNAMED, **SPIKE},
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
                labels=("l-spike",),
                checklist=("Grid renders",),
                description=DESCRIPTION,
            ),
            "c-backlog": card("Backlog", "Share my agenda", cover="yellow", stickers=("check",)),
        },
    )


def test_plan_labels_renames_colour_labels_and_creates_the_rest():
    assert plan_labels(UNNAMED) == PALETTE_PLAN
    assert plan_labels({**UNNAMED, **SPIKE})[3] == ("keep", "Spike", "purple")


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


def test_names_prerequisite_reads_signed_move_comments():
    unblocked = signed_reason("Blocked", "Ready", "Unblocked: the prerequisite shipped")
    blocked = signed_reason("In Progress", "Blocked", "Blocked: the theme card is a prerequisite")
    assert not names_prerequisite(unblocked)
    assert names_prerequisite(blocked)


async def test_dress_board_applies_the_look_to_every_card():
    trello = board()
    report = await dress(trello, dry_run=False)
    cards = trello.cards
    assert report == DressReport(BOARD_PLAN, 6, 2, (), RENAMED_ALL, (), (WATCH_LOG,))
    assert report.lists_renamed == 9
    assert {label["name"] for label in trello.labels.values()} >= {"Story", "Ready", "Fixture"}
    assert trello.names("c-idea") == ("Idea", "💡 Product owner")
    assert cards["c-review"]["cover"] == "orange"
    assert cards["c-review"]["stickers"] == ("star", "rocketship")
    assert trello.names("c-review") == ("Bug", "🔍 Code reviewer")
    assert cards["c-review"]["checklist"] == ("Times match the source",)
    assert cards["c-done"]["stickers"] == ("check",)
    assert trello.names("c-done") == ("Story", "Shipped")
    assert len(cards["c-done"]["checklist"]) == 2
    assert cards["c-blocked"]["cover"] == "red"
    assert trello.names("c-blocked") == ("Fixture", "Depends on", "🙋 Needs a human")
    assert cards["c-progress"]["checklist"] == ("Grid renders",)
    assert trello.names("c-progress") == ("Spike", "🤖 Senior developer")
    assert cards["c-backlog"]["cover"] == "yellow"
    assert cards["c-backlog"]["stickers"] == ("check",)
    assert trello.names("c-backlog") == ("Story", "📋 Delivery lead")


async def test_dress_board_is_idempotent():
    trello = board()
    await dress(trello, dry_run=False)
    trello.writes = ()
    again = await dress(trello, dry_run=False)
    assert trello.writes == ()
    assert again.cards_dressed == 0 and again.checklists_added == 0
    assert again.lists_renamed == 0
    assert all(action == "keep" for action, _, _ in again.labels)


async def test_dry_run_writes_nothing():
    trello = board()
    planned = await dress(trello, dry_run=True)
    assert trello.writes == ()
    assert planned == await dress(board(), dry_run=False)


def test_report_lines_name_each_label_action_and_the_counts():
    report = DressReport(
        (("rename", "Story", "blue"), ("create", "Idea", "sky")),
        3,
        1,
        (("Share my agenda", "Bug"),),
    )
    assert report_lines(report, dry_run=False) == (
        "rename label Story (blue)",
        "create label Idea (sky)",
        "Cards whose colour label becomes:",
        "  Share my agenda: Bug",
        "3 card(s) dressed",
        "1 checklist(s) added",
    )
    assert report_lines(report, dry_run=True)[-1] == "dry run: nothing was written"
    quiet = DressReport((), 0, 0, ())
    assert report_lines(quiet, dry_run=False)[0] == "Cards whose colour label becomes: none"


def test_report_lines_name_renamed_lanes_and_label_colours():
    report = DressReport(
        (("create", "💡 Product owner", "sky_dark"),), 0, 0, (), (("Ideas", display_name("Ideas")),)
    )
    lines = report_lines(report, dry_run=False)
    assert lines[:2] == (
        "rename lane Ideas → 💡 Ideas · product owner shapes",
        "create label 💡 Product owner (sky_dark)",
    )
    assert report.lists_renamed == 1


def tagged_board() -> FakeBoard:
    return FakeBoard(
        UNNAMED,
        {
            "c-red": card("Backlog", "Share my agenda", labels=("l-red",)),
            "c-green": card(
                "Ready", "Filter by track", cover="yellow", labels=("l-green", "l-blue")
            ),
            "c-plain": card("Backlog", "Switch between light and dark"),
        },
    )


async def test_dry_run_reports_cards_whose_colour_labels_change_meaning():
    trello = tagged_board()
    planned = await dress(trello, dry_run=True)
    assert trello.writes == ()
    assert planned.relabelled_cards == (
        ("Filter by track", "Shipped"),
        ("Filter by track", "Story"),
        ("Share my agenda", "Bug"),
    )
    assert "  Share my agenda: Bug" in report_lines(planned, dry_run=True)


async def test_dry_run_and_real_run_agree_on_type_labels():
    planned = await dress(tagged_board(), dry_run=True)
    trello = tagged_board()
    applied = await dress(trello, dry_run=False)
    assert planned == applied
    assert applied.cards_dressed == 3
    assert trello.names("c-red") == ("Bug", "📋 Delivery lead")
    assert trello.names("c-green") == ("Shipped", "Story", "📋 Delivery lead")
    assert trello.names("c-plain") == ("Story", "📋 Delivery lead")


PARTLY_DRESSED_LISTS = (
    *({"id": f"list-{n}", "name": name} for n, name in enumerate(BOARD_LISTS) if name != "Done"),
    {"id": "list-done", "name": display_name("Done")},
    {"id": "list-parking", "name": "Parking lot"},
)


async def test_dress_renames_lanes_once():
    trello = FakeBoard(
        UNNAMED, {"c-plain": card("Backlog", "Share my agenda")}, PARTLY_DRESSED_LISTS
    )
    first = await dress(trello, dry_run=False)
    assert first.lists_renamed == 8
    assert ("Ideas", "💡 Ideas · product owner shapes") in first.renamed_lanes
    assert all(old != "Done" for old, _ in first.renamed_lanes)
    assert set(trello.list_names()) == {
        *(display_name(name) for name in BOARD_LISTS),
        "Parking lot",
    }
    assert trello.names("c-plain") == ("Story", "📋 Delivery lead")
    trello.writes = ()
    again = await dress(trello, dry_run=False)
    assert again.lists_renamed == 0
    assert trello.writes == ()


async def test_dry_run_renames_no_lane():
    trello = FakeBoard(UNNAMED, {}, PARTLY_DRESSED_LISTS)
    planned = await dress(trello, dry_run=True)
    assert planned.lists_renamed == 8
    assert trello.writes == ()
    assert "Ideas" in trello.list_names()


ACTORS = {
    "l-dev": {"name": "🤖 Senior developer", "color": "purple_dark"},
    "l-tester": {"name": "🧪 Tester", "color": "lime_dark"},
}


def actor_board() -> FakeBoard:
    return FakeBoard(
        {**UNNAMED, **ACTORS},
        {
            "c-review": card("Review", "Share my agenda", labels=("l-dev",)),
            "c-done": card("Done", "Filter by track", labels=("l-tester",)),
            "c-testing": card("Testing", "Show the day", labels=("l-tester",)),
        },
    )


async def test_dress_fixes_stale_actor_labels():
    trello = actor_board()
    await dress(trello, dry_run=False)
    assert trello.names("c-review") == ("Story", "🔍 Code reviewer")
    assert trello.names("c-done") == ("Story", "Shipped")
    assert trello.names("c-testing") == ("🧪 Tester", "Story")
    assert ("remove_label", "c-review", "🤖 Senior developer") in trello.writes
    assert ("remove_label", "c-done", "🧪 Tester") in trello.writes
    assert not [call for call in trello.writes if call[:2] == ("remove_label", "c-testing")]
    trello.writes = ()
    again = await dress(trello, dry_run=False)
    assert again.cards_dressed == 0 and trello.writes == ()


WITHOUT_AGENT_OPS = tuple(
    {"id": f"list-{n}", "name": display_name(name)}
    for n, name in enumerate(BOARD_LISTS)
    if name != "Agent ops"
)


def watch_logs(trello: FakeBoard) -> list[dict]:
    return [c for c in trello.cards.values() if c["title"] == WATCH_LOG]


async def test_dress_creates_the_agent_ops_lane_and_its_watch_log_once():
    trello = FakeBoard(UNNAMED, {}, WITHOUT_AGENT_OPS)
    first = await dress(trello, dry_run=False)
    assert first.created_lanes == ("🛰 Agent ops · watching the agents",)
    assert first.created_cards == (WATCH_LOG,)
    assert trello.list_names()[-1] == "🛰 Agent ops · watching the agents"
    assert ("create_list", "🛰 Agent ops · watching the agents", "bottom") in trello.writes
    assert ("create", "Agent ops", WATCH_LOG, WATCH_LOG_DESCRIPTION) in trello.writes
    [log] = watch_logs(trello)
    assert log["list"] == "Agent ops" and log["cover"] == "black"
    assert log["description"] == WATCH_LOG_DESCRIPTION
    assert tuple(trello.labels[i]["name"] for i in log["labels"]) == ("🛰 Agent ops",)
    trello.writes = ()
    again = await dress(trello, dry_run=False)
    assert (again.created_lanes, again.created_cards, again.cards_dressed) == ((), (), 0)
    assert trello.writes == ()
    assert len(watch_logs(trello)) == 1


async def test_dry_run_reports_the_lane_and_card_it_would_create():
    trello = FakeBoard(UNNAMED, {}, WITHOUT_AGENT_OPS)
    planned = await dress(trello, dry_run=True)
    assert trello.writes == ()
    lines = report_lines(planned, dry_run=True)
    assert "create lane 🛰 Agent ops · watching the agents" in lines
    assert f"create card {WATCH_LOG}" in lines
    assert lines.index("create lane 🛰 Agent ops · watching the agents") == 0
    assert planned == await dress(FakeBoard(UNNAMED, {}, WITHOUT_AGENT_OPS), dry_run=False)


async def test_dress_keeps_an_existing_watch_log_and_dresses_it():
    trello = FakeBoard(UNNAMED, {"c-log": card("Agent ops", WATCH_LOG, labels=("l-blue",))})
    report = await dress(trello, dry_run=False)
    assert report.created_cards == ()
    assert len(watch_logs(trello)) == 1
    assert trello.cards["c-log"]["cover"] == "black"
    assert trello.names("c-log") == ("Story", "🛰 Agent ops")


async def test_dress_leaves_the_agent_ops_label_on_a_card_it_diagnosed():
    labels = {**UNNAMED, "l-ops": {"name": "🛰 Agent ops", "color": "blue_light"}}
    blocked = card(
        "Blocked", "Share my agenda", labels=("l-ops",), cover="red", stickers=("warning",)
    )
    trello = FakeBoard(labels, {"c-blocked": blocked})
    await dress(trello, dry_run=False)
    assert trello.names("c-blocked") == ("🛰 Agent ops", "Story", "🙋 Needs a human")
    assert not [call for call in trello.writes if call[0] == "remove_label"]
