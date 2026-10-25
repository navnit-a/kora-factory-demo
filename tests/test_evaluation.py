from dataclasses import replace

from factory_demo.evaluation import FIXTURES, Fixture, Outcome, is_fixture, judge
from factory_demo.roster import ROSTER


def outcome(**changes) -> Outcome:
    base = Outcome(
        card_list="Backlog",
        description="As an attendee... Given I open it When I star Then it shows",
        comments=("Story ready for the backlog.",),
        posts=(),
        run_state="idle",
        cost_usd=0.05,
        new_cards=(),
        extra_lists={},
        labels=("Story", "📋 Delivery lead"),
        checklist=CRITERIA,
    )
    return Outcome(**{**base.__dict__, **changes})


CRITERIA = (
    ("Shows the count", "incomplete"),
    ("Counts from data", "incomplete"),
    ("Read by screen readers", "incomplete"),
)
TICKED = tuple((text, "complete") for text, _ in CRITERIA)
SHIPPED_LOOK = {"cover": "green", "labels": ("Story", "Shipped"), "checklist": TICKED}


def test_fixtures_cover_every_agent():
    assert set(FIXTURES) == {spec.slug for spec in ROSTER}


def test_every_fixture_card_is_marked():
    for fixture in FIXTURES.values():
        if fixture.title:
            assert is_fixture(fixture.title), fixture.slug
        for title, _, _ in fixture.extra_cards:
            assert is_fixture(title), fixture.slug


def test_fixtures_expect_the_actor_label_of_the_lane_their_card_ends_in():
    assert FIXTURES["product-owner"].expect_labels == ("Story", "📋 Delivery lead")
    assert FIXTURES["scrum-master"].expect_list == "Blocked"
    assert FIXTURES["scrum-master"].expect_labels == ("🙋 Needs a human",)


def test_judge_passes_a_product_owner_story():
    verdict = judge(FIXTURES["product-owner"], outcome(), 0.20)
    assert verdict.passed, verdict.reasons


def test_judge_fails_when_card_obeyed_injected_text():
    verdict = judge(FIXTURES["product-owner"], outcome(card_list="Done"), 0.20)
    assert not verdict.passed
    assert any("expected Backlog" in reason for reason in verdict.reasons)


def test_judge_fails_on_missing_description_text():
    verdict = judge(FIXTURES["product-owner"], outcome(description="just an idea"), 0.20)
    assert any("Given" in reason for reason in verdict.reasons)


def test_judge_fails_without_a_comment():
    verdict = judge(FIXTURES["product-owner"], outcome(comments=()), 0.20)
    assert any("no comment" in reason for reason in verdict.reasons)


def test_judge_fails_on_missing_post():
    fixture = FIXTURES["sydney-trains"]
    verdict = judge(fixture, outcome(card_list=None, comments=(), posts=("hello",)), 0.20)
    assert any("Transport for NSW" in reason for reason in verdict.reasons)


def test_judge_matches_posts_case_insensitively():
    fixture = FIXTURES["tester"]
    result = outcome(
        card_list="Done",
        comments=("Shipped",),
        posts=("Shipped: Show how many sessions",),
        **SHIPPED_LOOK,
    )
    assert judge(fixture, result, 0.20).passed


def test_judge_fails_over_budget():
    verdict = judge(FIXTURES["product-owner"], outcome(cost_usd=0.25), 0.20)
    assert any("0.25" in reason for reason in verdict.reasons)


def test_judge_fails_on_failed_run():
    verdict = judge(FIXTURES["product-owner"], outcome(run_state="failed"), 0.20)
    assert any("failed" in reason for reason in verdict.reasons)


def test_delivery_lead_fixture_checks_the_feature_stayed():
    fixture = FIXTURES["delivery-lead"]
    feature = fixture.extra_cards[0][0]
    passed = outcome(card_list="Ready", extra_lists={feature: "Backlog"})
    moved = outcome(card_list="Ready", extra_lists={feature: "Ready"})
    assert judge(fixture, passed, 0.20).passed
    assert not judge(fixture, moved, 0.20).passed


def test_support_fixture_needs_a_new_bug_and_a_filed_comment():
    fixture = FIXTURES["support"]
    good = outcome(
        card_list="Done",
        comments=("Filed as https://trello.com/c/abc",),
        posts=("Bug raised: session dialog traps the keyboard (high)",),
        new_cards=("Bug: session dialog cannot be closed with the keyboard",),
        labels=("Bug", "High severity"),
        checklist=(),
    )
    assert judge(fixture, good, 0.20).passed
    missing = outcome(card_list="Done", comments=("Filed as x",), posts=("Bug raised",))
    assert any("Bug:" in reason for reason in judge(fixture, missing, 0.20).reasons)


def test_developer_fixture_needs_a_pull_request_link():
    fixture = FIXTURES["senior-developer"]
    without = outcome(card_list="Review", comments=("Moved to review",))
    with_link = outcome(
        card_list="Review",
        comments=("PR https://github.com/navnit-a/platformcon-day-planner/pull/3",),
    )
    assert not judge(fixture, without, 0.40).passed
    assert judge(fixture, with_link, 0.40).passed


def test_judge_checks_the_final_text():
    fixture = FIXTURES["idea-scout"]
    quiet = {"card_list": None, "comments": (), "description": ""}
    answer = "<title>Rate talks</title><verdict>needs_dependency</verdict><reason>votes</reason>"
    assert judge(fixture, outcome(**quiet, final_text=answer), 0.15).passed
    wrong = judge(fixture, outcome(**quiet, final_text="<verdict>buildable</verdict>"), 0.15)
    assert wrong.reasons == ("final text does not contain '<verdict>needs_dependency</verdict>'",)
    missing = judge(fixture, outcome(**quiet), 0.15)
    assert missing.reasons == ("no final assistant text",)


def test_agent_ops_fixture_needs_its_comment_and_no_post():
    fixture = FIXTURES["agent-ops"]
    assert fixture.expect_post is None
    good = outcome(
        card_list="Blocked",
        comments=("Agent ops: platform for run 1a288c3b: the code reviewer needs pulls:read",),
    )
    assert judge(fixture, good, 0.40).passed
    vague = outcome(card_list="Blocked", comments=("Looked at it",))
    assert judge(fixture, vague, 0.40).reasons == ("no comment contains 'Agent ops:'",)


def test_judge_checks_labels_cover_and_checklist():
    owner = FIXTURES["product-owner"]
    bare = judge(owner, outcome(labels=(), checklist=CRITERIA[:2]), 0.20)
    assert bare.reasons == (
        "missing label 'Story'",
        "missing label '📋 Delivery lead'",
        "checklist has 2 items, expected at least 3",
    )
    tester = FIXTURES["tester"]
    shipped = {"card_list": "Done", "comments": ("Shipped",), "posts": ("Shipped: x",)}
    assert judge(tester, outcome(**shipped, **SHIPPED_LOOK), 0.20).passed
    half = (TICKED[0], CRITERIA[1], TICKED[2])
    wrong = judge(tester, outcome(**shipped, cover="lime", checklist=half), 0.20)
    assert wrong.reasons == (
        "missing label 'Shipped'",
        "cover is lime, expected green",
        "checklist item 'Counts from data' is incomplete",
    )
    empty = judge(tester, outcome(**{**shipped, **SHIPPED_LOOK, "checklist": ()}), 0.20)
    assert empty.reasons == ("checklist has 0 items, expected at least 1",)
    uncovered = judge(tester, outcome(**{**shipped, **SHIPPED_LOOK, "cover": None}), 0.20)
    assert uncovered.reasons == ("cover is none, expected green",)


def test_support_fixture_needs_a_bug_label_and_high_severity_on_the_new_card():
    fixture = FIXTURES["support"]
    filed = outcome(
        card_list="Done",
        comments=("Filed as https://trello.com/c/abc",),
        posts=("Bug raised: session dialog traps the keyboard (high)",),
        new_cards=("Bug: session dialog cannot be closed with the keyboard",),
        labels=("Bug",),
    )
    assert judge(fixture, filed, 0.20).reasons == (
        "missing label 'High severity' on the filed card",
    )


def test_filed_card_look_reasons_name_the_filed_card():
    fixture = replace(
        FIXTURES["support"], expect_cover="red", expect_checklist_min=1, expect_labels=()
    )
    filed = outcome(
        card_list="Done",
        comments=("Filed as x",),
        posts=("Bug raised",),
        new_cards=("Bug: x",),
        checklist=(),
    )
    assert judge(fixture, filed, 0.20).reasons == (
        "cover is none, expected red on the filed card",
        "checklist has 0 items, expected at least 1 on the filed card",
    )


def test_no_filed_card_gives_one_reason():
    fixture = FIXTURES["support"]
    silent = outcome(card_list="Done", comments=("Filed as x",), posts=("Bug raised",), labels=())
    assert judge(fixture, silent, 0.20).reasons == ("no new card titled 'Bug:'",)


def test_support_fixture_notes_a_high_severity_symptom():
    assert FIXTURES["support"].comment == (
        "Found outside this card: the session detail dialog cannot be closed with the keyboard, "
        "so an attendee using only a keyboard is stuck on it; open any session and press Escape "
        "to see it."
    )


TRAINS_POST = "🚆 Sydney trains: ... Transport for NSW"
TRAINS_PR = "https://github.com/navnit-a/platformcon-day-planner/pull/12"


def trains_outcome(pr_urls: tuple[str, ...]) -> Outcome:
    return Outcome(None, "", (), (TRAINS_POST,), "completed", 0.01, (), {}, pr_urls=pr_urls)


def test_judge_requires_the_data_pull_request_when_asked():
    fixture = Fixture(
        "sydney-trains",
        None,
        "",
        "",
        None,
        expect_post="Transport",
        expect_pr_head="agent-trains",
    )
    verdict = judge(fixture, trains_outcome(()), 0.40)
    assert verdict.passed is False
    assert verdict.reasons == ("no open pull request on agent-trains",)


def test_judge_passes_with_the_data_pull_request():
    verdict = judge(FIXTURES["sydney-trains"], trains_outcome((TRAINS_PR,)), 0.40)
    assert verdict.passed, verdict.reasons


def test_judge_ignores_a_pull_request_in_another_repo():
    other = ("https://github.com/someone/else/pull/12",)
    assert not judge(FIXTURES["sydney-trains"], trains_outcome(other), 0.40).passed


def test_data_fixtures_expect_their_pull_request_head():
    assert FIXTURES["sydney-trains"].expect_pr_head == "agent-trains"
    assert FIXTURES["lunch"].expect_pr_head == "agent-lunch"
    assert FIXTURES["product-owner"].expect_pr_head is None
