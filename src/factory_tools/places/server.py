import asyncio
from math import asin, cos, radians, sin, sqrt
from typing import Annotated

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from factory_tools.http import json_or_error, request
from factory_tools.places.cache import cache_key, read_cached, write_cached

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
ATTRIBUTION = "Data: OpenStreetMap contributors, ODbL"
USER_AGENT = "kora-factory-demo (platformcon day planner)"
EARTH_RADIUS_M = 6_371_000
MAX_CANDIDATES = 200
OVERPASS_QUERY_TIMEOUT_S = 50
OVERPASS_CLIENT_TIMEOUT_S = 60.0
RETRY_DELAYS_S = (5, 15)
TOTAL_BUDGET_S = 90.0
MIN_ATTEMPT_S = 5.0
OVERPASS_HINT = "Overpass did not answer in time: retry in a minute or use a smaller radius."
ALL_FAILED = f"Every Overpass instance failed. {OVERPASS_HINT}"
SERVER_ERROR = "Overpass returned HTTP 5"
UNAVAILABLE_PREFIXES = (
    "Overpass did not answer in time",
    "Overpass could not be reached",
    "Overpass is rate limiting",
    SERVER_ERROR,
)
READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)

mcp = FastMCP(
    "places",
    instructions="Named cafes and restaurants near a point, nearest first, from OpenStreetMap.",
)


@mcp.tool(
    annotations=READ,
    description="Named cafes and restaurants near a point, nearest first, with kind, "
    "cuisine and street.",
)
async def places_lunch_nearby(
    latitude: Annotated[float, Field(ge=-90, le=90, description="Latitude of the starting point.")],
    longitude: Annotated[
        float, Field(ge=-180, le=180, description="Longitude of the starting point.")
    ],
    radius_m: Annotated[
        int, Field(ge=100, le=2000, description="Search radius in metres, walking distance.")
    ] = 600,
    limit: Annotated[int, Field(ge=1, le=10, description="How many places to return.")] = 3,
) -> dict:
    query = (
        f'[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];(node["amenity"~"cafe|restaurant"]["name"]'
        f"(around:{radius_m},{latitude},{longitude}););out {MAX_CANDIDATES};"
    )
    key = cache_key(latitude, longitude, radius_m, limit)
    try:
        payload = await _overpass(query)
    except ToolError:
        cached = read_cached(key)
        if cached is None:
            raise
        return cached
    places = rank_places(payload.get("elements", []), latitude, longitude, limit)
    if not places:
        raise ToolError(
            f"There are no cafes or restaurants within {radius_m} m; try a larger radius."
        )
    result = {"places": places, "searched_radius_m": radius_m, "attribution": ATTRIBUTION}
    write_cached(key, result)
    return result


class InstanceUnavailable(Exception):
    pass


async def _overpass(query: str) -> dict:
    deadline = _clock() + TOTAL_BUDGET_S
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as http:
        for url in OVERPASS_URLS:
            try:
                return await _from_instance(http, url, query, deadline)
            except InstanceUnavailable:
                continue
    raise ToolError(ALL_FAILED)


async def _from_instance(http: httpx.AsyncClient, url: str, query: str, deadline: float) -> dict:
    response = await _post_with_retries(http, url, query, deadline, RETRY_DELAYS_S)
    try:
        payload = json_or_error(response, "Overpass", OVERPASS_HINT)
    except ToolError as error:
        raise InstanceUnavailable(str(error)) from error
    if "runtime error" in str(payload.get("remark", "")):
        raise InstanceUnavailable(OVERPASS_HINT)
    return payload


async def _post_with_retries(
    http: httpx.AsyncClient, url: str, query: str, deadline: float, delays: tuple[float, ...]
) -> httpx.Response:
    try:
        return await _post(http, url, query, deadline)
    except ToolError as error:
        if not _is_unavailable(error):
            raise
        if not _may_retry(error, delays, deadline):
            raise InstanceUnavailable(str(error)) from error
    await asyncio.sleep(delays[0])
    return await _post_with_retries(http, url, query, deadline, delays[1:])


async def _post(http: httpx.AsyncClient, url: str, query: str, deadline: float) -> httpx.Response:
    remaining = deadline - _clock()
    if remaining < MIN_ATTEMPT_S:
        raise InstanceUnavailable(OVERPASS_HINT)
    return await request(
        http,
        "Overpass",
        "POST",
        url,
        hint=OVERPASS_HINT,
        retry_429=False,
        timeout_s=min(OVERPASS_CLIENT_TIMEOUT_S, remaining),
        data={"data": query},
    )


def _is_unavailable(error: ToolError) -> bool:
    return str(error).startswith(UNAVAILABLE_PREFIXES)


def _may_retry(error: ToolError, delays: tuple[float, ...], deadline: float) -> bool:
    if not delays or not str(error).startswith(SERVER_ERROR):
        return False
    return deadline - _clock() >= delays[0] + MIN_ATTEMPT_S


def _clock() -> float:
    return asyncio.get_running_loop().time()


def rank_places(elements: list[dict], lat: float, lon: float, limit: int) -> list[dict]:
    named = [e for e in elements if e.get("tags", {}).get("name")]
    places = [_place(e, lat, lon) for e in named]
    return sorted(places, key=lambda p: p["distance_m"])[:limit]


def _place(element: dict, lat: float, lon: float) -> dict:
    tags = element.get("tags", {})
    return {
        "name": tags["name"],
        "kind": tags.get("amenity", ""),
        "cuisine": tags.get("cuisine", ""),
        "distance_m": round(_haversine_m(lat, lon, element["lat"], element["lon"])),
        "street": tags.get("addr:street", ""),
        "lat": element["lat"],
        "lon": element["lon"],
    }


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))
