from typing import Any

from factory_tools.lists import BOARD_LISTS

IDEAS_LIST = "Ideas"
LANE_LIMIT = 50
IDEAS: tuple[tuple[str, str], ...] = (
    (
        "Show what is on now and next",
        "When I look up from a hallway conversation I want to see what is on right now and what "
        "starts next. I should not have to scroll the whole day to find it.",
    ),
    (
        "Star a session to add it to my agenda",
        "I want to tap a star on a session I like so it goes into my own plan for the day. "
        "Tapping it again should take it out.",
    ),
    (
        "Keep my agenda when I come back",
        "If I close the page and open it again later, my starred sessions should still be there. "
        "I do not want to sign in for that.",
    ),
    (
        "Filter the schedule by track",
        "I mostly care about one or two tracks, so let me pick a track and see only its sessions. "
        "Clearing the filter should bring the full day back.",
    ),
    (
        "Switch between light and dark",
        "The hall is dark during talks and the foyer is bright, so I want to switch the look. "
        "It should remember my choice.",
    ),
    (
        "Open a session to read more",
        "Tapping a session should show its full title, speakers, room and time in one place. "
        "Closing it should take me back to where I was in the schedule.",
    ),
    (
        "Share my agenda as text",
        "I want to copy my starred sessions as plain text so I can paste them to my team. "
        "Each line should have the time and the title.",
    ),
)


async def seed_ideas(board: Any) -> tuple[str, ...]:
    existing = {
        card["title"] for lane in BOARD_LISTS for card in await board.cards_in(lane, LANE_LIMIT)
    }
    created: tuple[str, ...] = ()
    for title, idea in IDEAS:
        if title in existing:
            continue
        await board.create(IDEAS_LIST, title, idea)
        created = (*created, title)
    return created
