import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from factory_tools.transport import server
from factory_tools.transport.server import ADD_INFO_URL, ATTRIBUTION, summarise_alerts

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "tfnsw_add_info.json").read_text())


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("TFNSW_API_KEY", "abc")


async def status() -> dict:
    async with Client(server.mcp) as client:
        return (await client.call_tool("transport_sydney_trains_status", {})).data


def run(coro):
    return asyncio.run(coro)


def test_summarise_alerts_groups_by_line_sorted():
    assert summarise_alerts(FIXTURE) == [
        {
            "line": "T1 North Shore & Western Line",
            "summary": "Buses replace trains between Hornsby and Berowra",
        },
        {
            "line": "T4 Eastern Suburbs & Illawarra Line",
            "summary": "Allow extra travel time on the T4 Line",
        },
        {"line": "T9 Northern Line", "summary": "Buses replace trains between Hornsby and Berowra"},
    ]


def test_summary_is_cut_at_200_characters():
    payload = {
        "infos": {"current": [{"subtitle": "s" * 300, "affected": {"lines": [{"name": "T2"}]}}]}
    }
    assert summarise_alerts(payload)[0]["summary"].endswith(" (truncated)")


@respx.mock
def test_status_reports_disruptions_with_the_api_key_header():
    route = respx.get(ADD_INFO_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    result = run(status())
    assert result["status"] == "disruptions"
    assert len(result["lines"]) == 3
    assert result["attribution"] == ATTRIBUTION
    assert route.calls[0].request.headers["authorization"] == "apikey abc"
    assert route.calls[0].request.url.params["filterMOTType"] == "1"


@respx.mock
def test_status_is_normal_when_no_current_alerts():
    respx.get(ADD_INFO_URL).mock(return_value=httpx.Response(200, json={"infos": {"current": []}}))
    result = run(status())
    assert result["status"] == "normal" and result["lines"] == []
    assert result["attribution"] == "Data: Transport for NSW Open Data, CC BY 4.0"


@respx.mock
def test_401_names_the_api_key():
    respx.get(ADD_INFO_URL).mock(return_value=httpx.Response(401, text="unauthorised"))
    with pytest.raises(ToolError, match="TFNSW_API_KEY"):
        run(status())


def test_missing_key_is_a_clear_tool_error_before_any_call(monkeypatch):
    monkeypatch.delenv("TFNSW_API_KEY")
    with pytest.raises(ToolError, match="TFNSW_API_KEY"):
        run(status())


def test_tool_is_read_only():
    async def listed():
        async with Client(server.mcp) as client:
            return (await client.list_tools())[0]

    tool = run(listed())
    assert tool.name == "transport_sydney_trains_status"
    assert tool.annotations.read_only_hint is True
