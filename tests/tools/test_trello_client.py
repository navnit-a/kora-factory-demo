import asyncio
import json

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from factory_tools.trello.client import TrelloClient

API = "https://api.trello.com/1"
LISTS = [
    {"id": "l-ideas", "name": "Ideas"},
    {"id": "l-backlog", "name": "Backlog"},
    {"id": "l-ready", "name": "Ready"},
    {"id": "l-progress", "name": "In Progress"},
    {"id": "l-review", "name": "Review"},
    {"id": "l-testing", "name": "Testing"},
    {"id": "l-done", "name": "Done"},
    {"id": "l-blocked", "name": "Blocked"},
]


def form(request: httpx.Request) -> dict:
    return dict(httpx.QueryParams(request.content.decode()))


def body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def mock_look(
    card_id: str,
    stickers: list[dict] | None = None,
    card_labels: list[dict] | None = None,
    board_labels: list[dict] | None = None,
) -> dict[str, respx.Route]:
    card = {"id": card_id, "idBoard": "board", "labels": card_labels or []}
    return {
        "card": respx.get(f"{API}/cards/{card_id}").mock(
            return_value=httpx.Response(200, json=card)
        ),
        "put": respx.put(f"{API}/cards/{card_id}").mock(return_value=httpx.Response(200, json={})),
        "stickers": respx.get(f"{API}/cards/{card_id}/stickers").mock(
            return_value=httpx.Response(200, json=stickers or [])
        ),
        "add_sticker": respx.post(f"{API}/cards/{card_id}/stickers").mock(
            return_value=httpx.Response(200, json={"id": "s-new"})
        ),
        "board_labels": respx.get(f"{API}/boards/board/labels").mock(
            return_value=httpx.Response(200, json=board_labels or [])
        ),
        "new_label": respx.post(f"{API}/labels").mock(
            return_value=httpx.Response(200, json={"id": "lab-new"})
        ),
        "add_label": respx.post(f"{API}/cards/{card_id}/idLabels").mock(
            return_value=httpx.Response(200, json=[])
        ),
    }


def client() -> TrelloClient:
    return TrelloClient("key", "token", "board", httpx.AsyncClient())


def run(coro):
    return asyncio.run(coro)


def mock_lists(lists: list[dict] = LISTS) -> respx.Route:
    return respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=lists))


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
def test_cards_in_requests_the_list_id_with_a_limit():
    mock_lists()
    route = respx.get(f"{API}/lists/l-ready/cards").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "0123456789abcdef0123456a",
                    "name": "Add now and next",
                    "shortUrl": "https://trello.com/c/c1",
                    "dateLastActivity": "2026-10-25T01:00:00.000Z",
                }
            ],
        )
    )
    cards = run(client().cards_in("Ready", 10))
    assert cards == [
        {
            "id": "0123456789abcdef0123456a",
            "title": "Add now and next",
            "list": "Ready",
            "url": "https://trello.com/c/c1",
            "last_activity": "2026-10-25T01:00:00.000Z",
        }
    ]
    assert route.calls[0].request.url.params["limit"] == "10"


@respx.mock
def test_card_includes_last_five_comments_truncated():
    mock_lists()
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "0123456789abcdef0123456a",
                "name": "Add now and next",
                "desc": "d" * 1300,
                "idList": "l-review",
                "idBoard": "board",
                "shortUrl": "https://trello.com/c/c1",
                "dateLastActivity": "2026-10-25T01:00:00.000Z",
            },
        )
    )
    actions = respx.get(f"{API}/cards/0123456789abcdef0123456a/actions").mock(
        return_value=httpx.Response(
            200,
            json=[{"date": "2026-10-25T00:59:00.000Z", "data": {"text": "x" * 1300}}],
        )
    )
    respx.get(f"{API}/cards/0123456789abcdef0123456a/checklists").mock(
        return_value=httpx.Response(200, json=[])
    )
    card = run(client().card("0123456789abcdef0123456a"))
    assert card["list"] == "Review"
    assert card["description"].endswith(" (truncated)")
    assert card["labels"] == [] and card["checklist"] == []
    assert card["comments"] == [
        {"when": "2026-10-25T00:59:00.000Z", "text": "x" * 1200 + " (truncated)"}
    ]
    params = actions.calls[0].request.url.params
    assert params["filter"] == "commentCard" and params["limit"] == "5"


@respx.mock
def test_move_sends_the_target_list_id():
    mock_lists()
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456a", "idBoard": "board"}
        )
    )
    put = respx.put(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456a", "idList": "l-done"}
        )
    )
    moved = run(client().move("0123456789abcdef0123456a", "Done"))
    assert form(put.calls[0].request)["idList"] == "l-done"
    assert moved == {"id": "0123456789abcdef0123456a", "list": "Done"}


@respx.mock
def test_create_posts_to_the_list_id():
    mock_lists()
    post = respx.post(f"{API}/cards").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456b", "shortUrl": "https://trello.com/c/c9"}
        )
    )
    mock_look("0123456789abcdef0123456b", board_labels=[{"id": "lab-idea", "name": "Idea"}])
    created = run(client().create("Ideas", "Dark mode", "Attendees in a dim hall"))
    fields = form(post.calls[0].request)
    assert fields["idList"] == "l-ideas" and fields["name"] == "Dark mode"
    assert created == {
        "id": "0123456789abcdef0123456b",
        "url": "https://trello.com/c/c9",
        "list": "Ideas",
        "label": "Idea",
        "look_applied": True,
        "detail": "",
    }


@respx.mock
def test_comment_and_description_use_their_endpoints():
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456a", "idBoard": "board"}
        )
    )
    comment = respx.post(f"{API}/cards/0123456789abcdef0123456a/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    desc = respx.put(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(200, json={"id": "0123456789abcdef0123456a"})
    )
    assert run(client().comment("0123456789abcdef0123456a", "done")) == {
        "id": "0123456789abcdef0123456a",
        "comment_id": "a1",
    }
    assert form(comment.calls[0].request)["text"] == "done"
    assert run(client().set_description("0123456789abcdef0123456a", "new")) == {
        "id": "0123456789abcdef0123456a",
        "description_updated": True,
    }
    assert form(desc.calls[0].request)["desc"] == "new"


@respx.mock
def test_429_surfaces_the_wait():
    respx.get(f"{API}/boards/board/lists").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "3"})
    )
    with pytest.raises(ToolError, match="Trello is rate limiting; try again in 3s"):
        run(client().list_ids())


def test_from_env_reads_the_three_variables(monkeypatch):
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_TOKEN", "t")
    monkeypatch.setenv("TRELLO_BOARD_ID", "b")
    c = TrelloClient.from_env(httpx.AsyncClient())
    assert (c.key, c.token, c.board_id) == ("k", "t", "b")


def test_from_env_names_a_missing_variable(monkeypatch):
    monkeypatch.delenv("TRELLO_TOKEN", raising=False)
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_BOARD_ID", "b")
    with pytest.raises(ToolError, match="TRELLO_TOKEN"):
        TrelloClient.from_env(httpx.AsyncClient())


@pytest.mark.parametrize("bad", ["../boards/x", "c1/actions", "abc def", "", "x" * 30])
def test_card_ids_that_are_not_trello_ids_are_rejected_before_any_call(bad):
    with pytest.raises(ToolError, match="not a Trello card id"):
        run(client().card(bad))


@respx.mock
def test_a_card_on_another_board_is_refused():
    respx.get(f"{API}/cards/0123456789abcdef01234567").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef01234567", "idBoard": "other"}
        )
    )
    move = respx.put(f"{API}/cards/0123456789abcdef01234567")
    with pytest.raises(ToolError, match="not on the factory board"):
        run(client().move("0123456789abcdef01234567", "Done"))
    assert not move.called


@respx.mock
def test_missing_list_error_names_the_lists_the_board_really_has():
    mock_lists([{"id": "l-ideas", "name": "Ideas"}, {"id": "l-cr", "name": "Code review"}])
    with pytest.raises(ToolError) as caught:
        run(client().cards_in("Review", 10))
    message = str(caught.value)
    assert "No list named 'Review' on the board" in message
    assert "The board has: Code review, Ideas" in message


@respx.mock
def test_writes_send_text_in_the_form_body_not_the_url():
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(200, json={"idBoard": "board"})
    )
    route = respx.post(f"{API}/cards/0123456789abcdef0123456a/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    run(client().comment("0123456789abcdef0123456a", "x" * 5000))
    request = route.calls[0].request
    assert "text" not in request.url.params
    assert dict(httpx.QueryParams(request.content.decode()))["text"] == "x" * 5000


@respx.mock
def test_non_json_reply_is_a_tool_error_with_a_next_step():
    respx.get(f"{API}/boards/board/lists").mock(
        return_value=httpx.Response(200, text="<html>maintenance</html>")
    )
    with pytest.raises(ToolError, match="Trello sent a reply that is not JSON"):
        run(client().list_ids())


CARD = "0123456789abcdef0123456a"


@respx.mock
def test_archive_closes_a_card_on_the_board():
    respx.get(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "idBoard": "board"})
    )
    put = respx.put(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "closed": True})
    )
    assert run(client().archive(CARD)) == {"id": CARD, "archived": True}
    assert form(put.calls[0].request) == {"closed": "true"}


@respx.mock
def test_archive_refuses_a_card_on_another_board():
    respx.get(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "idBoard": "elsewhere"})
    )
    with pytest.raises(ToolError, match="not on the factory board"):
        run(client().archive(CARD))


@respx.mock
def test_archive_failure_never_shows_the_credentials():
    respx.get(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "idBoard": "board"})
    )
    respx.put(f"{API}/cards/{CARD}").mock(return_value=httpx.Response(500, text="oops"))
    with pytest.raises(ToolError) as caught:
        run(client().archive(CARD))
    assert "token" not in str(caught.value)
    assert "key=" not in str(caught.value)


def test_no_tool_can_archive():
    from factory_demo.tools_check import expected_tool_names

    assert not [name for name in expected_tool_names() if "archive" in name or "delete" in name]


def delete_route(path: str) -> respx.Route:
    return respx.delete(f"{API}{path}").mock(return_value=httpx.Response(200, json={}))


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


@respx.mock
def test_move_still_happens_when_the_look_fails():
    mock_lists()
    routes = mock_look(CARD)
    down = httpx.Response(503, text="down")
    routes["put"].mock(side_effect=[httpx.Response(200, json={}), down] * 2)
    comment = respx.post(f"{API}/cards/{CARD}/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    moved = run(client().move_with_reason(CARD, "Review", "PR #4 opened"))
    assert comment.called
    assert form(routes["put"].calls[0].request) == {"idList": "l-review"}
    assert moved["list"] == "Review" and moved["comment_posted"] is True
    assert moved["look_applied"] is False
    assert "HTTP 503" in moved["detail"]
    assert "token" not in moved["detail"]
    assert form(routes["add_sticker"].calls[0].request)["image"] == "rocketship"
    shipped = run(client().move_with_reason(CARD, "Done", "Tests pass"))
    assert shipped["list"] == "Done" and shipped["look_applied"] is False
    assert "HTTP 503" in shipped["detail"]
    assert form(routes["new_label"].calls[0].request)["name"] == "Shipped"
    assert form(routes["add_label"].calls[0].request) == {"value": "lab-new"}
    assert form(routes["add_sticker"].calls[1].request)["image"] == "check"


@respx.mock
def test_look_relabels_before_the_cover_and_joins_every_failure():
    mock_lists()
    routes = mock_look(CARD)
    routes["put"].mock(side_effect=[httpx.Response(200, json={}), httpx.Response(503, text="a")])
    routes["stickers"].mock(return_value=httpx.Response(502, text="b"))
    respx.post(f"{API}/cards/{CARD}/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    moved = run(client().move_with_reason(CARD, "Done", "Tests pass"))
    assert "HTTP 503" in moved["detail"] and "HTTP 502" in moved["detail"]
    order = [call.request.url.path for call in respx.calls]
    cover = max(n for n, call in enumerate(respx.calls) if call.request.method == "PUT")
    assert order.index(f"/1/cards/{CARD}/idLabels") < cover
    assert order.index(f"/1/cards/{CARD}/stickers") > cover


@respx.mock
def test_move_to_done_adds_shipped_and_unblocking_drops_depends_on():
    mock_lists()
    routes = mock_look(
        CARD,
        card_labels=[{"id": "lab-story", "name": "Story"}, {"id": "lab-dep", "name": "Depends on"}],
        board_labels=[{"id": "lab-story", "name": "Story", "color": "blue"}],
    )
    respx.post(f"{API}/cards/{CARD}/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    drop = delete_route(f"/cards/{CARD}/idLabels/lab-dep")
    run(client().move_with_reason(CARD, "Done", "Tests pass"))
    assert form(routes["new_label"].calls[0].request) == {
        "name": "Shipped",
        "color": "green",
        "idBoard": "board",
    }
    assert form(routes["add_label"].calls[0].request) == {"value": "lab-new"}
    assert not drop.called
    run(client().move_with_reason(CARD, "Ready", "Unblocked: the API is back"))
    assert drop.called


@respx.mock
def test_create_sets_the_type_label():
    mock_lists()
    respx.post(f"{API}/cards").mock(
        return_value=httpx.Response(200, json={"id": CARD, "shortUrl": "https://trello.com/c/c9"})
    )
    routes = mock_look(CARD, board_labels=[{"id": "lab-bug", "name": "Bug", "color": "red"}])
    created = run(client().create("Ideas", "Bug: times show in UTC", "They should be local"))
    assert created["label"] == "Bug" and created["look_applied"] is True
    assert form(routes["add_label"].calls[0].request) == {"value": "lab-bug"}
    assert not routes["new_label"].called
    assert body(routes["put"].calls[0].request) == {"cover": {"color": None}}


@respx.mock
def test_create_adds_fixture_beside_the_prefix_label():
    mock_lists()
    respx.post(f"{API}/cards").mock(
        return_value=httpx.Response(200, json={"id": CARD, "shortUrl": "https://trello.com/c/c9"})
    )
    routes = mock_look(
        CARD,
        board_labels=[
            {"id": "lab-bug", "name": "Bug", "color": "red"},
            {"id": "lab-fix", "name": "Fixture", "color": "black"},
        ],
    )
    created = run(client().create("Backlog", "Bug: times show in UTC [fixture]", "d"))
    assert created["label"] == "Bug" and created["look_applied"] is True
    added = [form(call.request) for call in routes["add_label"].calls]
    assert added == [{"value": "lab-bug"}, {"value": "lab-fix"}]
    fixture = run(client().create("Backlog", "Count the sessions [fixture]", "d"))
    assert fixture["label"] == "Fixture"
    assert routes["add_label"].call_count == 3
    assert form(routes["add_label"].calls[2].request) == {"value": "lab-fix"}


@respx.mock
def test_create_reports_a_look_failure_but_keeps_the_card():
    mock_lists()
    respx.post(f"{API}/cards").mock(
        return_value=httpx.Response(200, json={"id": CARD, "shortUrl": "u"})
    )
    routes = mock_look(CARD)
    routes["board_labels"].mock(return_value=httpx.Response(500, text="oops"))
    created = run(client().create("Backlog", "Add a map", "d"))
    assert created["id"] == CARD and created["label"] == "Story"
    assert created["look_applied"] is False and "HTTP 500" in created["detail"]


@respx.mock
def test_ensure_label_creates_missing_known_labels_only():
    routes = mock_look(CARD, board_labels=[{"id": "lab-idea", "name": "Idea", "color": "sky"}])
    c = client()
    assert run(c.ensure_label("Idea")) == "lab-idea"
    assert not routes["new_label"].called
    assert run(c.ensure_label("Depends on")) == "lab-new"
    assert form(routes["new_label"].calls[0].request) == {
        "name": "Depends on",
        "color": "orange",
        "idBoard": "board",
    }
    with pytest.raises(ToolError, match="No label named 'Urgent'.*Bug.*High severity"):
        run(c.ensure_label("Urgent"))
    assert routes["new_label"].call_count == 1


@respx.mock
def test_board_labels_skip_unnamed_ones():
    mock_look(
        CARD, board_labels=[{"id": "x", "name": "", "color": "red"}, {"id": "b", "name": "Bug"}]
    )
    assert run(client().board_labels()) == {"Bug": "b"}


@respx.mock
def test_add_and_remove_label_check_the_card_first():
    routes = mock_look(
        CARD,
        card_labels=[{"id": "lab-tg", "name": "Proposed via Telegram"}],
        board_labels=[{"id": "lab-tg", "name": "Proposed via Telegram"}],
    )
    drop = delete_route(f"/cards/{CARD}/idLabels/lab-tg")
    c = client()
    assert run(c.card_labels(CARD)) == ("Proposed via Telegram",)
    assert run(c.add_label(CARD, "Proposed via Telegram")) == {
        "id": CARD,
        "label": "Proposed via Telegram",
        "added": False,
    }
    assert not routes["add_label"].called
    assert run(c.add_label(CARD, "Spike"))["added"] is True
    assert run(c.remove_label(CARD, "Proposed via Telegram"))["removed"] is True
    assert drop.called
    assert run(c.remove_label(CARD, "Bug"))["removed"] is False


CHECKLISTS = [
    {
        "id": "cl-old",
        "name": "Acceptance criteria",
        "checkItems": [
            {
                "id": "i1",
                "name": "Given a session, when I star it, then it shows",
                "state": "incomplete",
            },
            {"id": "i2", "name": "The header counts sessions", "state": "complete"},
        ],
    },
    {"id": "cl-notes", "name": "Notes", "checkItems": []},
]


def mock_checklists(card_id: str = CARD) -> dict[str, respx.Route]:
    return {
        "card": respx.get(f"{API}/cards/{card_id}").mock(
            return_value=httpx.Response(200, json={"id": card_id, "idBoard": "board"})
        ),
        "list": respx.get(f"{API}/cards/{card_id}/checklists").mock(
            return_value=httpx.Response(200, json=CHECKLISTS)
        ),
        "check": respx.put(url__regex=rf"{API}/cards/{card_id}/checkItem/\w+").mock(
            return_value=httpx.Response(200, json={})
        ),
    }


@respx.mock
def test_add_checklist_replaces_existing_items():
    mock_checklists()
    old = delete_route("/checklists/cl-old")
    notes = delete_route("/checklists/cl-notes")
    create = respx.post(f"{API}/cards/{CARD}/checklists").mock(
        return_value=httpx.Response(200, json={"id": "cl-new"})
    )
    item = respx.post(f"{API}/checklists/cl-new/checkItems").mock(
        return_value=httpx.Response(200, json={"id": "i"})
    )
    items = ("Stars persist", "Header shows the count", "Works offline")
    assert run(client().add_checklist(CARD, items)) == {"id": CARD, "checklist_items": 3}
    assert old.called and not notes.called
    assert form(create.calls[0].request) == {"name": "Acceptance criteria"}
    assert [form(call.request) for call in item.calls] == [
        {"name": text, "checked": "false"} for text in items
    ]


@respx.mock
def test_add_checklist_writes_the_new_items_before_deleting_the_old():
    mock_checklists()
    delete_route("/checklists/cl-old")
    respx.post(f"{API}/cards/{CARD}/checklists").mock(
        return_value=httpx.Response(200, json={"id": "cl-new"})
    )
    respx.post(f"{API}/checklists/cl-new/checkItems").mock(
        return_value=httpx.Response(200, json={"id": "i"})
    )
    run(client().add_checklist(CARD, ("Stars persist", "Works offline")))
    writes = [
        (call.request.method, call.request.url.path)
        for call in respx.calls
        if call.request.method != "GET"
    ]
    assert writes == [
        ("POST", f"/1/cards/{CARD}/checklists"),
        ("POST", "/1/checklists/cl-new/checkItems"),
        ("POST", "/1/checklists/cl-new/checkItems"),
        ("DELETE", "/1/checklists/cl-old"),
    ]


@respx.mock
def test_add_checklist_keeps_the_old_criteria_when_a_write_fails():
    mock_checklists()
    old = delete_route("/checklists/cl-old")
    respx.post(f"{API}/cards/{CARD}/checklists").mock(
        return_value=httpx.Response(200, json={"id": "cl-new"})
    )
    respx.post(f"{API}/checklists/cl-new/checkItems").mock(
        return_value=httpx.Response(500, text="oops")
    )
    with pytest.raises(ToolError, match="HTTP 500"):
        run(client().add_checklist(CARD, ("Stars persist",)))
    assert not old.called


@respx.mock
def test_checklist_items_reads_only_the_acceptance_criteria():
    mock_checklists()
    assert run(client().checklist_items(CARD)) == (
        ("Given a session, when I star it, then it shows", "incomplete"),
        ("The header counts sessions", "complete"),
    )


@respx.mock
def test_check_item_matches_exact_text_then_a_prefix():
    routes = mock_checklists()
    c = client()
    ticked = run(c.check_item(CARD, "given a session"))
    assert ticked == {
        "id": CARD,
        "item": "Given a session, when I star it, then it shows",
        "already_complete": False,
    }
    request = routes["check"].calls[0].request
    assert request.url.path.endswith("/checkItem/i1")
    assert form(request) == {"state": "complete"}
    again = run(c.check_item(CARD, "The header counts sessions"))
    assert again["already_complete"] is True
    assert routes["check"].call_count == 1


@respx.mock
def test_check_item_names_the_items_when_missing():
    routes = mock_checklists()
    with pytest.raises(ToolError) as caught:
        run(client().check_item(CARD, "Dark mode works"))
    message = str(caught.value)
    assert "No acceptance criterion matches 'Dark mode works'" in message
    assert "Given a session, when I star it, then it shows" in message
    assert "The header counts sessions" in message
    assert not routes["check"].called


def test_set_priority_toggles_star_and_label():
    with respx.mock:
        routes = mock_look(CARD, board_labels=[{"id": "lab-high", "name": "High severity"}])
        assert run(client().set_priority(CARD, True)) == {"id": CARD, "high": True}
        assert form(routes["add_sticker"].calls[0].request) == {
            "image": "star",
            "top": "-10",
            "left": "0",
            "zIndex": "2",
        }
        assert form(routes["add_label"].calls[0].request) == {"value": "lab-high"}
    with respx.mock:
        routes = mock_look(
            CARD,
            stickers=[{"id": "s9", "image": "star"}, {"id": "s1", "image": "check"}],
            card_labels=[{"id": "lab-high", "name": "High severity"}],
            board_labels=[{"id": "lab-high", "name": "High severity"}],
        )
        star = delete_route(f"/cards/{CARD}/stickers/s9")
        check = delete_route(f"/cards/{CARD}/stickers/s1")
        label = delete_route(f"/cards/{CARD}/idLabels/lab-high")
        assert run(client().set_priority(CARD, False)) == {"id": CARD, "high": False}
        assert star.called and label.called and not check.called
        assert not routes["add_sticker"].called


@respx.mock
def test_star_is_not_added_twice():
    routes = mock_look(CARD, stickers=[{"id": "s9", "image": "star"}])
    run(client().set_star(CARD, True))
    assert not routes["add_sticker"].called


def test_look_calls_refuse_ids_that_are_not_trello_ids():
    with pytest.raises(ToolError, match="not a Trello card id"):
        run(client().set_cover("../boards/x", "red"))


@respx.mock
def test_checklist_calls_explain_an_empty_or_missing_checklist():
    routes = mock_checklists()
    routes["list"].mock(return_value=httpx.Response(200, json=[]))
    c = client()
    with pytest.raises(ToolError, match="no Acceptance criteria checklist yet"):
        run(c.check_item(CARD, "Stars persist"))
    with pytest.raises(ToolError, match="at least one acceptance criterion"):
        run(c.add_checklist(CARD, ()))
    assert run(c.checklist_items(CARD)) == ()


@respx.mock
def test_blank_text_never_ticks_the_first_item():
    routes = mock_checklists()
    with pytest.raises(ToolError, match="No acceptance criterion matches"):
        run(client().check_item(CARD, "   "))
    assert not routes["check"].called


@respx.mock
def test_a_trello_reply_without_an_id_is_an_error_not_a_blank_call():
    routes = mock_look(CARD)
    routes["new_label"].mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(ToolError, match="Trello did not return an id for the new label"):
        run(client().add_label(CARD, "Spike"))
    assert not routes["add_label"].called
    mock_checklists()
    respx.post(f"{API}/cards/{CARD}/checklists").mock(return_value=httpx.Response(200, json={}))
    delete_route("/checklists/cl-old")
    with pytest.raises(ToolError, match="Trello did not return an id for the new checklist"):
        run(client().add_checklist(CARD, ("Stars persist",)))


@respx.mock
def test_malformed_board_labels_are_skipped():
    mock_look(CARD, board_labels=[{"name": "Bug"}, {"id": "s", "name": "Spike"}])
    assert run(client().board_labels()) == {"Spike": "s"}


@respx.mock
def test_check_item_refuses_an_ambiguous_prefix():
    routes = mock_checklists()
    items = [
        {"id": "i1", "name": "Stars persist after a reload", "state": "incomplete"},
        {"id": "i2", "name": "Stars show in the header", "state": "incomplete"},
        {"id": "i3", "name": "Stars", "state": "incomplete"},
    ]
    routes["list"].mock(
        return_value=httpx.Response(
            200, json=[{"id": "cl", "name": "Acceptance criteria", "checkItems": items[:2]}]
        )
    )
    with pytest.raises(ToolError) as caught:
        run(client().check_item(CARD, "stars"))
    message = str(caught.value)
    assert "2 acceptance criteria start with 'stars'" in message
    assert "'Stars persist after a reload'" in message and "'Stars show in the header'" in message
    assert "longer text" in message
    assert not routes["check"].called
    routes["list"].mock(
        return_value=httpx.Response(
            200, json=[{"id": "cl", "name": "Acceptance criteria", "checkItems": items}]
        )
    )
    assert run(client().check_item(CARD, "Stars"))["item"] == "Stars"
    assert routes["check"].calls[0].request.url.path.endswith("/checkItem/i3")


@respx.mock
def test_label_records_include_unnamed_labels_by_id():
    mock_look(
        CARD,
        board_labels=[
            {"id": "x", "name": "", "color": "red"},
            {"id": "b", "name": "Bug", "color": "red"},
            {"name": "no id", "color": "blue"},
        ],
    )
    assert run(client().label_records()) == {
        "x": {"name": "", "color": "red"},
        "b": {"name": "Bug", "color": "red"},
    }


@respx.mock
def test_rename_label_puts_the_new_name():
    route = respx.put(f"{API}/labels/lab-1").mock(return_value=httpx.Response(200, json={}))
    run(client().rename_label("lab-1", "Story"))
    assert form(route.calls[0].request) == {"name": "Story"}


@respx.mock
def test_card_look_reads_cover_full_description_and_every_label():
    text = "x" * 1500
    card = {
        "id": CARD,
        "idBoard": "board",
        "desc": text,
        "cover": {"color": "lime", "brightness": "dark"},
        "labels": [
            {"id": "a", "name": "Bug", "color": "red"},
            {"id": "b", "name": "", "color": "green"},
            {"id": "c"},
        ],
    }
    route = respx.get(f"{API}/cards/{CARD}").mock(return_value=httpx.Response(200, json=card))
    assert run(client().card_look(CARD)) == {
        "cover": "lime",
        "description": text,
        "labels": (
            {"name": "Bug", "color": "red"},
            {"name": "", "color": "green"},
            {"name": "", "color": None},
        ),
    }
    assert route.calls[0].request.url.params["fields"] == "idBoard,desc,cover,labels"
    route.mock(return_value=httpx.Response(200, json={"id": CARD, "idBoard": "board"}))
    assert run(client().card_look(CARD)) == {"cover": None, "description": "", "labels": ()}


@respx.mock
def test_card_look_refuses_labels_that_are_not_a_list():
    card = {"id": CARD, "idBoard": "board", "labels": {"name": "Bug"}}
    respx.get(f"{API}/cards/{CARD}").mock(return_value=httpx.Response(200, json=card))
    with pytest.raises(ToolError, match="labels"):
        run(client().card_look(CARD))


@respx.mock
def test_card_shows_its_label_names_and_acceptance_criteria():
    mock_lists()
    respx.get(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": CARD,
                "name": "Count the sessions",
                "idList": "l-testing",
                "idBoard": "board",
                "cover": {"color": "lime"},
                "labels": [
                    {"id": "a", "name": "Story", "color": "blue"},
                    {"id": "b", "name": "", "color": "green"},
                    {"id": "c", "name": "High severity", "color": "red"},
                ],
            },
        )
    )
    respx.get(f"{API}/cards/{CARD}/actions").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{API}/cards/{CARD}/checklists").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "x", "name": "Notes", "checkItems": [{"id": "n", "name": "skip"}]},
                {
                    "id": "k",
                    "name": "Acceptance criteria",
                    "checkItems": [
                        {"id": "i1", "name": "Shows the count", "state": "complete"},
                        {"id": "i2", "name": "Counts from data", "state": "incomplete"},
                    ],
                },
            ],
        )
    )
    card = run(client().card(CARD))
    assert card["list"] == "Testing"
    assert card["labels"] == ["Story", "High severity"]
    assert card["checklist"] == [
        {"text": "Shows the count", "state": "complete"},
        {"text": "Counts from data", "state": "incomplete"},
    ]
