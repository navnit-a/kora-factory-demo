from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentSpec:
    slug: str
    name: str
    description: str
    sandbox_image: str
    cpu: str
    memory: str
    disk: str
    egress_hosts: tuple[str, ...]


NODE_WEB = EnvironmentSpec(
    slug="node-web",
    name="Node web",
    description="Node 24 with npm for the PlatformCon Day Planner repository (Vite, Vitest).",
    sandbox_image="kora-node",
    cpu="1",
    memory="2Gi",
    disk="8Gi",
    egress_hosts=(
        "registry.npmjs.org",
        "github.com",
        "api.github.com",
        "codeload.github.com",
        "objects.githubusercontent.com",
    ),
)


def environment_request(spec: EnvironmentSpec) -> dict:
    return {
        "slug": spec.slug,
        "name": spec.name,
        "description": spec.description,
        "sandbox_image": spec.sandbox_image,
        "size": {"cpu": spec.cpu, "memory": spec.memory, "disk": spec.disk},
        "egress_hosts": list(spec.egress_hosts),
        "connectors": [],
    }
