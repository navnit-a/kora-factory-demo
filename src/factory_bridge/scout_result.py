import re
from dataclasses import dataclass

from factory_demo.practices import SCOUT_TAGS, VERDICTS

CRITERION_MARK = "- "


@dataclass(frozen=True)
class ScoutResult:
    title: str
    story: str
    criteria: tuple[str, ...]
    verdict: str
    dependencies: str
    reason: str


def parse_scout(text: str) -> ScoutResult:
    found = {tag: _tag(text, tag) for tag in SCOUT_TAGS}
    missing = [tag for tag in SCOUT_TAGS if not found[tag]]
    if missing:
        raise ValueError(f"scout answer missing: {', '.join(missing)}")
    if found["verdict"] not in VERDICTS:
        raise ValueError(f"scout verdict {found['verdict']!r} is not one of {', '.join(VERDICTS)}")
    criteria = _criteria(found["criteria"])
    if not criteria:
        raise ValueError(f"scout criteria have no lines starting {CRITERION_MARK!r}")
    return ScoutResult(
        title=found["title"],
        story=found["story"],
        criteria=criteria,
        verdict=found["verdict"],
        dependencies=found["dependencies"],
        reason=found["reason"],
    )


def _tag(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    return match.group(1).strip() if match else ""


def _criteria(block: str) -> tuple[str, ...]:
    lines = tuple(line.strip() for line in block.splitlines() if line.strip())
    starts = tuple(index for index, line in enumerate(lines) if line.startswith(CRITERION_MARK))
    ends = (*starts[1:], len(lines))
    return tuple(_criterion(lines[start:end]) for start, end in zip(starts, ends, strict=False))


def _criterion(lines: tuple[str, ...]) -> str:
    return " ".join((lines[0].removeprefix(CRITERION_MARK).strip(), *lines[1:]))
