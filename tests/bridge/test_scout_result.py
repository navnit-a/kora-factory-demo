import pytest

from factory_bridge.scout_result import ScoutResult, parse_scout

ANSWER = """I read the code and the lists.

<title>Show the next break</title>
<story>
As an attendee, I want to see when the next break starts, so that I can plan a coffee.
</story>
<criteria>
- Given the schedule has loaded, When I open the planner, Then I see the next break.
  It shows the start time.
- Given no break is left, When I open the planner, Then I see no break line.

</criteria>
<verdict> buildable </verdict>
<dependencies>none</dependencies>
<reason>The agenda already lists breaks.</reason>"""


def test_answer_with_prose_before_the_tags_parses():
    assert parse_scout(ANSWER) == ScoutResult(
        title="Show the next break",
        story=(
            "As an attendee, I want to see when the next break starts, so that I can plan a coffee."
        ),
        criteria=(
            "Given the schedule has loaded, When I open the planner, Then I see the next break. "
            "It shows the start time.",
            "Given no break is left, When I open the planner, Then I see no break line.",
        ),
        verdict="buildable",
        dependencies="none",
        reason="The agenda already lists breaks.",
    )


def test_criteria_are_split_into_lines():
    result = parse_scout(ANSWER)
    assert len(result.criteria) == 2
    assert all(line.startswith("Given") for line in result.criteria)


def test_first_of_a_repeated_tag_wins():
    assert parse_scout(ANSWER + "\n<title>Second title</title>").title == "Show the next break"


def test_malformed_scout_text_raises_naming_the_missing_tags():
    broken = ANSWER.replace("<title>", "<heading>").replace("<verdict>", "")
    with pytest.raises(ValueError, match="^scout answer missing: title, verdict$"):
        parse_scout(broken)


def test_empty_tag_counts_as_missing():
    with pytest.raises(ValueError, match="missing: reason"):
        parse_scout(ANSWER.replace("The agenda already lists breaks.", "  "))


def test_unknown_verdict_is_rejected():
    with pytest.raises(ValueError, match="maybe"):
        parse_scout(ANSWER.replace(" buildable ", "maybe"))


def test_criteria_without_dash_lines_are_rejected():
    criteria = ANSWER[ANSWER.index("<criteria>") : ANSWER.index("</criteria>")]
    with pytest.raises(ValueError, match="criteria"):
        parse_scout(ANSWER.replace(criteria, "<criteria>Given it works"))
