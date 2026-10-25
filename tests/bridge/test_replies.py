import pytest

from factory_bridge import replies
from factory_bridge.scout_result import ScoutResult
from factory_demo.practices import VERDICTS

TELEGRAM_MAX = 4096


def _result(verdict: str = "buildable", story: str = "As an attendee I want it.") -> ScoutResult:
    return ScoutResult(
        "Show the next break",
        story,
        ("Given a, When b, Then c", "Given d, When e, Then f"),
        verdict,
        "a backend to store shares" if verdict == "needs_dependency" else "none",
        "The agenda lists breaks.",
    )


def test_proposal_lays_out_the_write_up():
    text = replies.proposal(_result())
    assert text.startswith("Show the next break\n\nAs an attendee I want it.\n\nAcceptance:\n")
    assert "- Given a, When b, Then c\n- Given d, When e, Then f" in text
    assert "Verdict: " in text and "The agenda lists breaks." in text
    assert text.endswith("Reply yes to add it to Ideas, or no to drop it.")


def test_needs_dependency_names_it_and_offers_yes():
    text = replies.proposal(_result("needs_dependency"))
    assert "a backend to store shares" in text
    assert text.endswith("Reply yes to add it to Ideas, or no to drop it.")


def test_not_buildable_offers_no_yes():
    text = replies.proposal(_result("not_buildable"))
    assert "Reply yes" not in text
    assert text.endswith("Reply no to drop it, or send /idea again with a change.")


def test_each_verdict_reads_differently():
    sentences = {replies.proposal(_result(v)).split("Verdict: ")[1] for v in VERDICTS}
    assert len(sentences) == 3


def test_a_long_proposal_still_fits_and_keeps_its_question():
    text = replies.proposal(_result(story="word " * 2000))
    assert len(text) <= TELEGRAM_MAX
    assert text.endswith("Reply yes to add it to Ideas, or no to drop it.")


def test_refused_gives_the_id_to_pass_on():
    assert replies.refused(4242) == (
        "Sorry, I only take ideas from the team. Your Telegram id is 4242; ask Navnit to add it."
    )


def test_bad_text_names_the_limits():
    text = replies.bad_text()
    assert "10 to 500" in text
    assert "<" in text and ">" in text


def test_rate_limited_says_when():
    assert "14:05" in replies.rate_limited("14:05")


def test_added_links_the_card():
    assert "https://trello.com/c/abc" in replies.added("https://trello.com/c/abc")


def test_card_failed_keeps_the_proposal_and_asks_for_yes_again():
    text = replies.card_failed()
    assert "kept" in text and "yes" in text


@pytest.mark.parametrize(
    "text",
    [
        replies.ack(),
        replies.added("https://trello.com/c/abc"),
        replies.dropped(),
        replies.nothing_pending(),
        replies.refused(1),
        replies.rate_limited("09:00"),
        replies.bad_text(),
        replies.scout_failed(),
        replies.not_buildable_yes(),
        replies.card_failed(),
    ],
)
def test_every_reply_is_plain_and_fits_one_message(text):
    assert 0 < len(text) < TELEGRAM_MAX
    assert "*" not in text and "_" not in text and "`" not in text
