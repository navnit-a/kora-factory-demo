import argparse
import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factory_demo.cli import run_cli  # noqa: E402
from factory_demo.evaluation import FIXTURES  # noqa: E402
from factory_demo.evaluation_runner import (  # noqa: E402
    EvaluationBoard,
    evaluate,
    fetch_channel_preview,
)
from factory_demo.kora_api import load_client  # noqa: E402
from factory_demo.secrets import read_env  # noqa: E402
from factory_tools.trello.client import TrelloClient  # noqa: E402


async def run(args: argparse.Namespace) -> int:
    env = read_env(str(ROOT / ".env"))
    kora = load_client()
    async with httpx.AsyncClient() as http:
        trello = TrelloClient(
            env["TRELLO_API_KEY"], env["TRELLO_TOKEN"], env["TRELLO_BOARD_ID"], http
        )
        result = await evaluate(
            args.slug,
            kora,
            EvaluationBoard(trello),
            lambda: fetch_channel_preview(env["TELEGRAM_CHANNEL"]),
            card_id=args.card,
            keep=args.keep,
        )
    outcome = result.outcome
    print(f"run {result.run_id}: {outcome.run_state}, cost {outcome.cost_usd:.4f} USD")
    if result.card_id:
        print(f"card {result.card_id} in {outcome.card_list}")
    print("PASS" if result.verdict.passed else "FAIL")
    for reason in result.verdict.reasons:
        print(f"  - {reason}")
    return 0 if result.verdict.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", choices=sorted(FIXTURES))
    parser.add_argument("--card")
    parser.add_argument("--keep", action="store_true")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
