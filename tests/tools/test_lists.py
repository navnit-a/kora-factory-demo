from factory_tools.lists import BOARD_LISTS


def test_board_lists_are_the_eight_in_board_order():
    assert BOARD_LISTS == (
        "Ideas",
        "Backlog",
        "Ready",
        "In Progress",
        "Review",
        "Testing",
        "Done",
        "Blocked",
    )
