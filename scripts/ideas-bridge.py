import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factory_bridge.commands import idea_text_ok  # noqa: E402
from factory_bridge.kora_runs import ScoutRunner  # noqa: E402
from factory_bridge.replies import bad_text  # noqa: E402
from factory_bridge.service import Bridge, State, scout_once  # noqa: E402
from factory_bridge.telegram_api import TelegramBot  # noqa: E402
from factory_demo.kora_api import client_from_token  # noqa: E402
from factory_tools.trello.client import TrelloClient  # noqa: E402

ALLOWLIST = ROOT / "deploy/generated/ideas-allowlist"
IDEAS_LIST = "Ideas"
KORA_KEYS = ("KORA_BRIDGE_TOKEN", "KORA_SCOUT_TRIGGER_ID")
BRIDGE_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    *KORA_KEYS,
    "TRELLO_API_KEY",
    "TRELLO_TOKEN",
    "TRELLO_BOARD_ID",
)


def scout_runner(token: str, trigger_id: str) -> ScoutRunner:
    return ScoutRunner(client_from_token(token), trigger_id)


def missing(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not os.environ.get(name)]


async def serve() -> None:
    env = os.environ
    runner = scout_runner(env["KORA_BRIDGE_TOKEN"], env["KORA_SCOUT_TRIGGER_ID"])
    async with httpx.AsyncClient() as http:
        trello = TrelloClient.from_env(http)

        async def create_card(title: str, description: str) -> dict:
            return await trello.create(IDEAS_LIST, title, description)

        bot = TelegramBot(env["TELEGRAM_BOT_TOKEN"], http)
        bridge = Bridge(bot, runner, create_card, ALLOWLIST, time.time, int(time.time()))
        logging.getLogger("factory_bridge").info("ideas bridge polling Telegram")
        await bridge.run_forever(State(0, {}, {}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The Telegram idea door in front of the scout.")
    parser.add_argument("--once", metavar="IDEA", help="scout one idea, print the reply, exit")
    parser.add_argument("--from", dest="from_name", default="Navnit", help="proposer name")
    args = parser.parse_args(argv)
    absent = missing(KORA_KEYS if args.once else BRIDGE_KEYS)
    if absent:
        print(f"set these in .env first: {', '.join(absent)}", file=sys.stderr)
        return 2
    if args.once is not None and not idea_text_ok(args.once):
        print(bad_text(), file=sys.stderr)
        return 2
    if args.once:
        runner = scout_runner(os.environ["KORA_BRIDGE_TOKEN"], os.environ["KORA_SCOUT_TRIGGER_ID"])
        print(asyncio.run(scout_once(runner, args.once, args.from_name)))
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(serve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
