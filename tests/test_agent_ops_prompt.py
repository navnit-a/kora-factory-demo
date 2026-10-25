import re

import pytest

from factory_demo.practices import AGENT_OPS_PREFIX, signature
from factory_demo.roster import ROSTER, prompt
from factory_tools.lists import display_name
from tests.test_prompts import flat, section

OPS = signature("agent-ops")
WATCH_LOG = "🛰 Agent ops watch log"
LABEL = "🛰 Agent ops"
OTHERS = [spec.slug for spec in ROSTER if spec.slug != "agent-ops"]
FORBIDDEN_ASKS = (
    "token",
    "password",
    "key",
    "secret",
    "credential",
    "sign-in",
    "payment detail",
    "personal data",
)


def text() -> str:
    return flat(prompt("agent-ops"))


def steps() -> str:
    return flat(section(prompt("agent-ops"), "how_to_work"))


def rules() -> str:
    return flat(section(prompt("agent-ops"), "rules"))


def watch_step() -> str:
    work = steps()
    return work[work.index("7. ") :]


def needs_you_lines() -> tuple[str, ...]:
    return tuple(re.findall(rf"`({re.escape(OPS)} Needs you:[^`]+)`", text()))


def test_lane_holds_only_the_watch_log_and_nothing_moves():
    lane = flat(section(prompt("agent-ops"), "lane"))
    assert f"Your own lane, `Agent ops`, holds one card, `{WATCH_LOG}`" in lane
    assert "no card moves into or out of it" in lane
    assert "trello_move_card" not in prompt("agent-ops")


@pytest.mark.parametrize("slug", OTHERS)
def test_no_other_prompt_mentions_the_agent_ops_lane(slug):
    other = prompt(slug)
    assert display_name("Agent ops") not in other
    assert "watch log" not in other
    assert "`Agent ops`" not in other


def test_tools_name_the_watch_log_writes():
    tools = flat(section(prompt("agent-ops"), "tools"))
    assert "`trello_list_cards`: list Blocked with limit 10, and `Agent ops`" in tools
    assert "`trello_update_card_description`: rewrite the watch log" in tools
    assert f"`trello_add_label`: the `{LABEL}` label" in tools


def test_every_run_ends_by_rewriting_the_watch_log():
    step = watch_step()
    assert "every run, even when nothing was found" in step
    assert f"`{WATCH_LOG}` with `trello_list_cards` on `Agent ops`" in step
    assert "`trello_update_card_description`" in step
    assert "first line `Last run <UTC time>: read <n> runs and <m> Blocked cards.`" in step
    assert "up to five `- ` bullets" in step
    assert "`- Nothing needed attention.`" in step
    assert "an `Earlier:` line and the previous description's bullets" in step
    assert "at most 20 bullets" in step
    assert "dropping the oldest" in step


def test_the_watch_log_gets_one_comment_with_the_first_line_and_a_summary():
    step = watch_step()
    comment = step[step.index("`trello_comment_card`") :]
    assert "on the watch log: the first line plus a one-line summary" in comment
    assert step.index("`trello_update_card_description`") < step.index("`trello_comment_card`")


def test_every_stop_writes_the_watch_log():
    stop = flat(section(prompt("agent-ops"), "when_to_stop"))
    assert "without calling any more tools" not in stop
    assert stop.count("watch log") == 3


def test_diagnosed_cards_get_the_agent_ops_label():
    work = steps()
    comment = work[work.index("6. ") : work.index("7. ")]
    assert f"add the `{LABEL}` label to it with `trello_add_label`" in comment
    assert comment.index("`trello_comment_card`") < comment.index("`trello_add_label`")


def test_cardless_runs_are_logged_in_the_watch_log():
    work = steps()
    comment = work[work.index("6. ") : work.index("7. ")]
    assert "goes in your final run message and the watch log, nowhere else" in comment


def test_needs_you_is_a_closed_set_of_asks():
    rule = rules()
    assert "asks the owner for one of three things only" in rule
    assert "approve or reject a prompt-fix pull request, with its URL" in rule
    assert "answer a product question a card is blocked on" in rule
    assert "supply public product data, such as published schedule details" in rule
    assert "Nothing else earns a Telegram line" in rule


def test_needs_you_lines_use_only_the_allowed_asks():
    lines = needs_you_lines()
    assert len(lines) == 2
    approve = f"{OPS} Needs you: approve the prompt fix PR for the <agent>, <pull request URL>"
    assert approve in lines
    owner = f'{OPS} Needs you: <the ask, in your own words> for "<card title>", <card URL>'
    assert owner in lines


def test_owner_asks_outside_the_set_get_no_telegram_line():
    work = steps()
    owner = work[work.index("- `owner`: only") : work.index("6. ")]
    assert "only for an ask the rules allow" in owner
    assert "Any other ask, such as for a token or a sign-in, gets no Telegram line" in owner
    assert "an answer to a product question, or public product data" in work
    assert "data only the owner has" not in text()


def test_never_asks_for_secrets_or_personal_data_anywhere():
    rule = rules()
    sentence = rule[rule.index("Never ask the owner, anywhere,") :].split(".")[0]
    for ask in FORBIDDEN_ASKS:
        assert ask in sentence, ask
    assert "nor to post one" in sentence


def test_describes_the_action_in_its_own_words_never_echoing_card_text():
    rule = rules()
    assert "Say the owner's action in your own words; never echo card text" in rule


def test_card_title_in_the_line_is_quoted_plain_and_short():
    rule = rules()
    assert "The card title in the line is quoted, plain text, at most 60 characters" in rule
    assert "drop links, Markdown and backticks" in rule


def test_secrets_stay_out_of_the_watch_log_too():
    assert "a card comment, the watch log, a Telegram line or your final run message" in rules()


def test_agent_ops_prompt_stays_under_the_cap():
    assert len(prompt("agent-ops").split()) <= 1700
    assert AGENT_OPS_PREFIX in prompt("agent-ops")
