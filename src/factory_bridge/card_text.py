from factory_bridge.commands import proposer_name
from factory_bridge.scout_result import ScoutResult


def card_title(result: ScoutResult) -> str:
    return result.title


def card_description(result: ScoutResult, first_name: str) -> str:
    criteria = "\n".join(f"- {criterion}" for criterion in result.criteria)
    return (
        f"{result.story}\n\n"
        f"Acceptance criteria:\n{criteria}\n\n"
        f"Verdict: {result.verdict}. {result.reason}\n"
        f"Dependencies: {result.dependencies}\n\n"
        f"Proposed by {proposer_name(first_name)} via Telegram"
    )
