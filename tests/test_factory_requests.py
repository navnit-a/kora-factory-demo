from factory_demo.factory_requests import (
    agent_patch,
    agent_request,
    manual_trigger,
    schedule_trigger,
    tool_scopes,
    trigger_patch,
)
from factory_demo.roster import by_slug, prompt


def test_tool_scopes_use_server_and_tool():
    assert tool_scopes(by_slug("code-reviewer")) == [
        "mcp:trello:trello_list_cards:use",
        "mcp:trello:trello_get_card:use",
        "mcp:trello:trello_move_card:use",
        "mcp:trello:trello_comment_card:use",
    ]
    assert tool_scopes(by_slug("sydney-trains")) == [
        "mcp:transport:transport_sydney_trains_status:use",
        "mcp:telegram:telegram_send_message:use",
    ]


def test_developer_request_has_github_connector_on_one_repo():
    request = agent_request(by_slug("senior-developer"), "anthropic/claude-sonnet-5-5", "e-1")
    assert request["connectors"] == [
        {
            "connection": "github",
            "actions": [
                "contents:read",
                "contents:write",
                "pulls:read",
                "pulls:write",
                "checks:read",
                "actions:read",
            ],
            "resources": ["platformcon-day-planner"],
        }
    ]
    assert request["environments"] == [{"environment_id": "e-1", "is_default": True}]
    assert request["model_id"] == "anthropic/claude-sonnet-5-5"
    assert request["framework"] == "claude-code"
    assert request["identity_mode"] == "autonomous"
    assert request["system_prompt"] == prompt("senior-developer")
    assert request["max_concurrent_runs_per_pod"] == 3


def test_product_owner_request_has_no_connector_and_no_environment():
    request = agent_request(by_slug("product-owner"), "anthropic/claude-haiku-5-5", None)
    assert request["connectors"] == []
    assert request["environments"] == []
    assert request["slug"] == "product-owner"
    assert "mcp:trello:trello_update_card_description:use" in request["mcp_tools"]


def test_budget_is_weekly_with_run_limit():
    developer = agent_request(by_slug("senior-developer"), "m", "e-1")
    tester = agent_request(by_slug("tester"), "m", "e-1")
    assert developer["budget"] == {
        "limit_usd": 10.0,
        "reset_cadence": "weekly",
        "per_run_limit_usd": 0.40,
    }
    assert tester["budget"] == {
        "limit_usd": 3.0,
        "reset_cadence": "weekly",
        "per_run_limit_usd": 0.20,
    }


def test_patch_drops_immutable_fields():
    patch = agent_patch(by_slug("tester"), "m", "e-1")
    assert not {"slug", "identity_mode", "framework"} & set(patch)
    assert patch["system_prompt"] == prompt("tester")
    assert patch["mcp_tools"] == tool_scopes(by_slug("tester"))


def test_schedule_trigger_uses_cadence_cron():
    spec = by_slug("senior-developer")
    recording = schedule_trigger(spec, spec.schedules[0], "at-1", "recording")
    quiet = schedule_trigger(spec, spec.schedules[0], "at-1", "quiet")
    assert recording["schedule_config"] == {
        "cron_expression": "*/5 * * * *",
        "timezone": "Australia/Sydney",
        "catch_up": False,
    }
    assert quiet["schedule_config"]["cron_expression"] == "*/15 * * * *"
    assert recording["kind"] == "scheduled"
    assert recording["name"] == "Senior developer: every 5 min"
    assert recording["agent_type_id"] == "at-1"
    assert recording["max_parallel"] == 1
    assert recording["dedupe_enabled"] is True
    assert "{{ var.datetime }}" in recording["prompt_template"]


def test_manual_trigger_declares_inputs():
    lunch = by_slug("lunch")
    request = manual_trigger(lunch, lunch.manuals[0], "at-8")
    assert request["kind"] == "manual"
    assert request["name"] == "Lunch: run now"
    assert request["manual_config"]["inputs"][0] == {
        "name": "place",
        "type": "text",
        "label": "Place name",
        "required": True,
        "default": "Sydney Masonic Centre",
    }
    assert request["max_parallel"] == 1
    scrum = by_slug("scrum-master")
    now = manual_trigger(scrum, scrum.manuals[0], "at-3")["manual_config"]["inputs"]
    assert [(i["name"], i["required"]) for i in now] == [("now", True)]


def test_manual_trigger_without_inputs_sends_empty_config():
    spec = by_slug("tester")
    assert manual_trigger(spec, spec.manuals[0], "at-6")["manual_config"] == {"inputs": []}


def test_trigger_patch_leaves_the_schedule_alone():
    spec = by_slug("tester")
    request = schedule_trigger(spec, spec.schedules[0], "at-6", "quiet")
    patch = trigger_patch(request)
    assert set(patch) == {"name", "prompt_template", "max_parallel", "dedupe_enabled"}
    assert patch is not request


def test_trigger_patch_keeps_manual_config():
    spec = by_slug("tester")
    patch = trigger_patch(manual_trigger(spec, spec.manuals[0], "at-6"))
    assert patch["manual_config"] == {"inputs": []}


def test_support_gets_read_only_github():
    request = agent_request(by_slug("support"), "anthropic/claude-haiku-5-5", "e-1")
    assert request["connectors"] == [
        {
            "connection": "github",
            "actions": ["contents:read", "actions:read", "checks:read"],
            "resources": ["platformcon-day-planner"],
        }
    ]
    assert "mcp:trello:trello_create_card:use" in request["mcp_tools"]


def test_tool_scopes_turn_dots_into_colons():
    scopes = tool_scopes(by_slug("agent-ops"))
    assert "mcp:kora:runs:events:use" in scopes
    assert "mcp:kora:triggers:deliveries:list:use" in scopes
    assert "mcp:trello:trello_write_watch_log:use" in scopes
    assert "mcp:trello:trello_mark_diagnosed:use" in scopes
    assert "mcp:trello:trello_comment_card:use" not in scopes
    assert "mcp:trello:trello_update_card_description:use" not in scopes
    assert "mcp:trello:trello_add_label:use" not in scopes


def test_agent_request_carries_grant_scopes_and_resources():
    ops = agent_request(by_slug("agent-ops"), "anthropic/claude-sonnet-5-5", "e-2")
    assert ops["grant_scopes"] == list(by_slug("agent-ops").grant_scopes)
    assert "agents:runs:idea-scout:read" in ops["grant_scopes"]
    assert [c["resources"] for c in ops["connectors"]] == [["kora-factory-demo"]]
    developer = agent_request(by_slug("senior-developer"), "anthropic/claude-sonnet-5-5", "e-1")
    assert developer["grant_scopes"] == []
    assert [c["resources"] for c in developer["connectors"]] == [["platformcon-day-planner"]]


def test_tool_scopes_grant_the_board_language_tools():
    assert tool_scopes(by_slug("product-owner")) == [
        "mcp:trello:trello_list_cards:use",
        "mcp:trello:trello_get_card:use",
        "mcp:trello:trello_update_card_description:use",
        "mcp:trello:trello_add_checklist:use",
        "mcp:trello:trello_add_label:use",
        "mcp:trello:trello_move_card:use",
        "mcp:trello:trello_comment_card:use",
    ]
    lead = tool_scopes(by_slug("delivery-lead"))
    assert "mcp:trello:trello_add_label:use" in lead
    assert "mcp:trello:trello_set_priority:use" in lead
    assert "mcp:trello:trello_check_item:use" in tool_scopes(by_slug("tester"))
    support = tool_scopes(by_slug("support"))
    assert "mcp:trello:trello_add_label:use" in support
    assert "mcp:trello:trello_set_priority:use" in support
