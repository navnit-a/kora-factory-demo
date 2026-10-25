import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from factory_tools.places import server
from factory_tools.places.server import ATTRIBUTION, OVERPASS_URL, rank_places

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "overpass_lunch.json").read_text())
VENUE = (-33.8776, 151.2048)


async def lunch(**arguments) -> dict:
    async with Client(server.mcp) as client:
        return (await client.call_tool("places_lunch_nearby", arguments)).data


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PLACES_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(server, "RETRY_DELAYS_S", (0, 0))


def test_rank_places_sorts_by_distance_and_limits():
    places = rank_places(FIXTURE["elements"], *VENUE, limit=3)
    assert [p["name"] for p in places] == ["Corner Cafe", "Harbour Noodle", "Spice Lane"]
    assert places[0] == {
        "name": "Corner Cafe",
        "kind": "cafe",
        "cuisine": "",
        "distance_m": 35,
        "street": "Goulburn Street",
    }
    assert places[2]["cuisine"] == "thai"


def test_rank_skips_nodes_without_a_name():
    names = [p["name"] for p in rank_places(FIXTURE["elements"], *VENUE, limit=10)]
    assert len(names) == 4 and "" not in names


@respx.mock
def test_tool_queries_overpass_around_the_point_and_attributes_osm():
    route = respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    result = run(lunch(latitude=VENUE[0], longitude=VENUE[1]))
    assert [p["name"] for p in result["places"]] == ["Corner Cafe", "Harbour Noodle", "Spice Lane"]
    assert result["searched_radius_m"] == 600
    assert result["attribution"] == ATTRIBUTION == "Data: OpenStreetMap contributors, ODbL"
    query = dict(httpx.QueryParams(route.calls[0].request.content.decode()))["data"]
    assert "around:600,-33.8776,151.2048" in query
    assert query.endswith("out 200;")
    assert route.calls[0].request.headers["user-agent"].startswith("kora-factory-demo")


@respx.mock
def test_empty_result_says_nothing_within_radius():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
    with pytest.raises(ToolError, match="no cafes or restaurants within 600 m"):
        run(lunch(latitude=VENUE[0], longitude=VENUE[1]))


@respx.mock
def test_overpass_504_suggests_retry_or_smaller_radius():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(504, text="gateway timeout"))
    with pytest.raises(ToolError, match="retry in a minute or use a smaller radius"):
        run(lunch(latitude=VENUE[0], longitude=VENUE[1]))


def test_latitude_out_of_range_is_rejected():
    with pytest.raises(ToolError):
        run(lunch(latitude=91.0, longitude=151.2))


def test_tool_is_read_only():
    async def listed():
        async with Client(server.mcp) as client:
            return (await client.list_tools())[0]

    tool = run(listed())
    assert tool.name == "places_lunch_nearby"
    assert tool.annotations.read_only_hint is True


@respx.mock
def test_overpass_runtime_error_remark_is_a_retry_hint_not_no_places():
    respx.post(OVERPASS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"elements": [], "remark": "runtime error: Query timed out in 'query' at line 1"},
        )
    )
    with pytest.raises(ToolError, match="retry in a minute or use a smaller radius"):
        run(lunch(latitude=VENUE[0], longitude=VENUE[1]))


@respx.mock
def test_client_timeout_is_a_tool_error_with_the_hint():
    respx.post(OVERPASS_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ToolError, match="Overpass did not answer in time"):
        run(lunch(latitude=VENUE[0], longitude=VENUE[1]))


@respx.mock
def test_slow_overpass_gets_a_minute():
    route = respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    run(lunch(latitude=VENUE[0], longitude=VENUE[1]))
    query = dict(httpx.QueryParams(route.calls[0].request.content.decode()))["data"]
    assert query.startswith("[out:json][timeout:50];")
    timeout = route.calls[0].request.extensions["timeout"]
    assert timeout["read"] == 60.0


@respx.mock
def test_overpass_at_capacity_is_retried_then_answers():
    route = respx.post(OVERPASS_URL).mock(
        side_effect=[
            httpx.Response(502, text="server is currently at capacity"),
            httpx.Response(200, json=FIXTURE),
        ]
    )
    result = run(lunch(latitude=VENUE[0], longitude=VENUE[1]))
    assert route.call_count == 2
    assert "cached_at" not in result
    assert result["places"][0]["name"] == "Corner Cafe"


@respx.mock
def test_last_good_answer_is_served_when_overpass_stays_down():
    respx.post(OVERPASS_URL).mock(
        side_effect=[httpx.Response(200, json=FIXTURE), *[httpx.Response(502, text="busy")] * 3]
    )
    fresh = run(lunch(latitude=VENUE[0], longitude=VENUE[1]))
    cached = run(lunch(latitude=VENUE[0], longitude=VENUE[1]))
    assert cached["places"] == fresh["places"]
    assert cached["cached_at"]
    assert cached["attribution"] == ATTRIBUTION


@respx.mock
def test_without_a_cached_answer_overpass_down_is_a_retry_hint():
    route = respx.post(OVERPASS_URL).mock(return_value=httpx.Response(502, text="busy"))
    with pytest.raises(ToolError, match="retry in a minute"):
        run(lunch(latitude=VENUE[0], longitude=VENUE[1]))
    assert route.call_count == 3


@respx.mock
def test_a_cached_answer_is_only_for_the_same_point_and_radius():
    respx.post(OVERPASS_URL).mock(
        side_effect=[httpx.Response(200, json=FIXTURE), *[httpx.Response(502, text="busy")] * 3]
    )
    run(lunch(latitude=VENUE[0], longitude=VENUE[1]))
    with pytest.raises(ToolError):
        run(lunch(latitude=VENUE[0], longitude=VENUE[1], radius_m=900))
