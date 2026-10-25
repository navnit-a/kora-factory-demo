import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from factory_tools.transport import server
from factory_tools.transport.server import (
    ADD_INFO_URL,
    ATTRIBUTION,
    query_params,
    summarise_alerts,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "tfnsw_add_info.json").read_text())


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("TFNSW_API_KEY", "abc")


async def status() -> dict:
    async with Client(server.mcp) as client:
        return (await client.call_tool("transport_sydney_trains_status", {})).data


def run(coro):
    return asyncio.run(coro)


def test_summarise_alerts_lists_high_priority_lines_first():
    assert [e["line"] for e in summarise_alerts(FIXTURE)] == [
        "T1 North Shore & Western Line",
        "T2 Leppington & Inner West Line",
        "T9 Northern Line",
        "T4 Eastern Suburbs & Illawarra Line",
    ]


def test_summary_is_cut_at_200_characters():
    line = {"name": "T2", "product": {"class": 1}}
    info = {"type": "lineInfo", "subtitle": "s" * 300, "affected": {"lines": [line]}}
    payload = {"infos": {"current": [info]}}
    assert summarise_alerts(payload)[0]["summary"].endswith(" (truncated)")


@respx.mock
def test_status_reports_disruptions_with_the_api_key_header():
    route = respx.get(ADD_INFO_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    result = run(status())
    assert result["status"] == "disruptions"
    assert len(result["lines"]) == 4
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


def test_only_train_lines_count_and_the_network_prefix_is_dropped():
    lines = [entry["line"] for entry in summarise_alerts(FIXTURE)]
    assert "Hornsby to Berowra replacement bus" not in lines
    assert all(not name.startswith("Sydney Trains Network") for name in lines)


def test_query_asks_for_today_in_sydney_not_a_flag():
    from datetime import UTC, datetime

    params = query_params(datetime(2026, 10, 27, 20, 30, tzinfo=UTC))
    assert params["filterDateValid"] == "28-10-2026"
    assert params["filterMOTType"] == "1"


def test_summaries_are_capped_per_line_and_overall():
    def info(n):
        return {
            "type": "lineInfo",
            "subtitle": f"Change {n}",
            "affected": {"lines": [{"name": f"T{n % 30}", "product": {"class": 1}}]},
        }

    payload = {"infos": {"current": [info(n) for n in range(120)]}}
    entries = summarise_alerts(payload)
    assert len(entries) == 20
    per_line = {}
    for entry in entries:
        per_line[entry["line"]] = per_line.get(entry["line"], 0) + 1
    assert max(per_line.values()) <= 3


@respx.mock
def test_status_says_how_many_alerts_were_left_out():
    def info(n):
        return {
            "type": "lineInfo",
            "subtitle": f"Change {n}",
            "affected": {"lines": [{"name": f"T{n}", "product": {"class": 1}}]},
        }

    respx.get(ADD_INFO_URL).mock(
        return_value=httpx.Response(200, json={"infos": {"current": [info(n) for n in range(25)]}})
    )
    result = run(status())
    assert len(result["lines"]) == 20
    assert result["more"] == 5


def test_high_priority_sydney_trains_come_before_intercity_notices():
    def info(priority, line, text):
        return {
            "type": "lineInfo",
            "priority": priority,
            "subtitle": text,
            "affected": {"lines": [{"name": line, "product": {"class": 1}}]},
        }

    payload = {
        "infos": {
            "current": [
                info(
                    "normal",
                    "Intercity Trains Network Blue Mountains Line",
                    "Opal top up unavailable",
                ),
                info(
                    "normal",
                    "Sydney Trains Network T2 Leppington & Inner West Line",
                    "Running late",
                ),
                info("high", "Sydney Trains Network T8 Airport & South Line", "Trains not running"),
            ]
        }
    }
    entries = summarise_alerts(payload)
    assert [e["line"] for e in entries] == [
        "T8 Airport & South Line",
        "T2 Leppington & Inner West Line",
        "Blue Mountains Line",
    ]


def test_single_trip_notices_are_left_out_unless_high_priority():
    summaries = [e["summary"] for e in summarise_alerts(FIXTURE)]
    assert "Running late" not in summaries
    assert "Major delay: signal fault at Strathfield" in summaries
