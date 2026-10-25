import json

import httpx
import respx

from factory_demo.kora_api import KoraClient

BASE = "https://api.local.runkora.io"


def client() -> KoraClient:
    return KoraClient(BASE, "tok")


@respx.mock
def test_list_triggers_unwraps_null_as_empty():
    respx.get(f"{BASE}/api/v1/triggers").mock(
        return_value=httpx.Response(200, json={"triggers": None})
    )
    assert client().list_triggers() == []


@respx.mock
def test_list_triggers_unwraps_the_envelope():
    respx.get(f"{BASE}/api/v1/triggers").mock(
        return_value=httpx.Response(200, json={"triggers": [{"id": "t-1"}]})
    )
    assert client().list_triggers() == [{"id": "t-1"}]


@respx.mock
def test_create_trigger_posts_body():
    route = respx.post(f"{BASE}/api/v1/triggers").mock(
        return_value=httpx.Response(201, json={"id": "t-1"})
    )
    assert client().create_trigger({"kind": "manual", "name": "x"}) == {"id": "t-1"}
    assert json.loads(route.calls.last.request.content) == {"kind": "manual", "name": "x"}


@respx.mock
def test_update_trigger_patches_by_id():
    route = respx.patch(f"{BASE}/api/v1/triggers/t-1").mock(
        return_value=httpx.Response(200, json={"id": "t-1", "enabled": False})
    )
    assert client().update_trigger("t-1", {"enabled": False})["enabled"] is False
    assert json.loads(route.calls.last.request.content) == {"enabled": False}


@respx.mock
def test_fire_trigger_returns_delivery_id():
    route = respx.post(f"{BASE}/api/v1/trigger-fires/t-1").mock(
        return_value=httpx.Response(202, json={"delivery_id": "d-1"})
    )
    assert client().fire_trigger("t-1", {"now": "x"}) == "d-1"
    assert json.loads(route.calls.last.request.content) == {"variables": {"now": "x"}}


@respx.mock
def test_list_deliveries_filters_by_trigger():
    route = respx.get(f"{BASE}/api/v1/trigger-deliveries").mock(
        return_value=httpx.Response(200, json={"deliveries": [{"id": "d-1", "run_id": "r-1"}]})
    )
    assert client().list_deliveries("t-1") == [{"id": "d-1", "run_id": "r-1"}]
    params = route.calls.last.request.url.params
    assert params["trigger_id"] == "t-1"
    assert params["omit_payload"] == "true"
    assert params["limit"] == "10"


@respx.mock
def test_get_tenant_budget_none_when_unset():
    respx.get(f"{BASE}/api/v1/policy/tenant-budget").mock(
        return_value=httpx.Response(
            404, json={"code": "resource_not_found", "message": "no tenant budget configured"}
        )
    )
    assert client().get_tenant_budget() is None


@respx.mock
def test_get_tenant_budget_returns_the_cap():
    respx.get(f"{BASE}/api/v1/policy/tenant-budget").mock(
        return_value=httpx.Response(200, json={"limit_usd": 60.0, "reset_cadence": "weekly"})
    )
    assert client().get_tenant_budget() == {"limit_usd": 60.0, "reset_cadence": "weekly"}


@respx.mock
def test_set_tenant_budget_puts_weekly_cap():
    route = respx.put(f"{BASE}/api/v1/policy/tenant-budget").mock(
        return_value=httpx.Response(200, json={"limit_usd": 60.0, "reset_cadence": "weekly"})
    )
    client().set_tenant_budget(60.0, "weekly")
    assert json.loads(route.calls.last.request.content) == {
        "limit_usd": 60.0,
        "reset_cadence": "weekly",
    }
