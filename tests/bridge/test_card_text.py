from factory_bridge.card_text import card_description, card_title
from factory_bridge.scout_result import ScoutResult

RESULT = ScoutResult(
    "Show the next break",
    "As an attendee I want to see the next break.",
    ("Given a, When b, Then c", "Given d, When e, Then f"),
    "needs_dependency",
    "a backend",
    "Breaks need live times.",
)


def test_card_title_is_the_scout_title():
    assert card_title(RESULT) == "Show the next break"


def test_card_description_lays_out_the_story():
    assert card_description(RESULT, "Navnit") == (
        "As an attendee I want to see the next break.\n\n"
        "Acceptance criteria:\n"
        "- Given a, When b, Then c\n"
        "- Given d, When e, Then f\n\n"
        "Verdict: needs_dependency. Breaks need live times.\n"
        "Dependencies: a backend\n\n"
        "Proposed by Navnit via Telegram"
    )


def test_card_description_credits_the_proposer():
    assert card_description(RESULT, "Justin").endswith("Proposed by Justin via Telegram")
    assert card_description(RESULT, "🚀").endswith("Proposed by the team via Telegram")
