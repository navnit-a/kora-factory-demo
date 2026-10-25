from pathlib import Path


def read_env(path: str) -> dict[str, str]:
    pairs = (
        line.split("=", 1)
        for line in Path(path).read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    return {key.strip(): value for key, value in pairs}


def render_secret(
    name: str,
    namespace: str,
    env: dict[str, str],
    keys: dict[str, str],
    labels: dict[str, str] | None = None,
) -> str:
    values = {secret_key: env[var] for secret_key, var in keys.items()}
    label_lines = [f'    {k}: "{v}"' for k, v in (labels or {}).items()]
    metadata = [f"  name: {name}", f"  namespace: {namespace}"]
    if label_lines:
        metadata = [*metadata, "  labels:", *label_lines]
    data_lines = [f"  {k}: {v}" for k, v in values.items()]
    return (
        "\n".join(
            [
                "apiVersion: v1",
                "kind: Secret",
                "metadata:",
                *metadata,
                "type: Opaque",
                "stringData:",
                *data_lines,
            ]
        )
        + "\n"
    )
