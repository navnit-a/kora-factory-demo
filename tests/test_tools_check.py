from factory_demo.tools_check import SERVERS, expected_tool_names, missing_tools


def test_expected_tools_are_the_nine_from_the_design():
    assert expected_tool_names() == {
        "trello_list_cards",
        "trello_get_card",
        "trello_move_card",
        "trello_comment_card",
        "trello_create_card",
        "trello_update_card_description",
        "telegram_send_message",
        "transport_sydney_trains_status",
        "places_lunch_nearby",
    }
    assert SERVERS == ("trello", "telegram", "transport", "places")


def test_missing_tools_lists_names_not_yet_listed_by_the_gateway():
    listed = {"trello": ["trello_list_cards"], "telegram": ["telegram_send_message"]}
    missing = missing_tools(listed)
    assert "trello_move_card" in missing and "places_lunch_nearby" in missing
    assert "telegram_send_message" not in missing


def test_missing_tools_is_empty_when_all_nine_are_listed():
    listed = {
        "trello": [
            "trello_list_cards",
            "trello_get_card",
            "trello_move_card",
            "trello_comment_card",
            "trello_create_card",
            "trello_update_card_description",
        ],
        "telegram": ["telegram_send_message"],
        "transport": ["transport_sydney_trains_status"],
        "places": ["places_lunch_nearby"],
    }
    assert missing_tools(listed) == []
