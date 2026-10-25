from dataclasses import dataclass
from typing import Any

from factory_demo.dress_card import (
    CardPlan,
    CardState,
    criteria_from_description,
    names_prerequisite,
    plan_card,
    resolve_labels,
)
from factory_tools.lists import BOARD_LISTS, canonical_name, display_name
from factory_tools.trello.look import (
    AGENT_OPS,
    DEPENDS_ON,
    LABELS,
    LANE_STICKERS,
    SHIPPED,
    WATCH_LOG_TITLE,
)

__all__ = [
    "DressReport",
    "criteria_from_description",
    "dress",
    "names_prerequisite",
    "plan_labels",
    "report_lines",
]

LANE_LIMIT = 100
READY = "Ready"
READY_COLOUR = "yellow"
COLOUR_NAMES = dict(blue="Story", green=SHIPPED, orange=DEPENDS_ON, purple="Spike", red="Bug")
RENAMES = {**COLOUR_NAMES, READY_COLOUR: READY}
RENAME = "rename"
RELABEL_HEADER = "Cards whose colour label becomes:"
CREATE = "create"
WATCH_LOG_DESCRIPTION = "Agent ops writes what it checked and found here after every run."

LabelAction = tuple[str, str, str]
LaneRename = tuple[str, str, str]


@dataclass(frozen=True)
class DressReport:
    labels: tuple[LabelAction, ...]
    cards_dressed: int
    checklists_added: int
    relabelled_cards: tuple[tuple[str, str], ...]
    renamed_lanes: tuple[tuple[str, str], ...] = ()
    created_lanes: tuple[str, ...] = ()
    created_cards: tuple[str, ...] = ()

    @property
    def lists_renamed(self) -> int:
        return len(self.renamed_lanes)


def _label_action(name: str, colour: str, named: set[str], unnamed: set[str]) -> LabelAction:
    if name in named:
        return ("keep", name, colour)
    if RENAMES.get(colour) == name and colour in unnamed:
        return (RENAME, name, colour)
    return (CREATE, name, colour)


def plan_labels(existing: dict[str, dict]) -> tuple[LabelAction, ...]:
    named = {label.get("name") or "" for label in existing.values()} - {""}
    unnamed = {label.get("color") or "" for label in existing.values() if not label.get("name")}
    palette = tuple(_label_action(n, c, named, unnamed) for n, c in LABELS.items())
    has_ready = READY in named or READY_COLOUR in unnamed
    ready = (_label_action(READY, READY_COLOUR, named, unnamed),) if has_ready else ()
    return (*palette, *ready)


def plan_lanes(lists: list[dict]) -> tuple[LaneRename, ...]:
    matched = ((item["id"], item["name"], canonical_name(item["name"])) for item in lists)
    return tuple(
        (list_id, raw, display_name(lane))
        for list_id, raw, lane in matched
        if lane and raw != display_name(lane)
    )


def present_lanes(lists: list[dict]) -> tuple[str, ...]:
    found = {canonical_name(item["name"]) for item in lists}
    return tuple(lane for lane in BOARD_LISTS if lane in found)


def plan_new_lanes(lists: list[dict]) -> tuple[str, ...]:
    present = present_lanes(lists)
    return tuple(display_name(lane) for lane in BOARD_LISTS if lane not in present)


def plan_watch_log(states: tuple[CardState, ...]) -> tuple[str, ...]:
    found = any(s.lane == AGENT_OPS and s.title == WATCH_LOG_TITLE for s in states)
    return () if found else (WATCH_LOG_TITLE,)


def renamed_colours(plan: tuple[LabelAction, ...]) -> dict[str, str]:
    return {colour: name for action, name, colour in plan if action == RENAME}


def _unnamed_id(existing: dict[str, dict], colour: str) -> str:
    return next(
        i for i, label in existing.items() if not label.get("name") and label.get("color") == colour
    )


async def _apply_labels(trello: Any, plan: tuple[LabelAction, ...], existing: dict) -> None:
    for action, name, colour in plan:
        if action == RENAME:
            await trello.rename_label(_unnamed_id(existing, colour), name)
        elif action == CREATE:
            await trello.ensure_label(name)


async def _card_state(trello: Any, summary: dict, lane: str, renamed: dict) -> CardState:
    card_id = summary["id"]
    look = await trello.card_look(card_id)
    labels, relabelled = resolve_labels(tuple(look["labels"]), renamed)
    images = tuple(sticker.get("image") for sticker in await trello.stickers(card_id))
    comments = (await trello.card(card_id)).get("comments", [])
    return CardState(
        card_id=card_id,
        title=summary["title"],
        lane=lane,
        cover=look["cover"],
        lane_stickers=tuple(image for image in images if image in LANE_STICKERS),
        labels=labels,
        relabelled=relabelled,
        description=look["description"],
        last_comment=comments[0].get("text", "") if comments else "",
        has_checklist=bool(await trello.checklist_items(card_id)),
    )


async def _card_states(
    trello: Any, renamed: dict[str, str], lanes: tuple[str, ...]
) -> tuple[CardState, ...]:
    states: tuple[CardState, ...] = ()
    for lane in lanes:
        for summary in await trello.cards_in(lane, LANE_LIMIT):
            states = (*states, await _card_state(trello, summary, lane, renamed))
    return states


async def _apply_card(trello: Any, plan: CardPlan) -> None:
    for color in plan.cover:
        await trello.set_cover(plan.card_id, color)
    for image in plan.sticker:
        await trello.set_lane_sticker(plan.card_id, image)
    for name in plan.labels:
        await trello.add_label(plan.card_id, name)
    for name in plan.unlabel:
        await trello.remove_label(plan.card_id, name)
    if plan.criteria:
        await trello.add_checklist(plan.card_id, plan.criteria)


async def _apply_lanes(trello: Any, lanes: tuple[LaneRename, ...]) -> None:
    for list_id, _, name in lanes:
        await trello.rename_list(list_id, name)


async def _apply_new_lanes(trello: Any, names: tuple[str, ...]) -> None:
    for name in names:
        await trello.create_list(name, pos="bottom")


async def _apply_new_cards(trello: Any, titles: tuple[str, ...]) -> None:
    for title in titles:
        await trello.create(AGENT_OPS, title, WATCH_LOG_DESCRIPTION)


async def dress(trello: Any, dry_run: bool) -> DressReport:
    lists = await trello.board_lists()
    lanes, new_lanes = plan_lanes(lists), plan_new_lanes(lists)
    existing = await trello.label_records()
    labels = plan_labels(existing)
    states = await _card_states(trello, renamed_colours(labels), present_lanes(lists))
    plans = tuple(plan for plan in map(plan_card, states) if plan.changes)
    new_cards = plan_watch_log(states)
    if not dry_run:
        await _apply_lanes(trello, lanes)
        await _apply_new_lanes(trello, new_lanes)
        await _apply_labels(trello, labels, existing)
        for plan in plans:
            await _apply_card(trello, plan)
        await _apply_new_cards(trello, new_cards)
    relabelled = tuple(sorted((s.title, name) for s in states for name in s.relabelled))
    checklists = sum(1 for plan in plans if plan.criteria)
    renamed = tuple((raw, name) for _, raw, name in lanes)
    return DressReport(labels, len(plans), checklists, relabelled, renamed, new_lanes, new_cards)


def _relabel_lines(relabelled: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
    if not relabelled:
        return (f"{RELABEL_HEADER} none",)
    return (RELABEL_HEADER, *(f"  {title}: {name}" for title, name in relabelled))


def report_lines(report: DressReport, dry_run: bool) -> tuple[str, ...]:
    created = tuple(f"{CREATE} lane {name}" for name in report.created_lanes)
    lanes = tuple(f"{RENAME} lane {old} → {new}" for old, new in report.renamed_lanes)
    actions = tuple(f"{action} label {name} ({colour})" for action, name, colour in report.labels)
    cards = tuple(f"{CREATE} card {title}" for title in report.created_cards)
    counts = (
        f"{report.cards_dressed} card(s) dressed",
        f"{report.checklists_added} checklist(s) added",
    )
    note = ("dry run: nothing was written",) if dry_run else ()
    relabels = _relabel_lines(report.relabelled_cards)
    return (*created, *lanes, *actions, *cards, *relabels, *counts, *note)
