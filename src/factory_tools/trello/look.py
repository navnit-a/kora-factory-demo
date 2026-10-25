from dataclasses import dataclass
from typing import Literal

from factory_tools.lists import LANES, display_name


@dataclass(frozen=True)
class LaneLook:
    cover: str | None
    sticker: str | None


LANE_LOOK: dict[str, LaneLook] = {
    "Ideas": LaneLook(None, None),
    "Backlog": LaneLook(None, None),
    "Ready": LaneLook("yellow", None),
    "In Progress": LaneLook("purple", None),
    "Review": LaneLook("orange", "rocketship"),
    "Testing": LaneLook("lime", "thumbsup"),
    "Done": LaneLook("green", "check"),
    "Blocked": LaneLook("red", "warning"),
    "Agent ops": LaneLook("black", None),
}
ACTOR_LABELS: dict[str, str | None] = {lane.name: lane.actor for lane in LANES}
ACTOR_LABEL_NAMES = frozenset(actor for actor in ACTOR_LABELS.values() if actor)
ACTOR_COLOURS: dict[str, str] = {
    "💡 Product owner": "sky_dark",
    "📋 Delivery lead": "yellow_dark",
    "🤖 Senior developer": "purple_dark",
    "🔍 Code reviewer": "orange_dark",
    "🧪 Tester": "lime_dark",
    "🙋 Needs a human": "red_dark",
    "🛰 Agent ops": "blue_light",
}
LABELS: dict[str, str] = {
    "Idea": "sky",
    "Story": "blue",
    "Bug": "red",
    "Spike": "purple",
    "High severity": "red",
    "Depends on": "orange",
    "Shipped": "green",
    "Proposed via Telegram": "pink",
    "Fixture": "black",
    **ACTOR_COLOURS,
}
LabelName = Literal[
    "Idea",
    "Story",
    "Bug",
    "Spike",
    "High severity",
    "Depends on",
    "Shipped",
    "Proposed via Telegram",
    "Fixture",
    "💡 Product owner",
    "📋 Delivery lead",
    "🤖 Senior developer",
    "🔍 Code reviewer",
    "🧪 Tester",
    "🙋 Needs a human",
    "🛰 Agent ops",
]
LANE_STICKERS = frozenset({"rocketship", "thumbsup", "check", "warning"})
STAR = "star"
LANE_STICKER_POS = {"top": -10, "left": 70, "zIndex": 1}
STAR_POS = {"top": -10, "left": 0, "zIndex": 2}
CHECKLIST_NAME = "Acceptance criteria"
COVER_STYLE = {"brightness": "dark", "size": "normal"}
HIGH_SEVERITY = "High severity"
SHIPPED = "Shipped"
DEPENDS_ON = "Depends on"
DONE = "Done"
BLOCKED = "Blocked"
READY = "Ready"
IN_PROGRESS = "In Progress"
BACKLOG = "Backlog"
IDEAS = "Ideas"
AGENT_OPS = "Agent ops"
AGENT_OPS_LABEL = "🛰 Agent ops"
UNTYPED_LANES = frozenset({AGENT_OPS})
IDEA = "Idea"
FIXTURE = "Fixture"
UNBLOCKED = "Unblocked:"
FIXTURE_TAG = "[fixture]"


def type_label(title: str, list_name: str) -> str:
    stripped = title.lstrip()
    if stripped.startswith("Bug:"):
        return "Bug"
    if FIXTURE_TAG in title:
        return FIXTURE
    if stripped.startswith("Spike:"):
        return "Spike"
    return IDEA if list_name == IDEAS else "Story"


def labels_on_create(title: str, list_name: str) -> tuple[str, ...]:
    if list_name in UNTYPED_LANES:
        return _actor(list_name)
    label = type_label(title, list_name)
    fixture = (FIXTURE,) if FIXTURE_TAG in title and label != FIXTURE else ()
    return (label, *fixture, *_actor(list_name))


def _actor(list_name: str) -> tuple[str, ...]:
    actor = ACTOR_LABELS.get(list_name)
    return (actor,) if actor else ()


def _dropped(name: str, to_list: str, unblocked: bool) -> bool:
    return (
        name in ACTOR_LABEL_NAMES
        or (unblocked and name == DEPENDS_ON)
        or (to_list != IDEAS and name == IDEA)
    )


def labels_after_move(current: tuple[str, ...], to_list: str, reason: str) -> tuple[str, ...]:
    unblocked = to_list != BLOCKED and reason.lstrip().startswith(UNBLOCKED)
    kept = tuple(name for name in current if not _dropped(name, to_list, unblocked))
    shipped = (SHIPPED,) if to_list == DONE and SHIPPED not in kept else ()
    return (*kept, *_actor(to_list), *shipped)


def _signature(lane: str) -> str:
    return ACTOR_LABELS.get(lane) or display_name(lane)


def mover(from_list: str, to_list: str) -> str:
    if to_list == IN_PROGRESS and from_list == READY:
        return _signature(IN_PROGRESS)
    if to_list == READY:
        return _signature(BACKLOG)
    if to_list == BLOCKED:
        return display_name(from_list)
    return _signature(from_list)


def signed_reason(from_list: str | None, to_list: str, reason: str) -> str:
    if from_list is None:
        return reason
    return f"{mover(from_list, to_list)} → {display_name(to_list)}: {reason}"
