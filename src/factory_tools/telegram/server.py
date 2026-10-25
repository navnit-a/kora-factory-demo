import os
from typing import Annotated

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from factory_tools.http import json_or_error, request

API = "https://api.telegram.org"
MAX_TEXT = 4096
TRUNCATED_SUFFIX = "\n…(truncated)"
ENV_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL")
WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)

mcp = FastMCP(
    "telegram",
    instructions=(
        "Posts to the kora factory Telegram channel that the whole team and the household read. "
        "Keep posts short and plain; one post per event."
    ),
)


@mcp.tool(
    annotations=WRITE,
    description="Post one message to the factory's Telegram channel and return its id and link.",
)
async def telegram_send_message(
    text: Annotated[
        str,
        Field(min_length=1, description="The message, plain text, up to 4,096 characters."),
    ],
) -> dict:
    settings = _settings()
    body = {"chat_id": settings["TELEGRAM_CHAT_ID"], "text": _fit(text)}
    async with httpx.AsyncClient() as http:
        response = await request(
            http,
            "Telegram",
            "POST",
            f"{API}/bot{settings['TELEGRAM_BOT_TOKEN']}/sendMessage",
            hint="",
            retry_429=True,
            data=body,
        )
    reply = json_or_error(response, "Telegram", "Try again in a minute.")
    message_id = reply.get("result", {}).get("message_id", 0)
    channel = settings["TELEGRAM_CHANNEL"].lstrip("@")
    return {"message_id": message_id, "url": f"https://t.me/{channel}/{message_id}"}


def _settings() -> dict[str, str]:
    values = {name: os.environ.get(name, "") for name in ENV_KEYS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ToolError(f"Telegram is not configured: set {', '.join(missing)}")
    return values


def _fit(text: str) -> str:
    if len(text) <= MAX_TEXT:
        return text
    return text[: MAX_TEXT - len(TRUNCATED_SUFFIX)] + TRUNCATED_SUFFIX
