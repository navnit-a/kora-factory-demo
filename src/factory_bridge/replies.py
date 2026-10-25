from factory_bridge.commands import IDEA_MAX, IDEA_MIN
from factory_bridge.rate_limit import LIMIT
from factory_bridge.scout_result import ScoutResult

TELEGRAM_MAX = 4096
CUT_MARK = "..."
ASK_YES = "Reply yes to add it to Ideas, or no to drop it."
ASK_NO = "Reply no to drop it, or send /idea again with a change."


def ack() -> str:
    return "Got it. The idea scout is reading the planner now; the write-up follows in a minute."


def proposal(result: ScoutResult) -> str:
    criteria = "\n".join(f"- {criterion}" for criterion in result.criteria)
    body = (
        f"{result.title}\n\n{result.story}\n\nAcceptance:\n{criteria}\n\n"
        f"Verdict: {_verdict(result)} {result.reason}"
    )
    question = ASK_NO if result.verdict == "not_buildable" else ASK_YES
    return f"{_fit(body, TELEGRAM_MAX - len(question) - 2)}\n\n{question}"


def added(url: str) -> str:
    return f"Added to Ideas: {url}"


def dropped() -> str:
    return "Dropped. Nothing was added to the board."


def nothing_pending() -> str:
    return "There is no idea waiting for an answer. Send /idea followed by your idea."


def refused(user_id: int) -> str:
    return (
        "Sorry, I only take ideas from the team. "
        f"Your Telegram id is {user_id}; ask Navnit to add it."
    )


def rate_limited(until: str) -> str:
    return f"That is {LIMIT} ideas in the last hour. Send the next one after {until}."


def bad_text() -> str:
    return (
        f"Send /idea followed by the idea in {IDEA_MIN} to {IDEA_MAX} characters. "
        "The characters < and > are not allowed."
    )


def scout_failed() -> str:
    return "The idea scout could not write this one up. Nothing was added; try /idea again later."


def not_buildable_yes() -> str:
    return f"The scout judged this one not buildable, so it stays off the board. {ASK_NO}"


def _verdict(result: ScoutResult) -> str:
    if result.verdict == "buildable":
        return "the planner can build this as it is."
    if result.verdict == "needs_dependency":
        return f"buildable once the planner has {result.dependencies}."
    return "the planner cannot build this."


def _fit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - len(CUT_MARK)].rstrip() + CUT_MARK
