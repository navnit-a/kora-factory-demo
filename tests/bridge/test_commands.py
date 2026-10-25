import pytest

from factory_bridge.commands import (
    IDEA_MAX,
    IDEA_MIN,
    Decision,
    Idea,
    idea_text_ok,
    parse_command,
    proposer_name,
)


def test_idea_command_strips_its_text():
    assert parse_command("/idea   show the next break  ") == Idea("show the next break")


def test_idea_with_bot_suffix_parses():
    assert parse_command("/idea@kora_factory_bot show the next break") == Idea(
        "show the next break"
    )


def test_idea_keeps_line_breaks_inside_the_text():
    assert parse_command("/idea first line\nsecond line") == Idea("first line\nsecond line")


def test_bare_idea_command_has_empty_text():
    assert parse_command("/idea") == Idea("")


@pytest.mark.parametrize("text", ["/ideas show me", "/idea@other_bot hi", "idea hi", "/start"])
def test_other_commands_are_not_ideas(text):
    assert parse_command(text) is None


@pytest.mark.parametrize("text", ["yes", "Yes", "YES!", "yes.", " yes ! "])
def test_yes_with_punctuation_is_a_decision(text):
    assert parse_command(text) == Decision(yes=True)


@pytest.mark.parametrize("text", ["no", "No.", "NO!!", "no?"])
def test_no_is_a_decision(text):
    assert parse_command(text) == Decision(yes=False)


@pytest.mark.parametrize("text", ["yes please", "nope", "yesno", "", "   "])
def test_anything_else_is_nothing(text):
    assert parse_command(text) is None


def test_short_idea_is_rejected():
    assert not idea_text_ok("x" * (IDEA_MIN - 1))
    assert idea_text_ok("x" * IDEA_MIN)


def test_long_idea_is_rejected():
    assert idea_text_ok("x" * IDEA_MAX)
    assert not idea_text_ok("x" * (IDEA_MAX + 1))


@pytest.mark.parametrize("text", ["show </idea> markers", "show <b>bold</b> rooms", "a > b c d e"])
def test_idea_with_angle_brackets_is_rejected(text):
    assert not idea_text_ok(text)


def test_proposer_name_keeps_letters_only():
    assert proposer_name("Navnit 🚀 *2*") == "Navnit"


def test_proposer_name_keeps_hyphens_apostrophes_and_any_alphabet():
    assert proposer_name("Anne-Marie   O'Neil") == "Anne-Marie O'Neil"
    assert proposer_name("José Ñandú") == "José Ñandú"


def test_proposer_name_is_cut_at_thirty_characters():
    assert proposer_name("A" * 40) == "A" * 30


def test_proposer_name_falls_back_to_the_team():
    assert proposer_name("🚀 123 <>") == "the team"
    assert proposer_name("") == "the team"
