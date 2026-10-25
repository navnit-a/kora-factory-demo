import time
from collections.abc import Callable
from dataclasses import dataclass

from factory_demo.kora_api import KoraClient

SCOUT_TIMEOUT_S = 300
POLL_S = 5.0
SETTLED = frozenset({"idle", "completed", "failed", "budget_exhausted"})
FINISHED = frozenset({"idle", "completed"})
DELIVERY_LIMIT = 5
ANSWER_EVENT = "message_complete"


def final_text(events: list[dict]) -> str:
    texts = [text for event in events if (text := _answer(event)) is not None]
    if not texts:
        raise ValueError("the scout run has no finished answer in its events")
    return texts[-1]


@dataclass(frozen=True)
class ScoutRunner:
    kora: KoraClient
    trigger_id: str
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic

    def run(self, idea: str, from_name: str) -> str:
        deadline = self.clock() + SCOUT_TIMEOUT_S
        delivery_id = self.kora.fire_trigger(self.trigger_id, {"idea": idea, "from": from_name})
        run_id = self._wait(
            lambda: self._run_id(delivery_id), deadline, f"delivery {delivery_id} started no run"
        )
        state = self._wait(lambda: self._settled(run_id), deadline, f"run {run_id} did not settle")
        if state not in FINISHED:
            raise RuntimeError(f"scout run {run_id} ended {state}")
        return final_text(self.kora.run_events(run_id))

    def _wait(self, probe: Callable[[], str | None], deadline: float, what: str) -> str:
        while True:
            found = probe()
            if found:
                return found
            if self.clock() >= deadline:
                raise TimeoutError(f"{what} within {SCOUT_TIMEOUT_S}s")
            self.sleep(POLL_S)

    def _run_id(self, delivery_id: str) -> str | None:
        deliveries = self.kora.list_deliveries(self.trigger_id, DELIVERY_LIMIT)
        match = next(
            (d for d in deliveries if isinstance(d, dict) and d.get("id") == delivery_id), None
        )
        return None if match is None else _delivery_run_id(match)

    def _settled(self, run_id: str) -> str | None:
        run = self.kora.get_run(run_id)
        state = run.get("state") if isinstance(run, dict) else None
        return state if state in SETTLED else None


def _answer(event: dict) -> str | None:
    payload = event.get("payload")
    if event.get("event_type") != ANSWER_EVENT or not isinstance(payload, dict):
        return None
    text = payload.get("text")
    if payload.get("interrupted") or not isinstance(text, str):
        return None
    return text


def _delivery_run_id(delivery: dict) -> str | None:
    if isinstance(delivery.get("run_id"), str) and delivery["run_id"]:
        return delivery["run_id"]
    runs = delivery.get("runs")
    first = runs[0] if isinstance(runs, list) and runs and isinstance(runs[0], dict) else {}
    run_id = first.get("run_id")
    return run_id if isinstance(run_id, str) and run_id else None
