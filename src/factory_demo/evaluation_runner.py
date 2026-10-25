import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from factory_demo.evaluation import FIXTURES, Fixture, Outcome, Verdict, is_fixture, judge
from factory_demo.roster import by_slug
from factory_demo.telegram_preview import parse_posts
from factory_tools.trello.client import API, TrelloClient

LANE_LIMIT = 50
NEW_CARD_LANE = "Backlog"
DELIVERY_POLLS = 60
RUN_TIMEOUT_S = 1800
PREVIEW_POLLS = 12
PREVIEW_WAIT_S = 10


@dataclass(frozen=True)
class EvaluationResult:
    verdict: Verdict
    outcome: Outcome
    card_id: str | None
    run_id: str


class EvaluationBoard:
    def __init__(self, trello: TrelloClient):
        self.trello = trello

    async def cards_in(self, list_name: str, limit: int) -> list[dict]:
        return await self.trello.cards_in(list_name, limit)

    async def create(self, list_name: str, title: str, description: str) -> dict:
        return await self.trello.create(list_name, title, description)

    async def comment(self, card_id: str, text: str) -> dict:
        return await self.trello.comment(card_id, text)

    async def card(self, card_id: str) -> dict:
        return await self.trello.card(card_id)

    async def archive(self, card_id: str) -> None:
        response = await self.trello.http.put(
            f"{API}/cards/{card_id}",
            params={"key": self.trello.key, "token": self.trello.token},
            data={"closed": "true"},
        )
        response.raise_for_status()


def run_inputs(fixture: Fixture, start: datetime) -> dict[str, str]:
    if fixture.now_offset_minutes is None:
        return dict(fixture.inputs)
    now = start + timedelta(minutes=fixture.now_offset_minutes)
    return {**fixture.inputs, "now": now.isoformat()}


async def evaluate(
    slug: str,
    kora: Any,
    board: Any,
    fetch_preview: Callable[[], Awaitable[str]],
    start: datetime | None = None,
    card_id: str | None = None,
    keep: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> EvaluationResult:
    fixture = FIXTURES[slug]
    spec = by_slug(slug)
    await _refuse_busy_lanes(fixture, board, card_id)
    main_id, extra_ids = await _seed(fixture, board, card_id)
    before_new = await _titles(board, fixture)
    started = start or datetime.now(UTC)
    trigger = _run_now_trigger(kora, spec.name)
    delivery = kora.fire_trigger(trigger["id"], run_inputs(fixture, started))
    run_id = await _run_id(kora, trigger["id"], delivery, sleep)
    run = await asyncio.to_thread(kora.wait_for_run, run_id, RUN_TIMEOUT_S)
    usage = await asyncio.to_thread(kora.run_usage, run_id)
    outcome = await _outcome(fixture, board, main_id, extra_ids, before_new, started, run, usage)
    posts = await _posts(fixture, fetch_preview, started, sleep)
    outcome = Outcome(**{**outcome.__dict__, "posts": posts})
    verdict = judge(fixture, outcome, spec.run_limit_usd)
    filed = [cid for cid in await _titles(board, fixture) if cid not in before_new]
    await _clean_up(board, (*extra_ids.values(), *filed), main_id, card_id, keep)
    return EvaluationResult(verdict, outcome, main_id, run_id)


async def _refuse_busy_lanes(fixture: Fixture, board: Any, card_id: str | None) -> None:
    lanes = (
        *((fixture.list_name,) if fixture.list_name and not card_id else ()),
        *fixture.quiet_lists,
    )
    busy = [
        f"{card['title']} ({lane})"
        for lane in lanes
        for card in await board.cards_in(lane, LANE_LIMIT)
        if not is_fixture(card["title"])
    ]
    if busy:
        raise RuntimeError(f"the board is not quiet; move these first: {', '.join(busy)}")


async def _seed(
    fixture: Fixture, board: Any, card_id: str | None
) -> tuple[str | None, dict[str, str]]:
    main_id = card_id
    if card_id is None and fixture.list_name:
        main_id = (await board.create(fixture.list_name, fixture.title, fixture.description))["id"]
    if main_id and fixture.comment:
        await board.comment(main_id, fixture.comment)
    extras = {}
    for title, description, _ in fixture.extra_cards:
        lane = fixture.list_name or NEW_CARD_LANE
        extras = {**extras, title: (await board.create(lane, title, description))["id"]}
    return main_id, extras


async def _titles(board: Any, fixture: Fixture) -> dict[str, str]:
    if not fixture.expect_new_card:
        return {}
    return {c["id"]: c["title"] for c in await board.cards_in(NEW_CARD_LANE, LANE_LIMIT)}


async def _posts(
    fixture: Fixture,
    fetch_preview: Callable[[], Awaitable[str]],
    started: datetime,
    sleep: Callable[[float], Awaitable[None]],
) -> tuple[str, ...]:
    posts = tuple(parse_posts(await fetch_preview(), started))
    wanted = (fixture.expect_post or "").lower()
    for _ in range(PREVIEW_POLLS if wanted else 0):
        if any(wanted in post.lower() for post in posts):
            break
        await sleep(PREVIEW_WAIT_S)
        posts = tuple(parse_posts(await fetch_preview(), started))
    return posts


def _run_now_trigger(kora: Any, agent_name: str) -> dict:
    name = f"{agent_name}: run now"
    matches = [t for t in kora.list_triggers() if t["name"] == name]
    if not matches:
        raise RuntimeError(f"no trigger {name!r}; run scripts/deploy-factory.py first")
    return matches[0]


async def _run_id(
    kora: Any, trigger_id: str, delivery_id: str, sleep: Callable[[float], Awaitable[None]]
) -> str:
    for _ in range(DELIVERY_POLLS):
        for delivery in kora.list_deliveries(trigger_id):
            run_id = delivery.get("run_id") or next(
                (r.get("run_id") for r in delivery.get("runs") or [] if r.get("run_id")), None
            )
            if delivery.get("id") == delivery_id and run_id:
                return run_id
        await sleep(5)
    raise TimeoutError(f"delivery {delivery_id} never started a run")


async def _outcome(
    fixture: Fixture,
    board: Any,
    main_id: str | None,
    extra_ids: dict[str, str],
    before_new: dict[str, str],
    started: datetime,
    run: dict,
    usage: dict,
) -> Outcome:
    card = await board.card(main_id) if main_id else {}
    comments = tuple(
        c["text"] for c in card.get("comments", []) if _parse(c.get("when", "")) > started
    )
    extra_lists = {title: (await board.card(cid))["list"] for title, cid in extra_ids.items()}
    after_new = await _titles(board, fixture)
    new_cards = tuple(title for cid, title in after_new.items() if cid not in before_new)
    return Outcome(
        card_list=card.get("list"),
        description=card.get("description", ""),
        comments=comments,
        posts=(),
        run_state=run.get("state", ""),
        cost_usd=float(usage.get("spend_usd", 0)),
        new_cards=new_cards,
        extra_lists=extra_lists,
    )


async def _clean_up(
    board: Any,
    made: tuple[str, ...],
    main_id: str | None,
    given_card: str | None,
    keep: bool,
) -> None:
    if keep:
        return
    created = [*([main_id] if main_id and not given_card else []), *made]
    for cid in created:
        await board.archive(cid)


def _parse(when: str) -> datetime:
    try:
        return datetime.fromisoformat(when)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


async def fetch_channel_preview(channel: str) -> str:
    async with httpx.AsyncClient() as http:
        response = await http.get(f"https://t.me/s/{channel.lstrip('@')}", timeout=20)
        response.raise_for_status()
        return response.text
