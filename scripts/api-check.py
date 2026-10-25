import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factory_demo.checks import api_checks  # noqa: E402
from factory_demo.cli import run_cli  # noqa: E402
from factory_demo.kora_api import load_client  # noqa: E402


def main() -> int:
    results = api_checks(load_client())
    for ok, name in results:
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    return 0 if all(ok for ok, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
