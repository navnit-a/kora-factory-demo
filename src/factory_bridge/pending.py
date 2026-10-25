from dataclasses import dataclass

from factory_bridge.scout_result import ScoutResult

PENDING_TTL_S = 1800


@dataclass(frozen=True)
class Proposal:
    user_id: int
    chat_id: int
    first_name: str
    idea: str
    result: ScoutResult
    created_at: float


def put(pending: dict[int, Proposal], proposal: Proposal) -> dict[int, Proposal]:
    return {**pending, proposal.user_id: proposal}


def take(
    pending: dict[int, Proposal], user_id: int, now: float
) -> tuple[Proposal | None, dict[int, Proposal]]:
    rest = {key: value for key, value in pending.items() if key != user_id}
    proposal = pending.get(user_id)
    if proposal is None or now - proposal.created_at > PENDING_TTL_S:
        return None, rest
    return proposal, rest
