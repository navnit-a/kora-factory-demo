from dataclasses import dataclass
from typing import Literal


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
IDEAS = "Ideas"
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
    label = type_label(title, list_name)
    fixture = (FIXTURE,) if FIXTURE_TAG in title and label != FIXTURE else ()
    return (label, *fixture)


def _dropped(name: str, to_list: str, unblocked: bool) -> bool:
    return (unblocked and name == DEPENDS_ON) or (to_list != IDEAS and name == IDEA)


def labels_after_move(current: tuple[str, ...], to_list: str, reason: str) -> tuple[str, ...]:
    unblocked = to_list != BLOCKED and reason.lstrip().startswith(UNBLOCKED)
    kept = tuple(name for name in current if not _dropped(name, to_list, unblocked))
    shipped = (SHIPPED,) if to_list == DONE and SHIPPED not in kept else ()
    return (*kept, *shipped)
