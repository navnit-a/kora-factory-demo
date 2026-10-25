import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import httpx
from fastmcp.exceptions import ToolError

from factory_bridge import pending, rate_limit, replies
from factory_bridge.allowlist import read_allowlist
from factory_bridge.card_text import card_description, card_title
from factory_bridge.commands import Decision, Idea, idea_text_ok, parse_command, proposer_name
from factory_bridge.kora_runs import ScoutRunner
from factory_bridge.pending import Proposal
from factory_bridge.scout_result import parse_scout
from factory_bridge.telegram_api import Message, TelegramBot, private_message
from factory_demo.kora_api import KoraAuthError

log = logging.getLogger("factory_bridge")
RETRY_S = 5.0
PROPOSED_LABEL = "Proposed via Telegram"
SCOUT_ERRORS = (TimeoutError, RuntimeError, ValueError, httpx.HTTPError, KoraAuthError)


@dataclass(frozen=True)
class State:
    offset: int
    pending: dict[int, Proposal]
    history: dict[int, tuple[float, ...]]


@dataclass(frozen=True)
class Bridge:
    bot: TelegramBot
    runner: ScoutRunner
    create_card: Callable[[str, str], Awaitable[dict]]
    label_card: Callable[[str, str], Awaitable[dict]]
    allowlist_path: Path
    clock: Callable[[], float]
    started_at: int

    async def handle(self, state: State, message: Message) -> State:
        if message.date < self.started_at:
            return state
        if not self._allowed(message.user_id):
            await self._refuse(message)
            return state
        command = parse_command(message.text)
        if isinstance(command, Idea) and not idea_text_ok(command.text):
            await self._reply(message, replies.bad_text())
            return state
        if isinstance(command, Idea):
            return await self._on_idea(state, message, command.text)
        if isinstance(command, Decision):
            return await self._on_decision(state, message, command.yes)
        await self._reply(message, replies.bad_text())
        return state

    async def step(self, state: State) -> State:
        current = state
        for update in await self.bot.get_updates(state.offset):
            current = await self._update(current, update)
        return current

    async def run_forever(self, state: State) -> None:
        current = state
        while True:
            current = await self._step_or_wait(current)

    async def _step_or_wait(self, state: State) -> State:
        try:
            return await self.step(state)
        except ToolError as error:
            log.error("polling Telegram failed: %s", error)
        except Exception:
            log.exception("poll at offset %s failed unexpectedly", state.offset)
        await asyncio.sleep(RETRY_S)
        return state

    async def _update(self, state: State, update: dict) -> State:
        advanced = replace(state, offset=max(state.offset, update["update_id"] + 1))
        message = private_message(update)
        if message is None:
            return advanced
        try:
            return await self.handle(advanced, message)
        except ToolError as error:
            log.error(
                "update %s from user_id=%s failed: %s", update["update_id"], message.user_id, error
            )
            return advanced
        except Exception:
            log.exception("update %s from user_id=%s broke", update["update_id"], message.user_id)
            await self._tell_it_broke(message)
            return advanced

    async def _tell_it_broke(self, message: Message) -> None:
        try:
            await self.bot.send(message.chat_id, replies.scout_failed())
        except ToolError as error:
            log.error("could not tell user_id=%s it broke: %s", message.user_id, error)

    async def _on_idea(self, state: State, message: Message, idea: str) -> State:
        now = self.clock()
        history = state.history.get(message.user_id, ())
        if not rate_limit.allowed(history, now):
            until = datetime.fromtimestamp(rate_limit.retry_at(history, now)).strftime("%H:%M")
            await self._reply(message, replies.rate_limited(until))
            return state
        counted = {**state.history, message.user_id: rate_limit.record(history, now)}
        recorded = replace(state, history=counted)
        await self._reply(message, replies.ack())
        name = proposer_name(message.first_name)
        try:
            result = parse_scout(await asyncio.to_thread(self.runner.run, idea, name))
        except SCOUT_ERRORS as error:
            log.warning("scout failed for user_id=%s: %s", message.user_id, error)
            await self._reply(message, replies.scout_failed())
            return recorded
        proposal = Proposal(
            message.user_id, message.chat_id, message.first_name, idea, result, self.clock()
        )
        await self._reply(message, replies.proposal(result))
        return replace(recorded, pending=pending.put(recorded.pending, proposal))

    async def _on_decision(self, state: State, message: Message, yes: bool) -> State:
        proposal, rest = pending.take(state.pending, message.user_id, self.clock())
        if proposal is None:
            await self._reply(message, replies.nothing_pending())
            return replace(state, pending=rest)
        if not yes:
            await self._reply(message, replies.dropped())
            return replace(state, pending=rest)
        if proposal.result.verdict == "not_buildable":
            await self._reply(message, replies.not_buildable_yes())
            return state
        title = card_title(proposal.result)
        description = card_description(proposal.result, proposal.first_name)
        try:
            card = await self.create_card(title, description)
        except ToolError as error:
            log.error("card for user_id=%s not created: %s", message.user_id, error)
            await self._reply(message, replies.card_failed())
            return state
        await self._label(card.get("id", ""), message.user_id)
        log.info("card %s created for user_id=%s", card.get("id", ""), message.user_id)
        cleared = replace(state, pending=rest)
        try:
            await self._reply(message, replies.added(card.get("url", "")))
        except ToolError as error:
            log.error("card %s created but the reply failed: %s", card.get("id", ""), error)
        return cleared

    async def _label(self, card_id: str, user_id: int) -> None:
        try:
            await self.label_card(card_id, PROPOSED_LABEL)
        except ToolError as error:
            log.error("card %s for user_id=%s not labelled: %s", card_id, user_id, error)

    def _allowed(self, user_id: int) -> bool:
        try:
            return user_id in read_allowlist(self.allowlist_path)
        except (OSError, ValueError) as error:
            log.error("allowlist unreadable, refusing user_id=%s: %s", user_id, error)
            return False

    async def _refuse(self, message: Message) -> None:
        name = " ".join(message.first_name.split())
        log.info("refused user_id=%s first_name=%s", message.user_id, name)
        await self._reply(message, replies.refused(message.user_id))

    async def _reply(self, message: Message, text: str) -> None:
        await self.bot.send(message.chat_id, text)


async def scout_once(runner: ScoutRunner, idea: str, from_name: str) -> str:
    answer = await asyncio.to_thread(runner.run, idea, proposer_name(from_name))
    return replies.proposal(parse_scout(answer))
