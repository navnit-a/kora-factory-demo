import re
from pathlib import Path

LINE_PATTERN = re.compile(r"(?P<id>[0-9]+)(?:\s+(?P<name>.*))?")


def read_allowlist(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    lines = enumerate(path.read_text().splitlines(), start=1)
    return dict(_entry(path, number, line) for number, line in lines if line.strip())


def allow(path: Path, user_id: int, name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = " ".join((str(user_id), *name.split()))
    with path.open("a") as allowlist:
        allowlist.write(f"{line}\n")


def _entry(path: Path, number: int, line: str) -> tuple[int, str]:
    match = LINE_PATTERN.fullmatch(line.strip())
    if not match:
        raise ValueError(f"{path} line {number}: expected '<id>' or '<id> <name>', got {line!r}")
    return int(match.group("id")), (match.group("name") or "").strip()
