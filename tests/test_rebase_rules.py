from factory_demo.practices import REBASE_NEEDED, REPO_PATH
from factory_demo.roster import prompt
from tests.test_prompts import flat, section, word_cap

CONFLICTING = (
    "`gh pr view <number> --repo navnit-a/platformcon-day-planner --json mergeable` shows "
    "`CONFLICTING`"
)
BEHIND = f"`gh api {REPO_PATH}/compare/main...card-<card id> --jq .behind_by`"


def steps(slug: str) -> str:
    return flat(section(prompt(slug), "how_to_work"))


def test_rebase_needed_is_the_agreed_prefix():
    assert REBASE_NEEDED == "Rebase needed:"


def test_tester_sends_conflicting_prs_back_for_a_rebase():
    text = prompt("tester")
    work = steps("tester")
    assert CONFLICTING in work
    assert BEHIND in work
    assert work.index(CONFLICTING) < work.index("3. Read CI")
    rebase = work[work.index("7. A failed criterion") :]
    assert "a branch needing `main` (step 2, or a merge refused for conflicts)" in rebase
    assert "move the card to In Progress with a reason starting" in rebase
    assert f"or `{REBASE_NEEDED}` naming the `main` commit it lacks" in rebase
    assert "tick nothing" in rebase
    assert "post nothing to Telegram" in rebase
    assert "Blocked is only for what a human must settle" in flat(section(text, "lane"))
    stuck = flat(section(text, "when_to_stop"))
    assert "merge conflict" not in stuck
    assert "A refused merge: move the card to Blocked" not in work
    assert len(text.split()) <= 1780


def test_reviewer_sends_conflicting_prs_back_for_a_rebase():
    work = steps("code-reviewer")
    assert CONFLICTING in work
    assert BEHIND in work
    check = work.index(CONFLICTING)
    assert work.index("3. ") < check < work.index("4. ")
    assert f"move the card to In Progress with a reason starting `{REBASE_NEEDED}`" in work
    assert "naming the `main` commit" in work
    assert "instead of a review" in work
    assert REBASE_NEEDED in flat(section(prompt("code-reviewer"), "lane"))


def test_developer_resumes_a_rebase_needed_card():
    text = prompt("senior-developer")
    work = steps("senior-developer")
    assert f"A latest comment starting `{REBASE_NEEDED}`" in work
    assert "merge the latest `main` into `card-<card id>`" in work
    assert "resolve the conflicts" in work
    assert "keep the tests green" in work
    assert "push, and move the card to Review again" in work
    assert "existing branch and pull request" in work
    assert "never start again from scratch" in work
    assert REBASE_NEEDED in flat(section(text, "lane"))
    assert len(text.split()) <= word_cap("senior-developer")


def test_scrum_master_does_not_block_paused_lanes():
    work = steps("scrum-master")
    paused = work[work.index("4. ") : work.index("5. ")]
    assert "the team was paused" in paused
    assert "comment starting `Operator:`" in paused
    assert "stand-up" in paused
    for owner in (
        "the code reviewer for Review",
        "the tester for Testing",
        "the senior developer for In Progress",
    ):
        assert owner in paused, owner
    assert "leave the card alone" in paused
    assert work.index("4. ") < work.index("move it to Blocked with a reason")


def test_scrum_master_never_moves_cards_for_a_rebase():
    text = prompt("scrum-master")
    work = steps("scrum-master")
    conflict = work[work.index("5. ") : work.index("6. ")]
    assert "behind `main`" in conflict
    assert "you cannot check that" in conflict
    assert "still move it to Blocked" in conflict
    assert "check the pull request's `mergeable`" in conflict
    assert f"send it back with `{REBASE_NEEDED}`" in conflict
    assert "never copy a commit id from a comment" in conflict
    assert "In Progress with a reason" not in work
    assert "Never move a card anywhere but Blocked;" in flat(section(text, "rules"))
    lane = flat(section(text, "lane"))
    assert "to Blocked and nothing else, ever" in lane
    assert REBASE_NEEDED not in lane
    assert "rebase" not in flat(section(text, "when_to_stop"))
    assert len(text.split()) <= 950
