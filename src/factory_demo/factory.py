from collections.abc import Callable
from dataclasses import dataclass

import httpx

from factory_demo.factory_requests import (
    Cadence,
    agent_patch,
    agent_request,
    manual_trigger,
    schedule_trigger,
    trigger_patch,
)
from factory_demo.kora_api import KoraAuthError, KoraClient
from factory_demo.roster import ROSTER, AgentSpec
from factory_demo.smoke import pick_model

TENANT_CAP_USD = 60.0
TENANT_CAP_CADENCE = "weekly"
GITHUB_SKIP_REASON = "run with --with-github after the GitHub App is connected"


@dataclass(frozen=True)
class DeployReport:
    created: tuple[str, ...]
    updated: tuple[str, ...]
    skipped: tuple[str, ...]


def deploy_factory(
    client: KoraClient,
    cadence: Cadence,
    include_github: bool,
    wait: Callable[[str], object] | None = None,
) -> DeployReport:
    models = client.list_models()
    environments = {e["slug"]: e["id"] for e in client.list_environments()}
    agents = {a["slug"]: a for a in client.list_agents()}
    triggers = {t["name"]: t for t in client.list_triggers()}
    report = DeployReport((), (), ())
    for spec in ROSTER:
        if spec.github_actions and not include_github:
            report = _with(report, skipped=f"{spec.name}: {GITHUB_SKIP_REASON}")
            continue
        model_id = pick_model(models, spec.model)
        environment_id = environments.get(spec.environment) if spec.environment else None
        agent, report = _upsert_agent(client, spec, agents, model_id, environment_id, report)
        if wait is not None:
            wait(agent["id"])
        report = _upsert_triggers(client, spec, agent["id"], cadence, triggers, report)
    return report


def set_team_schedules(client: KoraClient, enabled: bool, cadence: Cadence) -> tuple[str, ...]:
    triggers = {t["name"]: t for t in client.list_triggers()}
    failed: tuple[str, ...] = ()
    for spec in ROSTER:
        for schedule in (s for s in spec.schedules if s.team):
            request = schedule_trigger(spec, schedule, "", cadence)
            existing = triggers.get(request["name"])
            if existing is None:
                continue
            patch = {"enabled": enabled, "schedule_config": request["schedule_config"]}
            try:
                client.update_trigger(existing["id"], patch)
            except (KoraAuthError, httpx.HTTPError):
                failed = (*failed, request["name"])
    return failed


def factory_status(client: KoraClient) -> list[tuple[str, str, bool]]:
    rows = [
        (t["name"], (t.get("schedule_config") or {}).get("cron_expression", ""), t["enabled"])
        for t in client.list_triggers()
        if t.get("kind") == "scheduled"
    ]
    return sorted(rows)


def ensure_tenant_cap(client: KoraClient) -> dict:
    current = client.get_tenant_budget()
    wanted = {"limit_usd": TENANT_CAP_USD, "reset_cadence": TENANT_CAP_CADENCE}
    if current and all(current.get(k) == v for k, v in wanted.items()):
        return current
    return client.set_tenant_budget(TENANT_CAP_USD, TENANT_CAP_CADENCE)


def _upsert_agent(
    client: KoraClient,
    spec: AgentSpec,
    agents: dict[str, dict],
    model_id: str,
    environment_id: str | None,
    report: DeployReport,
) -> tuple[dict, DeployReport]:
    existing = agents.get(spec.slug)
    if existing is None:
        agent = client.create_agent(agent_request(spec, model_id, environment_id))
        return agent, _with(report, created=f"agent {spec.slug}")
    agent = client.update_agent(existing["id"], agent_patch(spec, model_id, environment_id))
    return {**existing, **agent}, _with(report, updated=f"agent {spec.slug}")


def _upsert_triggers(
    client: KoraClient,
    spec: AgentSpec,
    agent_id: str,
    cadence: Cadence,
    triggers: dict[str, dict],
    report: DeployReport,
) -> DeployReport:
    scheduled = [(schedule_trigger(spec, s, agent_id, cadence), s.team) for s in spec.schedules]
    manual = [(manual_trigger(spec, m, agent_id), False) for m in spec.manuals]
    for request, pause_on_create in (*scheduled, *manual):
        existing = triggers.get(request["name"])
        if existing is not None:
            client.update_trigger(existing["id"], trigger_patch(request))
            report = _with(report, updated=f"trigger {request['name']}")
            continue
        created = client.create_trigger(request)
        if pause_on_create:
            client.update_trigger(created["id"], {"enabled": False})
        report = _with(report, created=f"trigger {request['name']}")
    return report


def _with(report: DeployReport, **added: str) -> DeployReport:
    return DeployReport(
        created=(*report.created, *([added["created"]] if "created" in added else [])),
        updated=(*report.updated, *([added["updated"]] if "updated" in added else [])),
        skipped=(*report.skipped, *([added["skipped"]] if "skipped" in added else [])),
    )
