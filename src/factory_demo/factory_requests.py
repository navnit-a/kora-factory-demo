from typing import Literal

from factory_demo.roster import (
    GITHUB_CONNECTION,
    GITHUB_RESOURCE,
    RUNS_PER_POD,
    SYDNEY,
    AgentSpec,
    Manual,
    Schedule,
    prompt,
)
from factory_demo.tools_check import TOOLS_BY_SERVER

Cadence = Literal["recording", "quiet"]
IMMUTABLE_AGENT_FIELDS = frozenset({"slug", "identity_mode", "framework"})
MUTABLE_TRIGGER_FIELDS = (
    "name",
    "prompt_template",
    "schedule_config",
    "manual_config",
    "max_parallel",
    "dedupe_enabled",
)
SERVER_OF = {tool: server for server, tools in TOOLS_BY_SERVER.items() for tool in tools}


def tool_scopes(spec: AgentSpec) -> list[str]:
    return [f"mcp:{SERVER_OF[tool]}:{tool}:use" for tool in spec.tools]


def agent_request(spec: AgentSpec, model_id: str, environment_id: str | None) -> dict:
    return {
        "name": spec.name,
        "slug": spec.slug,
        "description": spec.description,
        "system_prompt": prompt(spec.slug),
        "framework": "claude-code",
        "identity_mode": "autonomous",
        "model_id": model_id,
        "mcp_tools": tool_scopes(spec),
        "connectors": _connectors(spec),
        "environments": _environments(environment_id),
        "max_concurrent_runs_per_pod": RUNS_PER_POD,
        "budget": {
            "limit_usd": spec.weekly_limit_usd,
            "reset_cadence": "weekly",
            "per_run_limit_usd": spec.run_limit_usd,
        },
    }


def agent_patch(spec: AgentSpec, model_id: str, environment_id: str | None) -> dict:
    request = agent_request(spec, model_id, environment_id)
    return {k: v for k, v in request.items() if k not in IMMUTABLE_AGENT_FIELDS}


def schedule_trigger(spec: AgentSpec, schedule: Schedule, agent_id: str, cadence: Cadence) -> dict:
    cron = schedule.cron_recording if cadence == "recording" else schedule.cron_quiet
    return {
        "kind": "scheduled",
        "name": f"{spec.name}: {schedule.name}",
        "agent_type_id": agent_id,
        "prompt_template": schedule.tick,
        "schedule_config": {"cron_expression": cron, "timezone": SYDNEY, "catch_up": False},
        "max_parallel": 1,
        "dedupe_enabled": True,
    }


def manual_trigger(spec: AgentSpec, manual: Manual, agent_id: str) -> dict:
    inputs = [
        {
            "name": field.name,
            "type": "text",
            "label": field.label,
            "required": field.required,
            "default": field.default,
        }
        for field in manual.inputs
    ]
    return {
        "kind": "manual",
        "name": f"{spec.name}: {manual.name}",
        "agent_type_id": agent_id,
        "prompt_template": manual.prompt,
        "manual_config": {"inputs": inputs},
        "max_parallel": 1,
        "dedupe_enabled": True,
    }


def trigger_patch(request: dict) -> dict:
    return {k: request[k] for k in MUTABLE_TRIGGER_FIELDS if k in request}


def _connectors(spec: AgentSpec) -> list[dict]:
    if not spec.github_actions:
        return []
    return [
        {
            "connection": GITHUB_CONNECTION,
            "actions": list(spec.github_actions),
            "resources": [GITHUB_RESOURCE],
        }
    ]


def _environments(environment_id: str | None) -> list[dict]:
    return (
        [] if environment_id is None else [{"environment_id": environment_id, "is_default": True}]
    )
