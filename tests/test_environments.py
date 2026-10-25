import httpx
import respx

from factory_demo.environments import ENVIRONMENTS, NODE_WEB, PYTHON_TOOLS, environment_request
from factory_demo.kora_api import KoraClient
from factory_demo.roster import ROSTER

BASE = "https://api.local.runkora.io"


def test_node_web_runs_on_the_node_image_within_the_laptop_budget():
    body = environment_request(NODE_WEB)
    assert body["slug"] == "node-web"
    assert body["sandbox_image"] == "kora-node"
    assert body["size"] == {"cpu": "1", "memory": "2Gi", "disk": "8Gi"}


def test_node_web_reaches_npm_github_and_the_conference_site_and_nothing_else():
    hosts = environment_request(NODE_WEB)["egress_hosts"]
    assert hosts == [
        "registry.npmjs.org",
        "github.com",
        "api.github.com",
        "codeload.github.com",
        "objects.githubusercontent.com",
        "sydney.platformcon.com",
    ]


def test_environment_request_is_a_fresh_copy_each_time():
    first = environment_request(NODE_WEB)
    first["egress_hosts"].append("evil.example")
    assert "evil.example" not in environment_request(NODE_WEB)["egress_hosts"]


def test_python_tools_environment_request():
    body = environment_request(PYTHON_TOOLS)
    assert body["slug"] == "python-tools"
    assert body["sandbox_image"] == "kora-base"
    assert body["size"] == {"cpu": "1", "memory": "2Gi", "disk": "8Gi"}
    assert {"pypi.org", "files.pythonhosted.org", "github.com"} <= set(body["egress_hosts"])
    assert "registry.npmjs.org" not in body["egress_hosts"]


def test_every_roster_environment_is_declared():
    declared = {spec.slug for spec in ENVIRONMENTS}
    assert {spec.environment for spec in ROSTER if spec.environment} <= declared
    assert tuple(spec.slug for spec in ENVIRONMENTS) == ("node-web", "python-tools")


@respx.mock
def test_client_creates_an_environment():
    route = respx.post(f"{BASE}/api/v1/environments").mock(
        return_value=httpx.Response(201, json={"id": "env-1", "slug": "node-web"})
    )
    created = KoraClient(BASE, "tok").create_environment({"slug": "node-web"})
    assert created["id"] == "env-1"
    assert route.calls[0].request.read() == b'{"slug":"node-web"}'
