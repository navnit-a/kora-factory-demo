from dataclasses import dataclass
from typing import Any

from factory_tools.lists import BOARD_LISTS
from factory_tools.trello.look import (
    DEPENDS_ON,
    DONE,
    FIXTURE_TAG,
    LABELS,
    LANE_LOOK,
    LANE_STICKERS,
    SHIPPED,
    UNBLOCKED,
    type_label,
)

LANE_LIMIT = 100
READY = "Ready"
READY_COLOUR = "yellow"
FIXTURE = "Fixture"
COLOUR_NAMES = dict(blue="Story", green=SHIPPED, orange=DEPENDS_ON, purple="Spike", red="Bug")
RENAMES = {**COLOUR_NAMES, READY_COLOUR: READY}
TYPE_LABELS = frozenset({"Idea", "Story", "Bug", "Spike", FIXTURE})
DEPENDENCY_WORDS = ("depends on", "prerequisite")
BULLET = "- "
HEADING = "#"
CRITERIA = "criteria"

LabelAction = tuple[str, str, str]


@dataclass(frozen=True)
class DressReport:
    labels: tuple[LabelAction, ...]
    cards_dressed: int
    checklists_added: int


@dataclass(frozen=True)
class CardState:
    card_id: str
    title: str
    lane: str
    cover: str | None
    lane_stickers: tuple[str, ...]
    labels: tuple[str, ...]
    description: str
    last_comment: str
    has_checklist: bool


@dataclass(frozen=True)
class CardPlan:
    card_id: str
    cover: tuple[str, ...]
    sticker: tuple[str, ...]
    labels: tuple[str, ...]
    criteria: tuple[str, ...]

    @property
    def changes(self) -> bool:
        return any((self.cover, self.sticker, self.labels, self.criteria))


def _label_action(name: str, colour: str, named: set[str], unnamed: set[str]) -> LabelAction:
    if name in named:
        return ("keep", name, colour)
    if RENAMES.get(colour) == name and colour in unnamed:
        return ("rename", name, colour)
    return ("create", name, colour)


def plan_labels(existing: dict[str, dict]) -> tuple[LabelAction, ...]:
    named = {label.get("name") or "" for label in existing.values()} - {""}
    unnamed = {label.get("color") or "" for label in existing.values() if not label.get("name")}
    palette = tuple(_label_action(n, c, named, unnamed) for n, c in LABELS.items())
    has_ready = READY in named or READY_COLOUR in unnamed
    ready = (_label_action(READY, READY_COLOUR, named, unnamed),) if has_ready else ()
    return (*palette, *ready)


def _is_heading(line: str) -> bool:
    return CRITERIA in line.casefold() and not line.lstrip().startswith(BULLET)


def _bullets(lines: list[str]) -> tuple[str, ...]:
    items: tuple[str, ...] = ()
    for line in (line.strip() for line in lines):
        if line.startswith(BULLET):
            items = (*items, line.removeprefix(BULLET).strip())
        elif line.startswith(HEADING) or (line and items):
            break
    return tuple(item for item in items if item)


def criteria_from_description(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    start = next((n for n, line in enumerate(lines) if _is_heading(line)), None)
    return () if start is None else _bullets(lines[start + 1 :])


def names_prerequisite(comment: str) -> bool:
    if comment.lstrip().startswith(UNBLOCKED):
        return False
    lowered = comment.casefold()
    return any(word in lowered for word in DEPENDENCY_WORDS)


def wanted_labels(state: CardState) -> tuple[str, ...]:
    typed = () if TYPE_LABELS & set(state.labels) else (type_label(state.title, state.lane),)
    fixture = (FIXTURE,) if FIXTURE_TAG in state.title else ()
    shipped = (SHIPPED,) if state.lane == DONE else ()
    depends = (DEPENDS_ON,) if names_prerequisite(state.last_comment) else ()
    return tuple(dict.fromkeys((*typed, *fixture, *shipped, *depends)))


def plan_card(state: CardState) -> CardPlan:
    look = LANE_LOOK[state.lane]
    cover = (look.cover,) if look.cover and state.cover != look.cover else ()
    sticker = (look.sticker,) if look.sticker and state.lane_stickers != (look.sticker,) else ()
    missing = tuple(name for name in wanted_labels(state) if name not in state.labels)
    criteria = () if state.has_checklist else criteria_from_description(state.description)
    return CardPlan(state.card_id, cover, sticker, missing, criteria)


def _unnamed_id(existing: dict[str, dict], colour: str) -> str:
    return next(
        i for i, label in existing.items() if not label.get("name") and label.get("color") == colour
    )


async def _apply_labels(trello: Any, plan: tuple[LabelAction, ...], existing: dict) -> None:
    for action, name, colour in plan:
        if action == "rename":
            await trello.rename_label(_unnamed_id(existing, colour), name)
        elif action == "create":
            await trello.ensure_label(name)


async def _card_state(trello: Any, card_id: str, title: str, lane: str) -> CardState:
    look = await trello.card_look(card_id)
    images = tuple(sticker.get("image") for sticker in await trello.stickers(card_id))
    comments = (await trello.card(card_id)).get("comments", [])
    return CardState(
        card_id=card_id,
        title=title,
        lane=lane,
        cover=look["cover"],
        lane_stickers=tuple(image for image in images if image in LANE_STICKERS),
        labels=tuple(look["labels"]),
        description=look["description"],
        last_comment=comments[0].get("text", "") if comments else "",
        has_checklist=bool(await trello.checklist_items(card_id)),
    )


async def _card_plans(trello: Any) -> tuple[CardPlan, ...]:
    plans: tuple[CardPlan, ...] = ()
    for lane in BOARD_LISTS:
        for summary in await trello.cards_in(lane, LANE_LIMIT):
            state = await _card_state(trello, summary["id"], summary["title"], lane)
            plans = (*plans, plan_card(state))
    return plans


async def _apply_card(trello: Any, plan: CardPlan) -> None:
    for color in plan.cover:
        await trello.set_cover(plan.card_id, color)
    for image in plan.sticker:
        await trello.set_lane_sticker(plan.card_id, image)
    for name in plan.labels:
        await trello.add_label(plan.card_id, name)
    if plan.criteria:
        await trello.add_checklist(plan.card_id, plan.criteria)


async def dress(trello: Any, dry_run: bool) -> DressReport:
    existing = await trello.label_records()
    labels = plan_labels(existing)
    if not dry_run:
        await _apply_labels(trello, labels, existing)
    changed = tuple(plan for plan in await _card_plans(trello) if plan.changes)
    if not dry_run:
        for plan in changed:
            await _apply_card(trello, plan)
    return DressReport(labels, len(changed), sum(1 for plan in changed if plan.criteria))


def report_lines(report: DressReport, dry_run: bool) -> tuple[str, ...]:
    actions = tuple(f"{action} label {name} ({colour})" for action, name, colour in report.labels)
    counts = (
        f"{report.cards_dressed} card(s) dressed",
        f"{report.checklists_added} checklist(s) added",
    )
    note = ("dry run: nothing was written",) if dry_run else ()
    return (*actions, *counts, *note)
