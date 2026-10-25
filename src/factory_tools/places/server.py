from math import asin, cos, radians, sin, sqrt
from typing import Annotated

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from factory_tools.http import json_or_error, request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ATTRIBUTION = "Data: OpenStreetMap contributors, ODbL"
USER_AGENT = "kora-factory-demo (platformcon day planner)"
EARTH_RADIUS_M = 6_371_000
MAX_CANDIDATES = 200
OVERPASS_QUERY_TIMEOUT_S = 50
OVERPASS_CLIENT_TIMEOUT_S = 60.0
OVERPASS_HINT = "Overpass did not answer in time: retry in a minute or use a smaller radius."
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
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as http:
        response = await request(
            http,
            "Overpass",
            "POST",
            OVERPASS_URL,
            hint=OVERPASS_HINT,
            timeout_s=OVERPASS_CLIENT_TIMEOUT_S,
            data={"data": query},
        )
    payload = json_or_error(response, "Overpass", OVERPASS_HINT)
    if "runtime error" in str(payload.get("remark", "")):
        raise ToolError(OVERPASS_HINT)
    places = rank_places(payload.get("elements", []), latitude, longitude, limit)
    if not places:
        raise ToolError(
            f"There are no cafes or restaurants within {radius_m} m; try a larger radius."
        )
    return {"places": places, "searched_radius_m": radius_m, "attribution": ATTRIBUTION}


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
    }


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))
