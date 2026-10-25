import os
from datetime import UTC, datetime

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from factory_tools.http import request, truncate

ADD_INFO_URL = "https://api.transport.nsw.gov.au/v1/tp/add_info"
ADD_INFO_PARAMS = {"outputFormat": "rapidJSON", "filterDateValid": "1", "filterMOTType": "1"}
ATTRIBUTION = "Data: Transport for NSW Open Data, CC BY 4.0"
SUMMARY_LIMIT = 200
KEY_HINT = "Check TFNSW_API_KEY: it is missing, expired or lacks the Trip Planner APIs."
READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)

mcp = FastMCP(
    "transport",
    instructions="Current Sydney Trains disruptions from Transport for NSW, grouped by line.",
)


@mcp.tool(annotations=READ)
async def transport_sydney_trains_status() -> dict:
    """Current Sydney Trains disruptions, one entry per affected line, or status normal if none."""
    key = os.environ.get("TFNSW_API_KEY", "")
    if not key:
        raise ToolError("Sydney transport is not configured: set TFNSW_API_KEY")
    async with httpx.AsyncClient() as http:
        response = await _fetch(http, key)
    lines = summarise_alerts(response.json())
    return {
        "status": "disruptions" if lines else "normal",
        "lines": lines,
        "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        "attribution": ATTRIBUTION,
    }


def summarise_alerts(payload: dict) -> list[dict]:
    current = payload.get("infos", {}).get("current", [])
    pairs = {
        (line["name"], _summary(info))
        for info in current
        for line in info.get("affected", {}).get("lines", [])
        if line.get("name")
    }
    return [{"line": name, "summary": summary} for name, summary in sorted(pairs)]


async def _fetch(http: httpx.AsyncClient, key: str) -> httpx.Response:
    headers = {"Authorization": f"apikey {key}"}
    try:
        return await request(
            http,
            "Transport for NSW",
            "GET",
            ADD_INFO_URL,
            hint="",
            params=ADD_INFO_PARAMS,
            headers=headers,
        )
    except ToolError as error:
        if "HTTP 401" in str(error) or "HTTP 403" in str(error):
            raise ToolError(f"{error} {KEY_HINT}") from error
        raise


def _summary(info: dict) -> str:
    text = info.get("subtitle") or info.get("urlText") or "Service change"
    return truncate(text, SUMMARY_LIMIT)
