from dataclasses import dataclass

import httpx
from fastmcp.exceptions import ToolError

from factory_tools.http import DEFAULT_TIMEOUT_S, json_or_error, request

API = "https://api.telegram.org"
SERVICE = "Telegram"
HINT = "Check TELEGRAM_BOT_TOKEN and that no other process polls this bot."
POLL_GRACE_S = 10


@dataclass(frozen=True)
class Message:
    update_id: int
    chat_id: int
    user_id: int
    first_name: str
    text: str
    date: int


def private_message(update: dict) -> Message | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or chat.get("type") != "private" or not isinstance(sender, dict):
        return None
    text = message.get("text")
    first_name = sender.get("first_name", "")
    numbers = (update.get("update_id"), chat.get("id"), sender.get("id"), message.get("date"))
    if not isinstance(text, str) or not text or not all(map(_whole, numbers)):
        return None
    update_id, chat_id, user_id, date = numbers
    name = first_name if isinstance(first_name, str) else ""
    return Message(update_id, chat_id, user_id, name, text, date)


@dataclass(frozen=True)
class TelegramBot:
    token: str
    http: httpx.AsyncClient

    async def get_updates(self, offset: int, timeout_s: int = 30) -> list[dict]:
        body = {"offset": offset, "timeout": timeout_s, "allowed_updates": ["message"]}
        response = await self._post("getUpdates", body, timeout_s + POLL_GRACE_S)
        return _updates(json_or_error(response, SERVICE, HINT))

    async def send(self, chat_id: int, text: str) -> None:
        await self._post("sendMessage", {"chat_id": chat_id, "text": text})

    async def _post(
        self, method: str, body: dict, timeout_s: float = DEFAULT_TIMEOUT_S
    ) -> httpx.Response:
        url = f"{API}/bot{self.token}/{method}"
        return await request(self.http, SERVICE, "POST", url, HINT, timeout_s=timeout_s, json=body)


def _updates(reply: dict | list) -> list[dict]:
    result = reply.get("result") if isinstance(reply, dict) else None
    if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
        raise ToolError(f"{SERVICE} sent a getUpdates reply without a result list. {HINT}")
    if not all(_whole(item.get("update_id")) for item in result):
        raise ToolError(f"{SERVICE} sent an update without a numeric update_id. {HINT}")
    return result


def _whole(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
