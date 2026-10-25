from typing import Literal

BOARD_LISTS: tuple[str, ...] = (
    "Ideas",
    "Backlog",
    "Ready",
    "In Progress",
    "Review",
    "Testing",
    "Done",
    "Blocked",
)

ListName = Literal[
    "Ideas", "Backlog", "Ready", "In Progress", "Review", "Testing", "Done", "Blocked"
]


def lists_sentence() -> str:
    return "Lists are: " + ", ".join(BOARD_LISTS) + "."
