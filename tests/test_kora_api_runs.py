import json

import httpx
import pytest
import respx

from factory_demo import kora_api
from factory_demo.kora_api import KoraAuthError, KoraClient, client_from_token

BASE = "https://api.local.runkora.io"
EVENTS = f"{BASE}/api/v1/runs/r-1/events"


def client() -> KoraClient:
    return KoraClient(BASE, "tok")


def page(events: list[dict], next_seq: int, has_more: bool) -> httpx.Response:
    return httpx.Response(200, json={"events": events, "next_seq": next_seq, "has_more": has_more})


@respx.mock
def test_run_events_asks_for_json():
    route = respx.get(EVENTS).mock(return_value=page([{"sequence_no": 1}], 1, False))
    assert client().run_events("r-1") == [{"sequence_no": 1}]
    request = route.calls.last.request
    assert request.headers["Accept"] == "application/json"
    assert request.url.params["after_seq"] == "0"
    assert request.url.params["limit"] == "200"


@respx.mock
def test_run_events_pages_with_the_cursor_up_to_the_limit():
    route = respx.get(EVENTS).mock(
        side_effect=[
            page([{"sequence_no": n} for n in range(1, 201)], 200, True),
            page([{"sequence_no": n} for n in range(201, 251)], 250, False),
        ]
    )
    events = client().run_events("r-1", limit=400)
    assert [e["sequence_no"] for e in events] == list(range(1, 251))
    assert route.calls[1].request.url.params["after_seq"] == "200"
    assert route.calls[1].request.url.params["limit"] == "200"


@respx.mock
def test_run_events_stops_at_the_limit():
    route = respx.get(EVENTS).mock(
        return_value=page([{"sequence_no": 1}, {"sequence_no": 2}], 2, True)
    )
    assert len(client().run_events("r-1", limit=2)) == 2
    assert route.call_count == 1
    assert route.calls.last.request.url.params["limit"] == "2"


@respx.mock
def test_run_events_rejects_an_unexpected_shape():
    respx.get(EVENTS).mock(return_value=httpx.Response(200, json={"events": "nope"}))
    with pytest.raises(ValueError, match="run events"):
        client().run_events("r-1")


@respx.mock
def test_run_events_names_a_rejected_token():
    respx.get(EVENTS).mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(KoraAuthError):
        client().run_events("r-1")


@respx.mock
def test_create_token_posts_scopes_and_days():
    route = respx.post(f"{BASE}/api/v1/identity/tokens").mock(
        return_value=httpx.Response(
            201, json={"id": "p-1", "token": "kora_x", "expires_at": "2027-01-23T00:00:00Z"}
        )
    )
    scopes = ["trigger:t-1:fire", "triggers:read"]
    reply = client().create_token("ideas-bridge", scopes, 90)
    assert reply["token"] == "kora_x"
    assert json.loads(route.calls.last.request.content) == {
        "name": "ideas-bridge",
        "scopes": scopes,
        "expires_in_days": 90,
    }


def test_client_from_token_passes_the_token_through(monkeypatch):
    monkeypatch.setattr(kora_api, "default_ca_file", lambda: True)
    monkeypatch.delenv("KORA_API_URL", raising=False)
    kora = client_from_token("kora_abc")
    assert kora.base_url == BASE
    assert kora.http.headers["Authorization"] == "Bearer kora_abc"


def test_client_from_token_takes_the_url(monkeypatch):
    monkeypatch.setattr(kora_api, "default_ca_file", lambda: True)
    kora = client_from_token("t", base_url="https://kora.example/")
    assert kora.base_url == "https://kora.example"
