import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factory_demo.ideas import seed_ideas  # noqa: E402
from factory_demo.secrets import read_env  # noqa: E402
from factory_tools.trello.client import TrelloClient  # noqa: E402


async def main() -> int:
    env = read_env(str(ROOT / ".env"))
    async with httpx.AsyncClient() as http:
        trello = TrelloClient(
            env["TRELLO_API_KEY"], env["TRELLO_TOKEN"], env["TRELLO_BOARD_ID"], http
        )
        created = await seed_ideas(trello)
    for title in created:
        print(f"added to Ideas: {title}")
    print(f"{len(created)} idea(s) added")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
