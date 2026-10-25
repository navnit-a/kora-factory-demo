SERVERS = ("trello", "telegram", "transport", "places")
TOOLS_BY_SERVER = {
    "trello": (
        "trello_list_cards",
        "trello_get_card",
        "trello_move_card",
        "trello_comment_card",
        "trello_create_card",
        "trello_update_card_description",
        "trello_add_label",
        "trello_add_checklist",
        "trello_check_item",
        "trello_set_priority",
    ),
    "telegram": ("telegram_send_message",),
    "transport": ("transport_sydney_trains_status",),
    "places": ("places_lunch_nearby",),
}
PLATFORM_TOOLS = {
    "kora": ("runs.list", "runs.get", "runs.events", "triggers.get", "triggers.deliveries.list"),
}


def expected_tool_names() -> set[str]:
    return {tool for tools in TOOLS_BY_SERVER.values() for tool in tools}


def missing_tools(listed: dict[str, list[str]]) -> list[str]:
    present = {tool for tools in listed.values() for tool in tools}
    return sorted(expected_tool_names() - present)
