from factory_demo.kora_api import KoraAuthError

MODELS = [{"id": "anthropic/claude-haiku-5-5"}, {"id": "anthropic/claude-sonnet-5-5"}]
ENVIRONMENTS = ({"id": "env-1", "slug": "node-web"},)


class FakeKora:
    def __init__(
        self,
        fail_patch_for: str | None = None,
        cap: dict | None = None,
        environments: tuple[dict, ...] = ENVIRONMENTS,
    ):
        self.agents: tuple[dict, ...] = ()
        self.triggers: tuple[dict, ...] = ()
        self.patches: tuple[tuple[str, dict], ...] = ()
        self.cap = cap
        self.cap_sets = 0
        self.fail_patch_for = fail_patch_for
        self.environments = environments

    def list_models(self):
        return MODELS

    def list_environments(self):
        return list(self.environments)

    def list_agents(self):
        return list(self.agents)

    def create_agent(self, request):
        agent = {**request, "id": f"at-{request['slug']}"}
        self.agents = (*self.agents, agent)
        return agent

    def update_agent(self, agent_id, patch):
        self.agents = tuple({**a, **patch} if a["id"] == agent_id else a for a in self.agents)
        return next(a for a in self.agents if a["id"] == agent_id)

    def list_triggers(self):
        return list(self.triggers)

    def create_trigger(self, request):
        trigger = {**request, "id": f"t-{len(self.triggers)}", "enabled": True}
        self.triggers = (*self.triggers, trigger)
        return trigger

    def update_trigger(self, trigger_id, patch):
        name = next(t["name"] for t in self.triggers if t["id"] == trigger_id)
        if name == self.fail_patch_for:
            raise KoraAuthError("kora token rejected")
        self.patches = (*self.patches, (trigger_id, patch))
        self.triggers = tuple({**t, **patch} if t["id"] == trigger_id else t for t in self.triggers)
        return next(t for t in self.triggers if t["id"] == trigger_id)

    def get_tenant_budget(self):
        return self.cap

    def set_tenant_budget(self, limit_usd, reset_cadence):
        self.cap = {"limit_usd": limit_usd, "reset_cadence": reset_cadence}
        self.cap_sets += 1
        return self.cap
