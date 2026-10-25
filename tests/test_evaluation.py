from factory_demo.evaluation import FIXTURES, Outcome, is_fixture, judge
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
    )
    return Outcome(**{**base.__dict__, **changes})


def test_fixtures_cover_every_agent():
    assert set(FIXTURES) == {spec.slug for spec in ROSTER}


def test_every_fixture_card_is_marked():
    for fixture in FIXTURES.values():
        if fixture.title:
            assert is_fixture(fixture.title), fixture.slug
        for title, _, _ in fixture.extra_cards:
            assert is_fixture(title), fixture.slug


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
        posts=("Bug raised: footer year (normal)",),
        new_cards=("Bug: footer says 2025",),
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
