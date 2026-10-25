import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from tests.tools.trello_helpers import (
    API,
    CARD,
    LISTS,
    body,
    client,
    comment_route,
    delete_route,
    form,
    mock_lists,
    mock_look,
    run,
)


@respx.mock
def test_list_ids_resolves_names_at_call_time():
    renamed = [{**item, "id": "l-ideas-new"} if item["name"] == "Ideas" else item for item in LISTS]
    respx.get(f"{API}/boards/board/lists").mock(
        side_effect=[httpx.Response(200, json=LISTS), httpx.Response(200, json=renamed)]
    )
    c = client()
    assert run(c.list_ids())["Ideas"] == "l-ideas"
    assert run(c.list_ids())["Ideas"] == "l-ideas-new"


DISPLAY_LISTS = [
    {"id": "l-ideas", "name": "💡 Ideas · product owner shapes"},
    {"id": "l-backlog", "name": "📋 Backlog · delivery lead orders"},
    {"id": "l-ready", "name": "🟡 Ready · next for the developer"},
    {"id": "l-progress", "name": "🛠 In Progress · senior developer builds"},
    {"id": "l-review", "name": "🔍 Review · code reviewer reads"},
    {"id": "l-testing", "name": "🧪 Testing · tester proves"},
    {"id": "l-done", "name": "✅ Done · shipped"},
    {"id": "l-blocked", "name": "⛔ Blocked · needs a human"},
]


@respx.mock
def test_list_ids_maps_display_names_to_canonical():
    mock_lists([*DISPLAY_LISTS, {"id": "l-parking", "name": "Parking lot"}])
    assert run(client().list_ids()) == {
        "Ideas": "l-ideas",
        "Backlog": "l-backlog",
        "Ready": "l-ready",
        "In Progress": "l-progress",
        "Review": "l-review",
        "Testing": "l-testing",
        "Done": "l-done",
        "Blocked": "l-blocked",
    }


@respx.mock
def test_list_ids_keeps_the_first_list_matching_a_lane():
    mock_lists([*DISPLAY_LISTS, {"id": "l-ideas-old", "name": "Ideas"}])
    assert run(client().list_ids())["Ideas"] == "l-ideas"


@respx.mock
def test_display_named_board_reads_and_moves_by_canonical_name():
    mock_lists(DISPLAY_LISTS)
    respx.get(f"{API}/lists/l-progress/cards").mock(
        return_value=httpx.Response(200, json=[{"id": "0123456789abcdef0123456a"}])
    )
    route = respx.put(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(200, json={"id": "x", "idBoard": "board"})
    )
    cards = run(client().cards_in("In Progress", 5))
    moved = run(client().move("0123456789abcdef0123456a", "Review"))
    assert [card["list"] for card in cards] == ["In Progress"]
    assert moved == {"id": "0123456789abcdef0123456a", "list": "Review"}
    assert form(route.calls[0].request) == {"idList": "l-review"}


@respx.mock
def test_card_on_a_display_named_board_reports_the_canonical_list():
    mock_lists(DISPLAY_LISTS)
    card_id = "0123456789abcdef0123456a"
    respx.get(f"{API}/cards/{card_id}").mock(
        return_value=httpx.Response(
            200, json={"id": card_id, "idBoard": "board", "idList": "l-testing", "labels": []}
        )
    )
    respx.get(f"{API}/cards/{card_id}/actions").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{API}/cards/{card_id}/checklists").mock(return_value=httpx.Response(200, json=[]))
    assert run(client().card(card_id))["list"] == "Testing"


@respx.mock
def test_unknown_list_name_still_fails_loudly():
    lists = [item for item in DISPLAY_LISTS if item["id"] != "l-review"]
    mock_lists([*lists, {"id": "l-cr", "name": "Code review"}])
    with pytest.raises(ToolError) as caught:
        run(client().cards_in("Review", 10))
    message = str(caught.value)
    assert "No list named 'Review' on the board" in message
    assert "Code review" in message
    assert "🛠 In Progress · senior developer builds" in message
    assert "The factory expects: Ideas, Backlog, Ready, In Progress, Review" in message


@respx.mock
def test_cards_in_unknown_list_names_the_lists():
    mock_lists([{"id": "l-ideas", "name": "Ideas"}])
    with pytest.raises(
        ToolError, match="No list named 'Review' on the board. The board has: Ideas"
    ):
        run(client().cards_in("Review", 10))


@respx.mock
def test_missing_list_error_names_the_lists_the_board_really_has():
    mock_lists([{"id": "l-ideas", "name": "Ideas"}, {"id": "l-cr", "name": "Code review"}])
    with pytest.raises(ToolError) as caught:
        run(client().cards_in("Review", 10))
    message = str(caught.value)
    assert "No list named 'Review' on the board" in message
    assert "The board has: Code review, Ideas" in message


@respx.mock
def test_actor_label_is_created_with_its_lane_colour():
    routes = mock_look(CARD)
    assert run(client().ensure_label("🤖 Senior developer")) == "lab-new"
    assert form(routes["new_label"].calls[0].request) == {
        "name": "🤖 Senior developer",
        "color": "purple_dark",
        "idBoard": "board",
    }


@respx.mock
def test_move_swaps_actor_labels():
    mock_lists(DISPLAY_LISTS)
    routes = mock_look(
        CARD,
        list_id="l-progress",
        card_labels=[
            {"id": "lab-story", "name": "Story"},
            {"id": "lab-dev", "name": "🤖 Senior developer"},
            {"id": "lab-high", "name": "High severity"},
        ],
        board_labels=[{"id": "lab-cr", "name": "🔍 Code reviewer", "color": "orange_dark"}],
    )
    comment = comment_route()
    dev = delete_route(f"/cards/{CARD}/idLabels/lab-dev")
    story = delete_route(f"/cards/{CARD}/idLabels/lab-story")
    high = delete_route(f"/cards/{CARD}/idLabels/lab-high")
    moved = run(client().move_with_reason(CARD, "Review", "PR https://github.com/x/y/pull/4"))
    assert form(comment.calls[0].request) == {
        "text": "🤖 Senior developer → 🔍 Review · code reviewer reads: "
        "PR https://github.com/x/y/pull/4"
    }
    assert dev.called and not story.called and not high.called
    assert [form(call.request) for call in routes["add_label"].calls] == [{"value": "lab-cr"}]
    assert not routes["new_label"].called
    assert moved["comment_posted"] is True and moved["look_applied"] is True


@respx.mock
def test_done_removes_actor_labels():
    mock_lists()
    routes = mock_look(
        CARD,
        list_id="l-testing",
        card_labels=[{"id": "lab-story", "name": "Story"}, {"id": "lab-qa", "name": "🧪 Tester"}],
    )
    comment = comment_route()
    tester = delete_route(f"/cards/{CARD}/idLabels/lab-qa")
    run(client().move_with_reason(CARD, "Done", "Tests pass"))
    assert form(comment.calls[0].request) == {"text": "🧪 Tester → ✅ Done · shipped: Tests pass"}
    assert tester.called
    created = [form(call.request)["name"] for call in routes["new_label"].calls]
    assert created == ["Shipped"]


@respx.mock
def test_a_pull_into_in_progress_is_signed_by_the_developer():
    mock_lists(DISPLAY_LISTS)
    mock_look(CARD, list_id="l-ready")
    comment = comment_route()
    run(client().move_with_reason(CARD, "In Progress", "Starting: the header count"))
    assert form(comment.calls[0].request) == {
        "text": "🤖 Senior developer → 🛠 In Progress · senior developer builds: "
        "Starting: the header count"
    }


@respx.mock
def test_move_from_a_list_outside_the_lanes_posts_the_reason_unsigned():
    mock_lists([*LISTS, {"id": "l-parking", "name": "Parking lot"}])
    mock_look(CARD, list_id="l-parking")
    comment = comment_route()
    run(client().move_with_reason(CARD, "Backlog", "Back in the queue"))
    assert form(comment.calls[0].request) == {"text": "Back in the queue"}


@respx.mock
def test_board_lists_returns_the_raw_lists_with_ids():
    mock_lists(DISPLAY_LISTS)
    assert run(client().board_lists()) == DISPLAY_LISTS


@respx.mock
def test_rename_list_puts_the_new_name():
    route = respx.put(f"{API}/lists/l-ideas").mock(return_value=httpx.Response(200, json={}))
    run(client().rename_list("l-ideas", "💡 Ideas · product owner shapes"))
    assert form(route.calls[0].request) == {"name": "💡 Ideas · product owner shapes"}


@respx.mock
def test_move_applies_cover_and_replaces_lane_sticker_keeping_star():
    mock_lists()
    routes = mock_look(
        CARD, stickers=[{"id": "s1", "image": "rocketship"}, {"id": "s2", "image": "star"}]
    )
    respx.post(f"{API}/cards/{CARD}/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    old_lane = delete_route(f"/cards/{CARD}/stickers/s1")
    star = delete_route(f"/cards/{CARD}/stickers/s2")
    moved = run(client().move_with_reason(CARD, "Testing", "PR #4 approved"))
    puts = routes["put"].calls
    assert form(puts[0].request) == {"idList": "l-testing"}
    assert body(puts[1].request) == {
        "cover": {"color": "lime", "brightness": "dark", "size": "normal"}
    }
    assert old_lane.called and not star.called
    assert form(routes["add_sticker"].calls[0].request) == {
        "image": "thumbsup",
        "top": "-10",
        "left": "70",
        "zIndex": "1",
    }
    assert moved == {
        "id": CARD,
        "list": "Testing",
        "comment_posted": True,
        "look_applied": True,
        "detail": "",
    }


@respx.mock
def test_move_to_a_lane_without_cover_clears_it_and_adds_no_sticker():
    mock_lists()
    routes = mock_look(CARD, stickers=[{"id": "s1", "image": "warning"}])
    respx.post(f"{API}/cards/{CARD}/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    warning = delete_route(f"/cards/{CARD}/stickers/s1")
    run(client().move_with_reason(CARD, "Backlog", "Unblocked: back to the queue"))
    assert body(routes["put"].calls[1].request) == {"cover": {"color": None}}
    assert warning.called and not routes["add_sticker"].called
