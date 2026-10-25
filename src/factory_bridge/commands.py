import re
from dataclasses import dataclass

IDEA_MIN = 10
IDEA_MAX = 500
NAME_MAX = 30
FALLBACK_NAME = "the team"
NAME_MARKS = frozenset(" -'")
IDEA_PATTERN = re.compile(r"/idea(?:@kora_factory_bot)?(?:\s+(?P<text>.*))?", re.I | re.S)
DECISION_PATTERN = re.compile(r"(?P<word>yes|no)[\s.!?]*", re.I)


@dataclass(frozen=True)
class Idea:
    text: str


@dataclass(frozen=True)
class Decision:
    yes: bool


def parse_command(text: str) -> Idea | Decision | None:
    message = text.strip()
    idea = IDEA_PATTERN.fullmatch(message)
    if idea:
        return Idea((idea.group("text") or "").strip())
    decision = DECISION_PATTERN.fullmatch(message)
    if decision:
        return Decision(yes=decision.group("word").lower() == "yes")
    return None


def idea_text_ok(text: str) -> bool:
    return IDEA_MIN <= len(text) <= IDEA_MAX and "<" not in text and ">" not in text


def proposer_name(first_name: str) -> str:
    kept = "".join(char for char in first_name if char.isalpha() or char in NAME_MARKS)
    name = " ".join(kept.split())[:NAME_MAX].strip()
    return name or FALLBACK_NAME
