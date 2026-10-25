import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from factory_tools.http import request, truncate

ADD_INFO_URL = "https://api.transport.nsw.gov.au/v1/tp/add_info"
ATTRIBUTION = "Data: Transport for NSW Open Data, CC BY 4.0"
SYDNEY = ZoneInfo("Australia/Sydney")
TRAIN_CLASS = 1
METRO_NETWORK = "Sydney Trains Network "
NETWORK_PREFIXES = (METRO_NETWORK, "Intercity Trains Network ")
PRIORITY_RANK = {"veryHigh": 0, "high": 1, "normal": 2, "low": 3, "veryLow": 4}
LINE_DISRUPTION = "lineInfo"
URGENT = frozenset({"veryHigh", "high"})
SUMMARY_LIMIT = 200
PER_LINE_LIMIT = 3
TOTAL_LIMIT = 20
KEY_HINT = "Check TFNSW_API_KEY: it is missing, expired or lacks the Trip Planner APIs."
READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)

mcp = FastMCP(
    "transport",
    instructions="Current Sydney Trains disruptions from Transport for NSW, grouped by line.",
)


@mcp.tool(annotations=READ)
async def transport_sydney_trains_status() -> dict:
    """Current Sydney Trains disruptions, up to three per line and twenty in all, or normal."""
    key = os.environ.get("TFNSW_API_KEY", "")
    if not key:
        raise ToolError("Sydney transport is not configured: set TFNSW_API_KEY")
    now = datetime.now(UTC)
    async with httpx.AsyncClient() as http:
        response = await _fetch(http, key, query_params(now))
    every = _pairs(response.json())
    lines = _capped(every)
    return {
        "status": "disruptions" if lines else "normal",
        "lines": lines,
        "more": len(every) - len(lines),
        "as_of": now.isoformat(timespec="seconds"),
        "attribution": ATTRIBUTION,
    }


def query_params(now: datetime) -> dict[str, str]:
    today = now.astimezone(SYDNEY).strftime("%d-%m-%Y")
    return {"outputFormat": "rapidJSON", "filterDateValid": today, "filterMOTType": "1"}


def summarise_alerts(payload: dict) -> list[dict]:
    return _capped(_pairs(payload))


def _pairs(payload: dict) -> list[dict]:
    current = payload.get("infos", {}).get("current", [])
    ranked = {
        (_rank(info, line), _line_name(line), _summary(info))
        for info in current
        if _relevant(info)
        for line in info.get("affected", {}).get("lines", [])
        if line.get("name") and line.get("product", {}).get("class") == TRAIN_CLASS
    }
    ordered = sorted(ranked)
    unique = list(dict.fromkeys((name, summary) for _, name, summary in ordered))
    return [{"line": name, "summary": summary} for name, summary in unique]


def _relevant(info: dict) -> bool:
    return info.get("type") == LINE_DISRUPTION or info.get("priority") in URGENT


def _rank(info: dict, line: dict) -> tuple[int, int]:
    priority = PRIORITY_RANK.get(info.get("priority", "normal"), 2)
    network = 0 if line["name"].startswith(METRO_NETWORK) else 1
    return priority, network


def _capped(entries: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    kept = []
    for entry in entries:
        count = seen.get(entry["line"], 0)
        if count < PER_LINE_LIMIT and len(kept) < TOTAL_LIMIT:
            kept = [*kept, entry]
            seen = {**seen, entry["line"]: count + 1}
    return kept


async def _fetch(http: httpx.AsyncClient, key: str, params: dict) -> httpx.Response:
    headers = {"Authorization": f"apikey {key}"}
    try:
        return await request(
            http, "Transport for NSW", "GET", ADD_INFO_URL, hint="", params=params, headers=headers
        )
    except ToolError as error:
        if "HTTP 401" in str(error) or "HTTP 403" in str(error):
            raise ToolError(f"{error} {KEY_HINT}") from error
        raise


def _line_name(line: dict) -> str:
    name = line["name"]
    for prefix in NETWORK_PREFIXES:
        name = name.removeprefix(prefix)
    return name


def _summary(info: dict) -> str:
    text = info.get("subtitle") or info.get("urlText") or "Service change"
    return truncate(text, SUMMARY_LIMIT)
