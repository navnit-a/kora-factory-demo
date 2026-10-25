import asyncio

import httpx
from fastmcp.exceptions import ToolError

TRUNCATE_NOTE = " (truncated)"
MAX_RETRY_AFTER_S = 5.0
BODY_PREVIEW_CHARS = 200
DEFAULT_TIMEOUT_S = 20.0


def truncate(text: str, limit: int = 1200) -> str:
    return text if len(text) <= limit else text[:limit] + TRUNCATE_NOTE


def upstream_error(service: str, response: httpx.Response, hint: str) -> ToolError:
    body = response.text[:BODY_PREVIEW_CHARS]
    message = f"{service} returned HTTP {response.status_code}: {body}."
    return ToolError(f"{message} {hint}".strip())


async def request(
    client: httpx.AsyncClient,
    service: str,
    method: str,
    url: str,
    hint: str,
    retry_429: bool = True,
    **kwargs,
) -> httpx.Response:
    response = await client.request(method, url, timeout=DEFAULT_TIMEOUT_S, **kwargs)
    if response.status_code == 429 and retry_429:
        await asyncio.sleep(_retry_after(response))
        return await request(client, service, method, url, hint, retry_429=False, **kwargs)
    if response.status_code == 429:
        wait = int(_retry_after(response, cap=None))
        raise ToolError(f"{service} is rate limiting; try again in {wait}s")
    if response.is_error:
        raise upstream_error(service, response, hint)
    return response


def _retry_after(response: httpx.Response, cap: float | None = MAX_RETRY_AFTER_S) -> float:
    try:
        seconds = float(response.headers.get("Retry-After", "1"))
    except ValueError:
        seconds = 1.0
    return seconds if cap is None else min(seconds, cap)
