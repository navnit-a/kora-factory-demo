import json

import httpx
import pytest
import respx

from factory_bridge.kora_runs import POLL_S, SCOUT_TIMEOUT_S, SETTLED, ScoutRunner, final_text
from factory_demo.kora_api import KoraClient

BASE = "https://api.local.runkora.io"
TRIGGER = "t-scout"


def complete(text: str, interrupted: bool = False) -> dict:
    payload = {"text": text, **({"interrupted": True} if interrupted else {})}
    return {"sequence_no": 1, "event_type": "message_complete", "payload": payload}


def test_final_text_takes_the_last_uninterrupted_message_complete():
    events = [
        complete("first"),
        {"event_type": "text_block", "payload": {"content": "thinking aloud"}},
        complete("the answer"),
        complete("half an answ", interrupted=True),
        {"event_type": "tool_use", "payload": {}},
    ]
    assert final_text(events) == "the answer"


def test_final_text_raises_when_there_is_no_finished_answer():
    with pytest.raises(ValueError, match="finished answer"):
        final_text([complete("cut", interrupted=True), {"event_type": "message_complete"}])


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: tuple[float, ...] = ()

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps = (*self.sleeps, seconds)
        self.now += seconds


def runner(fake: FakeTime) -> ScoutRunner:
    return ScoutRunner(KoraClient(BASE, "tok"), TRIGGER, sleep=fake.sleep, clock=fake.clock)


def deliveries(*items: dict) -> httpx.Response:
    return httpx.Response(200, json={"deliveries": list(items)})


def events_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"events": [complete(text)], "next_seq": 1, "has_more": False})


@respx.mock
def test_scout_runner_waits_for_the_delivery_then_the_run():
    fire = respx.post(f"{BASE}/api/v1/trigger-fires/{TRIGGER}").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    listed = respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        side_effect=[
            deliveries(),
            deliveries({"id": "d-0", "run_id": "r-old"}, {"id": "d-1", "runs": []}),
            deliveries({"id": "d-1", "runs": [{"run_id": "r-1"}]}),
        ]
    )
    respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        side_effect=[
            httpx.Response(200, json={"id": "r-1", "state": "active"}),
            httpx.Response(200, json={"id": "r-1", "state": "idle"}),
        ]
    )
    events = respx.get(f"{BASE}/api/v1/runs/r-1/events").mock(return_value=events_reply("done"))
    fake = FakeTime()
    assert runner(fake).run("Rate each talk", "Ana") == "done"

    assert json.loads(fire.calls.last.request.content) == {
        "variables": {"idea": "Rate each talk", "from": "Ana"}
    }
    assert listed.calls.last.request.url.params["limit"] == "5"
    assert events.calls.last.request.headers["Accept"] == "application/json"
    assert fake.sleeps == (POLL_S, POLL_S, POLL_S)


@respx.mock
def test_scout_runner_reads_a_top_level_run_id():
    respx.post(f"{BASE}/api/v1/trigger-fires/{TRIGGER}").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        return_value=deliveries({"id": "d-1", "run_id": "r-1"})
    )
    respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        return_value=httpx.Response(200, json={"id": "r-1", "state": "completed"})
    )
    respx.get(f"{BASE}/api/v1/runs/r-1/events").mock(return_value=events_reply("ok"))
    assert runner(FakeTime()).run("idea text", "Ana") == "ok"


@respx.mock
def test_scout_runner_times_out():
    respx.post(f"{BASE}/api/v1/trigger-fires/{TRIGGER}").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        return_value=deliveries({"id": "d-1", "runs": []})
    )
    fake = FakeTime()
    with pytest.raises(TimeoutError, match="d-1"):
        runner(fake).run("idea text", "Ana")
    assert fake.now - 1000.0 == SCOUT_TIMEOUT_S
    assert len(fake.sleeps) == SCOUT_TIMEOUT_S / POLL_S


@respx.mock
def test_scout_runner_times_out_on_a_run_that_never_settles():
    respx.post(f"{BASE}/api/v1/trigger-fires/{TRIGGER}").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        return_value=deliveries({"id": "d-1", "run_id": "r-1"})
    )
    respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        return_value=httpx.Response(200, json={"id": "r-1", "state": "active"})
    )
    with pytest.raises(TimeoutError, match="r-1"):
        runner(FakeTime()).run("idea text", "Ana")


@pytest.mark.parametrize("state", ["error", "terminated", "completing", "pending"])
def test_states_kora_does_not_settle_on_are_not_settled(state):
    assert state not in SETTLED


@respx.mock
@pytest.mark.parametrize("state", ["failed", "budget_exhausted"])
def test_scout_runner_names_a_failed_run(state):
    respx.post(f"{BASE}/api/v1/trigger-fires/{TRIGGER}").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        return_value=deliveries({"id": "d-1", "run_id": "r-1"})
    )
    respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        return_value=httpx.Response(200, json={"id": "r-1", "state": state})
    )
    with pytest.raises(RuntimeError, match=state):
        runner(FakeTime()).run("idea text", "Ana")


@respx.mock
def test_budget_exhausted_settles_at_once():
    respx.post(f"{BASE}/api/v1/trigger-fires/{TRIGGER}").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        return_value=deliveries({"id": "d-1", "run_id": "r-1"})
    )
    run = respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        return_value=httpx.Response(200, json={"id": "r-1", "state": "budget_exhausted"})
    )
    fake = FakeTime()
    with pytest.raises(RuntimeError, match="budget_exhausted"):
        runner(fake).run("idea text", "Ana")
    assert run.call_count == 1
    assert fake.sleeps == ()


@respx.mock
def test_run_id_skips_non_dict_deliveries():
    respx.post(f"{BASE}/api/v1/trigger-fires/{TRIGGER}").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        return_value=httpx.Response(
            200, json={"deliveries": ["d-1", None, 7, ["d-1"], {"id": "d-1", "run_id": "r-1"}]}
        )
    )
    respx.get(f"{BASE}/api/v1/runs/r-1").mock(
        return_value=httpx.Response(200, json={"id": "r-1", "state": "completed"})
    )
    respx.get(f"{BASE}/api/v1/runs/r-1/events").mock(return_value=events_reply("ok"))
    assert runner(FakeTime()).run("idea text", "Ana") == "ok"
