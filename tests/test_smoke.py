from factory_demo.smoke import build_smoke_agent, pick_model


def test_smoke_agent_body_is_cheap_and_autonomous():
    body = build_smoke_agent("anthropic/claude-haiku-5-5", "env-1")
    assert body["slug"] == "smoke"
    assert body["framework"] == "claude-code"
    assert body["identity_mode"] == "autonomous"
    assert body["model_id"] == "anthropic/claude-haiku-5-5"
    assert body["budget"] == {"per_run_limit_usd": 0.2}
    assert body["environments"] == [{"environment_id": "env-1", "is_default": True}]
    assert body["max_concurrent_runs_per_pod"] == 1


def test_smoke_agent_declares_no_inference_scopes_kora_derives_them():
    body = build_smoke_agent("anthropic/claude-haiku-5-5", "env-1")
    assert not [s for s in body.get("grant_scopes", []) if s.startswith("inference:")]


def test_pick_model_matches_by_deployment_name_suffix():
    models = [{"id": "anthropic/claude-sonnet-5-5"}, {"id": "anthropic/claude-haiku-5-5"}]
    assert pick_model(models, "claude-haiku-5-5") == "anthropic/claude-haiku-5-5"


def test_pick_model_raises_with_the_listed_ids_when_absent():
    import pytest

    with pytest.raises(LookupError, match="anthropic/claude-sonnet-5-5"):
        pick_model([{"id": "anthropic/claude-sonnet-5-5"}], "claude-haiku-5-5")
