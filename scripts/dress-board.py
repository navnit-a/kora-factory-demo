import argparse
import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastmcp.exceptions import ToolError  # noqa: E402

from factory_demo.dress_board import dress, report_lines  # noqa: E402
from factory_demo.secrets import read_env  # noqa: E402
from factory_tools.trello.client import TrelloClient  # noqa: E402


async def main(dry_run: bool) -> int:
    env = read_env(str(ROOT / ".env"))
    async with httpx.AsyncClient() as http:
        trello = TrelloClient(
            env["TRELLO_API_KEY"], env["TRELLO_TOKEN"], env["TRELLO_BOARD_ID"], http
        )
        try:
            report = await dress(trello, dry_run)
        except ToolError as error:
            print(f"dress-board stopped: {error}", file=sys.stderr)
            return 1
    for line in report_lines(report, dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Name the lanes and labels; dress every card.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    raise SystemExit(asyncio.run(main(parser.parse_args().dry_run)))
