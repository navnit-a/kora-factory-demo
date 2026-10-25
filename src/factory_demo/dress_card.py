from dataclasses import dataclass

from factory_tools.trello.look import (
    DEPENDS_ON,
    DONE,
    FIXTURE_TAG,
    LANE_LOOK,
    SHIPPED,
    UNBLOCKED,
    type_label,
)

FIXTURE = "Fixture"
TYPE_LABELS = frozenset({"Idea", "Story", "Bug", "Spike", FIXTURE})
DEPENDENCY_WORDS = ("depends on", "prerequisite")
BULLET = "- "
HEADING = "#"
CRITERIA = "criteria"


@dataclass(frozen=True)
class CardState:
    card_id: str
    title: str
    lane: str
    cover: str | None
    lane_stickers: tuple[str, ...]
    labels: tuple[str, ...]
    relabelled: tuple[str, ...]
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


def resolve_labels(
    labels: tuple[dict, ...], renamed: dict[str, str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    unnamed = tuple(label.get("color") or "" for label in labels if not label.get("name"))
    relabelled = tuple(renamed[colour] for colour in unnamed if colour in renamed)
    named = tuple(label["name"] for label in labels if label.get("name"))
    return tuple(dict.fromkeys((*named, *relabelled))), relabelled


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
