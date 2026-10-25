from datetime import UTC, datetime, timedelta

import pytest

from factory_demo.evaluation import FIXTURES
from factory_demo.evaluation_runner import evaluate, run_inputs
from tests.fake_kora import FakeKora

START = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


class FakeTrello:
    def __init__(self, cards: dict[str, dict] | None = None):
        self.cards = dict(cards or {})
        self.archived: tuple[str, ...] = ()
        self.on_run = None

    async def cards_in(self, list_name, limit):
        return [
            {"id": cid, "title": c["title"], "list": c["list"]}
            for cid, c in self.cards.items()
            if c["list"] == list_name
        ][:limit]

    async def create(self, list_name, title, description):
        card_id = f"{len(self.cards):024x}"
        self.cards = {
            **self.cards,
            card_id: {
                "title": title,
                "list": list_name,
                "description": description,
                "comments": (),
            },
        }
        return {"id": card_id, "url": f"https://trello.com/c/{card_id}", "list": list_name}

    async def comment(self, card_id, text):
        return self._comment(card_id, text, "2026-10-25T08:59:00Z")

    def _comment(self, card_id, text, when):
        card = self.cards[card_id]
        self.cards = {
            **self.cards,
            card_id: {**card, "comments": ({"when": when, "text": text}, *card["comments"])},
        }
        return {"id": card_id}

    async def card(self, card_id):
        card = self.cards[card_id]
        return {
            "id": card_id,
            "title": card["title"],
            "list": card["list"],
            "url": "",
            "description": card["description"],
            "comments": list(card["comments"]),
            "labels": list(card.get("labels", ())),
            "checklist": [
                {"text": text, "state": state} for text, state in card.get("checklist", ())
            ],
        }

    async def card_look(self, card_id):
        card = self.cards[card_id]
        labels = tuple({"name": name, "color": None} for name in card.get("labels", ()))
        return {"cover": card.get("cover"), "description": card["description"], "labels": labels}

    async def archive(self, card_id):
        self.archived = (*self.archived, card_id)


class RunningKora(FakeKora):
    def __init__(self, trello: FakeTrello, act):
        super().__init__()
        self.trello = trello
        self.act = act
        self.fired: tuple[tuple[str, dict], ...] = ()
        self.events: tuple[dict, ...] = ()
        self.events_read: tuple[str, ...] = ()
        self.triggers = (
            {"id": "t-po", "name": "Product owner: run now", "kind": "manual"},
            {"id": "t-sm", "name": "Scrum master: run now", "kind": "manual"},
        )

    def fire_trigger(self, trigger_id, variables):
        self.fired = (*self.fired, (trigger_id, variables))
        self.act(self.trello)
        return "d-1"

    def list_deliveries(self, trigger_id, limit=10):
        return [{"id": "d-1", "run_id": "r-1"}]

    def wait_for_run(self, run_id, timeout_s=600, poll_s=5.0):
        return {"id": run_id, "state": "idle"}

    def run_usage(self, run_id):
        return {"spend_usd": 0.04}

    def run_events(self, run_id, limit=400):
        self.events_read = (*self.events_read, run_id)
        return list(self.events)


CRITERIA = (("Shows", "incomplete"), ("Counts", "incomplete"), ("Reads", "incomplete"))


def write_story(trello: FakeTrello, checklist: tuple[tuple[str, str], ...]) -> None:
    card_id = next(cid for cid, c in trello.cards.items() if c["list"] == "Ideas")
    card = trello.cards[card_id]
    story = {
        "list": "Backlog",
        "description": "Given x When y Then z",
        "labels": ("Story", "📋 Delivery lead"),
        "checklist": checklist,
    }
    trello.cards = {**trello.cards, card_id: {**card, **story}}
    trello._comment(card_id, "Story ready.", "2026-10-25T09:01:00Z")


def product_owner_works(trello: FakeTrello) -> None:
    write_story(trello, CRITERIA)


async def no_posts() -> str:
    return "<html></html>"


async def test_evaluate_passes_a_working_product_owner():
    trello = FakeTrello()
    kora = RunningKora(trello, product_owner_works)
    result = await evaluate("product-owner", kora, trello, no_posts, start=START)
    assert result.verdict.passed, result.verdict.reasons
    assert result.outcome.cost_usd == 0.04
    assert kora.fired == (("t-po", {}),)
    assert len(trello.archived) == 1
    assert kora.events_read == ()


async def test_runner_reads_labels_cover_and_checklist():
    trello = FakeTrello()
    kora = RunningKora(trello, lambda board: write_story(board, CRITERIA[:2]))
    result = await evaluate("product-owner", kora, trello, no_posts, start=START)
    assert result.outcome.labels == ("Story", "📋 Delivery lead")
    assert result.outcome.cover is None
    assert result.outcome.checklist == CRITERIA[:2]
    assert result.verdict.reasons == ("checklist has 2 items, expected at least 3",)


def ship_as_tester(trello: FakeTrello) -> None:
    card = trello.cards["c" * 24]
    done = {
        "list": "Done",
        "cover": "green",
        "labels": ("Story", "Shipped"),
        "checklist": tuple((text, "complete") for text, _ in CRITERIA),
    }
    trello.cards = {**trello.cards, "c" * 24: {**card, **done}}
    trello._comment("c" * 24, "Shipped: PR 7", "2026-10-25T09:01:00Z")


async def test_runner_judges_the_shipped_look_of_a_given_card():
    testing = {"title": "[fixture] Count", "list": "Testing", "description": "", "comments": ()}
    trello = FakeTrello({"c" * 24: {**testing, "labels": ("Story",), "checklist": CRITERIA}})
    kora = RunningKora(trello, ship_as_tester)
    kora.triggers = ({"id": "t-te", "name": "Tester: run now", "kind": "manual"},)

    async def shipped_post() -> str:
        return (
            '<div data-post="c/2"><div class="tgme_widget_message_text">Shipped: Count'
            '</div><time datetime="2026-10-25T09:03:00+00:00"></time></div>'
        )

    result = await evaluate("tester", kora, trello, shipped_post, start=START, card_id="c" * 24)
    assert result.verdict.passed, result.verdict.reasons
    assert result.outcome.cover == "green"
    assert trello.archived == ()


async def test_evaluate_keeps_the_card_when_asked():
    trello = FakeTrello()
    kora = RunningKora(trello, product_owner_works)
    result = await evaluate("product-owner", kora, trello, no_posts, start=START, keep=True)
    assert trello.archived == ()
    assert result.card_id


async def test_evaluate_refuses_a_busy_lane():
    trello = FakeTrello(
        {"a" * 24: {"title": "Real idea", "list": "Ideas", "description": "", "comments": ()}}
    )
    kora = RunningKora(trello, product_owner_works)
    with pytest.raises(RuntimeError, match="Real idea"):
        await evaluate("product-owner", kora, trello, no_posts, start=START)
    assert kora.fired == ()


def test_scrum_master_gets_a_clock_two_hours_on():
    inputs = run_inputs(FIXTURES["scrum-master"], START)
    assert inputs == {"now": (START + timedelta(minutes=120)).isoformat()}
    assert run_inputs(FIXTURES["lunch"], START)["place"] == "Sydney Masonic Centre"


def support_files_a_bug(trello: FakeTrello) -> None:
    source = next(cid for cid, c in trello.cards.items() if c["list"] == "Done")
    trello.cards = {
        **trello.cards,
        "b" * 24: {
            "title": "Bug: session dialog cannot be closed with the keyboard",
            "list": "Backlog",
            "description": "",
            "comments": (),
            "labels": ("Bug", "High severity"),
        },
    }
    trello._comment(source, "Filed as https://trello.com/c/bbbb", "2026-10-25T09:02:00Z")


async def test_evaluate_archives_the_bug_the_support_agent_filed():
    trello = FakeTrello()
    kora = RunningKora(trello, support_files_a_bug)
    kora.triggers = ({"id": "t-su", "name": "Support: run now", "kind": "manual"},)

    async def bug_post() -> str:
        return (
            '<div data-post="c/1"><div class="tgme_widget_message_text">'
            "Bug raised: session dialog traps the keyboard (high)"
            '</div><time datetime="2026-10-25T09:03:00+00:00"></time></div>'
        )

    result = await evaluate("support", kora, trello, bug_post, start=START)
    assert result.verdict.passed, result.verdict.reasons
    assert result.outcome.labels == ("Bug", "High severity")
    assert "b" * 24 in trello.archived


def scrum_master_blocks(trello: FakeTrello) -> None:
    card_id = next(cid for cid, c in trello.cards.items() if c["list"] == "In Progress")
    blocked = {"list": "Blocked", "labels": ("🙋 Needs a human",)}
    trello.cards = {**trello.cards, card_id: {**trello.cards[card_id], **blocked}}
    trello._comment(card_id, "Idle 120 min.", "2026-10-25T09:01:00Z")


async def test_evaluate_waits_for_the_channel_preview_to_catch_up():
    trello = FakeTrello()
    kora = RunningKora(trello, scrum_master_blocks)
    pages = iter(
        [
            "<html></html>",
            '<div data-post="c/7"><div class="tgme_widget_message_text">Blocked: x</div>'
            '<time datetime="2026-10-25T09:02:00+00:00"></time></div>',
        ]
    )

    async def preview() -> str:
        return next(pages)

    async def no_wait(_: float) -> None:
        return None

    result = await evaluate("scrum-master", kora, trello, preview, start=START, sleep=no_wait)
    assert result.verdict.passed, result.verdict.reasons


SCOUT_ANSWER = (
    "<title>Rate each talk</title><story>As an attendee</story><criteria>Given</criteria>"
    "<dependencies>a ratings store</dependencies>"
    "<verdict>needs_dependency</verdict><reason>needs somewhere to keep votes</reason>"
)


def answered(text: str, interrupted: bool = False) -> dict:
    return {
        "event_type": "message_complete",
        "payload": {"text": text, "interrupted": interrupted},
    }


def scout_kora(trello: FakeTrello, events: tuple[dict, ...]) -> RunningKora:
    kora = RunningKora(trello, lambda _: None)
    kora.triggers = (
        {"id": "t-run", "name": "Idea scout: run now", "kind": "manual"},
        {"id": "t-scout", "name": "Idea scout: scout", "kind": "manual"},
    )
    kora.events = events
    return kora


async def test_runner_fires_the_named_manual_trigger():
    trello = FakeTrello()
    kora = scout_kora(trello, (answered(SCOUT_ANSWER),))
    result = await evaluate("idea-scout", kora, trello, no_posts, start=START)
    assert kora.fired == (
        (
            "t-scout",
            {
                "idea": "Let attendees rate each talk out of five stars and show everyone "
                "the average",
                "from": "Navnit",
            },
        ),
    )
    assert result.verdict.passed, result.verdict.reasons
    assert trello.cards == {}


async def test_runner_reads_final_text_from_events():
    trello = FakeTrello()
    kora = scout_kora(trello, (answered("thinking"), answered(SCOUT_ANSWER), answered("x", True)))
    result = await evaluate("idea-scout", kora, trello, no_posts, start=START)
    assert result.outcome.final_text == SCOUT_ANSWER
    assert kora.events_read == ("r-1",)


async def test_runner_names_a_run_without_final_text():
    trello = FakeTrello()
    kora = scout_kora(trello, ())
    result = await evaluate("idea-scout", kora, trello, no_posts, start=START)
    assert not result.verdict.passed
    assert "no final assistant text" in result.verdict.reasons


TRAINS_PR = "https://github.com/navnit-a/platformcon-day-planner/pull/12"


async def trains_post() -> str:
    return (
        '<div data-post="c/9"><div class="tgme_widget_message_text">'
        "🚆 Sydney trains: ... Transport for NSW"
        '</div><time datetime="2026-10-25T09:03:00+00:00"></time></div>'
    )


async def test_runner_lists_pull_requests_for_the_expected_head():
    trello = FakeTrello()
    kora = RunningKora(trello, lambda _: None)
    kora.triggers = ({"id": "t-tr", "name": "Sydney trains: run now", "kind": "manual"},)
    seen: list[str] = []

    def list_prs(head: str) -> list[str]:
        seen.append(head)
        return [TRAINS_PR]

    result = await evaluate(
        "sydney-trains", kora, trello, trains_post, start=START, list_prs=list_prs
    )
    assert seen == ["agent-trains"]
    assert result.outcome.pr_urls == (TRAINS_PR,)
    assert result.verdict.passed, result.verdict.reasons


async def test_runner_fails_a_data_agent_without_a_pull_request():
    trello = FakeTrello()
    kora = RunningKora(trello, lambda _: None)
    kora.triggers = ({"id": "t-tr", "name": "Sydney trains: run now", "kind": "manual"},)
    result = await evaluate(
        "sydney-trains", kora, trello, trains_post, start=START, list_prs=lambda _: []
    )
    assert result.verdict.reasons == ("no open pull request on agent-trains",)


async def test_runner_skips_pull_requests_for_a_card_agent():
    trello = FakeTrello()
    kora = RunningKora(trello, product_owner_works)
    seen: list[str] = []

    def list_prs(head: str) -> list[str]:
        seen.append(head)
        return []

    result = await evaluate("product-owner", kora, trello, no_posts, start=START, list_prs=list_prs)
    assert seen == []
    assert result.outcome.pr_urls == ()
