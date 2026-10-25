import json
from html.parser import HTMLParser

import httpx
import pytest
import respx

from factory_demo.github_app import (
    AppCredentials,
    callback_code,
    connection_manifest,
    convert,
    create_form,
    manifest,
    setup_installation_id,
    with_env_values,
)

CALLBACK = "http://127.0.0.1:8765/callback"
SETUP = "http://127.0.0.1:8765/setup"
REPO = "https://github.com/navnit-a/platformcon-day-planner"


class FormReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = ""
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form":
            self.action = values["action"]
        if tag == "input" and "name" in values:
            self.fields[values["name"]] = values.get("value", "")


def test_manifest_asks_for_least_permissions_and_no_webhook():
    body = manifest("kora factory", CALLBACK, SETUP, REPO)
    assert body["default_permissions"] == {
        "contents": "write",
        "pull_requests": "write",
        "checks": "read",
        "actions": "read",
        "metadata": "read",
    }
    assert body["public"] is False
    assert body["default_events"] == []
    assert "hook_attributes" not in body
    assert body["redirect_url"] == CALLBACK
    assert body["setup_url"] == SETUP
    assert body["url"] == REPO


def test_create_form_posts_manifest_with_state():
    body = manifest('kora "factory"', CALLBACK, SETUP, REPO)
    reader = FormReader()
    reader.feed(create_form(body, "s3cret"))
    assert reader.action == "https://github.com/settings/apps/new?state=s3cret"
    assert json.loads(reader.fields["manifest"]) == body


@respx.mock
def test_convert_returns_credentials():
    respx.post("https://api.github.com/app-manifests/c0de/conversions").mock(
        return_value=httpx.Response(
            201, json={"id": 42, "slug": "kora-factory", "pem": "-----BEGIN-----", "x": 1}
        )
    )
    with httpx.Client() as http:
        assert convert(http, "c0de") == AppCredentials("42", "kora-factory", "-----BEGIN-----")


@respx.mock
def test_convert_raises_on_failure():
    respx.post("https://api.github.com/app-manifests/old/conversions").mock(
        return_value=httpx.Response(422, json={"message": "expired"})
    )
    with httpx.Client() as http, pytest.raises(ValueError, match="422"):
        convert(http, "old")


def test_callback_rejects_foreign_state():
    with pytest.raises(ValueError, match="state does not match"):
        callback_code("/callback?code=abc&state=theirs", "ours")


def test_callback_needs_a_code():
    with pytest.raises(ValueError, match="no code"):
        callback_code("/callback?state=ours", "ours")


def test_callback_returns_the_code():
    assert callback_code("/callback?code=abc&state=ours", "ours") == "abc"


def test_setup_reads_the_installation_id():
    assert setup_installation_id("/setup?installation_id=987&setup_action=install") == "987"
    with pytest.raises(ValueError, match="installation_id"):
        setup_installation_id("/setup?installation_id=abc")


def test_with_env_values_replaces_and_appends():
    text = "A=1\nGITHUB_APP_ID=old\nB=2\n"
    out = with_env_values(text, {"GITHUB_APP_ID": "42", "GITHUB_APP_SLUG": "kora"})
    assert out == "A=1\nGITHUB_APP_ID=42\nB=2\nGITHUB_APP_SLUG=kora\n"


def test_connection_manifest_names_the_owner_and_installation():
    text = connection_manifest("42", "987")
    for line in (
        "kind: Connection",
        "  name: github",
        "  namespace: kora-tenant-example",
        "  adapter: github_app",
        "  baseHost: github.com",
        "  secretRef: github-app-key",
        "  secretKey: key.pem",
        '    app_id: "42"',
        "    installation_id: 987",
        "    owner: navnit-a",
    ):
        assert line in text
