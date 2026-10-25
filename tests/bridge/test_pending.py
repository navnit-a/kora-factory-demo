from factory_bridge.pending import PENDING_TTL_S, Proposal, put, take
from factory_bridge.scout_result import ScoutResult

NOW = 1_800_000_000.0
RESULT = ScoutResult(
    "Show the next break", "Story.", ("Given a, When b, Then c",), "buildable", "none", "Reason."
)


def _proposal(user_id: int = 111, idea: str = "show the next break", at: float = NOW) -> Proposal:
    return Proposal(user_id, 999, "Navnit", idea, RESULT, at)


def test_take_returns_the_proposal_and_removes_it():
    pending = put({}, _proposal())
    proposal, rest = take(pending, 111, NOW + 60)
    assert proposal == _proposal()
    assert rest == {}
    assert 111 in pending


def test_take_leaves_other_people_alone():
    pending = put(put({}, _proposal()), _proposal(user_id=222))
    proposal, rest = take(pending, 111, NOW)
    assert proposal.user_id == 111
    assert list(rest) == [222]


def test_absent_proposal_is_none():
    assert take({}, 111, NOW) == (None, {})


def test_expired_proposal_is_dropped_on_take():
    pending = put({}, _proposal())
    assert take(pending, 111, NOW + PENDING_TTL_S)[0] is not None
    assert take(pending, 111, NOW + PENDING_TTL_S + 1) == (None, {})


def test_new_proposal_replaces_the_old_one():
    pending = put(put({}, _proposal(idea="first idea text")), _proposal(idea="second idea text"))
    assert len(pending) == 1
    assert pending[111].idea == "second idea text"
