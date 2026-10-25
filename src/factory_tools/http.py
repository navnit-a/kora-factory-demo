import asyncio

import httpx
from fastmcp.exceptions import ToolError

TRUNCATE_NOTE = " (truncated)"
MAX_RETRY_AFTER_S = 5.0
BODY_PREVIEW_CHARS = 200
DEFAULT_TIMEOUT_S = 35.0


def truncate(text: str, limit: int = 1200) -> str:
    return text if len(text) <= limit else text[:limit] + TRUNCATE_NOTE


def upstream_error(service: str, response: httpx.Response, hint: str) -> ToolError:
    body = response.text[:BODY_PREVIEW_CHARS]
    message = f"{service} returned HTTP {response.status_code}: {body}."
    return ToolError(f"{message} {hint}".strip())


def json_or_error(response: httpx.Response, service: str, hint: str) -> dict | list:
    try:
        return response.json()
    except ValueError as error:
        raise ToolError(f"{service} sent a reply that is not JSON. {hint}".strip()) from error


async def request(
    client: httpx.AsyncClient,
    service: str,
    method: str,
    url: str,
    hint: str,
    retry_429: bool = True,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    **kwargs,
) -> httpx.Response:
    response = await _send(client, service, method, url, hint, timeout_s, **kwargs)
    if response.status_code == 429 and retry_429:
        await asyncio.sleep(_retry_after(response))
        return await request(
            client, service, method, url, hint, retry_429=False, timeout_s=timeout_s, **kwargs
        )
    if response.status_code == 429:
        wait = int(_retry_after(response, cap=None))
        raise ToolError(f"{service} is rate limiting; try again in {wait}s")
    if response.is_error:
        raise upstream_error(service, response, hint)
    return response


async def _send(
    client: httpx.AsyncClient,
    service: str,
    method: str,
    url: str,
    hint: str,
    timeout_s: float,
    **kwargs,
) -> httpx.Response:
    try:
        return await client.request(method, url, timeout=timeout_s, **kwargs)
    except httpx.TimeoutException as error:
        raise ToolError(f"{service} did not answer in time. {hint}".strip()) from error
    except httpx.TransportError as error:
        raise ToolError(f"{service} could not be reached ({error}). {hint}".strip()) from error


def _retry_after(response: httpx.Response, cap: float | None = MAX_RETRY_AFTER_S) -> float:
    try:
        seconds = float(response.headers.get("Retry-After", "1"))
    except ValueError:
        seconds = 1.0
    return seconds if cap is None else min(seconds, cap)
