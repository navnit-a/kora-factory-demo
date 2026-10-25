import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factory_bridge.allowlist import allow  # noqa: E402

ALLOWLIST = ROOT / "deploy/generated/ideas-allowlist"


def main(argv: list[str] | None = None, path: Path = ALLOWLIST) -> int:
    parser = argparse.ArgumentParser(description="Let a Telegram user send ideas to the bridge.")
    parser.add_argument("user_id", type=int, help="the Telegram id the bot's refusal named")
    parser.add_argument("name", nargs="*", help="a name to remember them by")
    args = parser.parse_args(argv)
    if args.user_id <= 0:
        parser.error("the Telegram id is a positive number")
    name = " ".join(args.name)
    allow(path, args.user_id, name)
    print(f"allowed {args.user_id} {name}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
