import httpx
import respx

from factory_demo.checks import api_checks, probe_claude, probe_openai
from factory_demo.kora_api import KoraClient

BASE = "https://api.local.runkora.io"


def client() -> KoraClient:
    return KoraClient(BASE, "tok")


@respx.mock
def test_probe_claude_passes_on_a_real_message():
    route = respx.post(f"{BASE}/v1/messages").mock(
        return_value=httpx.Response(
            200, json={"type": "message", "content": [{"type": "text", "text": "ready"}]}
        )
    )
    assert probe_claude(client(), "anthropic/claude-haiku-5-5") == (True, "ready")
    assert b'"max_tokens":8' in route.calls[0].request.read()


@respx.mock
def test_probe_claude_fails_on_a_200_carrying_an_error_body():
    respx.post(f"{BASE}/v1/messages").mock(
        return_value=httpx.Response(
            200, json={"type": "error", "error": {"message": "upstream provider returned an error"}}
        )
    )
    ok, detail = probe_claude(client(), "anthropic/claude-haiku-5-5")
    assert not ok
    assert "upstream provider returned an error" in detail


@respx.mock
def test_probe_claude_fails_with_the_body_on_an_http_error():
    respx.post(f"{BASE}/v1/messages").mock(
        return_value=httpx.Response(503, json={"error": {"message": "provider_error"}})
    )
    ok, detail = probe_claude(client(), "anthropic/claude-haiku-5-5")
    assert not ok
    assert "503" in detail and "provider_error" in detail


@respx.mock
def test_probe_openai_passes_on_a_choice_with_content():
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ready"}}]})
    )
    assert probe_openai(client(), "openai/gpt-5-4") == (True, "ready")


@respx.mock
def test_probe_openai_fails_without_choices():
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"error": {"message": "no deployment"}})
    )
    ok, detail = probe_openai(client(), "openai/gpt-5-4")
    assert not ok and "no deployment" in detail


def mock_platform(environment_slugs: tuple[str, ...]) -> None:
    ids = [f"anthropic/{n}" for n in ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-fable-5-1")]
    ids += ["openai/gpt-5-5", "openai/gpt-5-4"]
    respx.get(f"{BASE}/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": i} for i in ids]})
    )
    respx.get(f"{BASE}/v1/catalog/pricing").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    environments = [{"slug": slug} for slug in environment_slugs]
    respx.get(f"{BASE}/api/v1/environments").mock(
        return_value=httpx.Response(200, json={"environments": environments})
    )
    respx.post(f"{BASE}/v1/messages").mock(
        return_value=httpx.Response(200, json={"type": "message", "content": [{"text": "ready"}]})
    )
    respx.post(f"{BASE}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ready"}}]})
    )


@respx.mock
def test_checks_expect_every_environment():
    mock_platform(("node-web",))
    results = {name: ok for ok, name in api_checks(client())}
    assert results["environment node-web present"]
    assert not results["environment python-tools present"]


@respx.mock
def test_api_checks_cover_models_prices_environment_and_one_live_call_per_provider():
    mock_platform(("node-web", "python-tools"))
    results = {name: ok for ok, name in api_checks(client())}
    assert results["model openai/gpt-5-4 listed"]
    assert not results["every demo model has a price"]
    assert results["environment node-web present"]
    assert results["anthropic/claude-haiku-5-5 answers through the gateway"]
    assert results["openai/gpt-5-4 answers through the gateway"]
