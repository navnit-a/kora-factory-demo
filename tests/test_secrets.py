import pytest
import yaml

from factory_demo.secrets import read_env, render_secret


def test_read_env_keeps_value_after_first_equals(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# c\nA=1\nB=x=y \n\nC=\n")
    assert read_env(str(env)) == {"A": "1", "B": "x=y ", "C": ""}


def test_render_secret_maps_keys_and_labels():
    out = render_secret(
        "azure-ailabs",
        "kora-system",
        {"K": "s3cr3t"},
        {"apiKey": "K"},
        {"runkora.io/inference-provider": "true"},
    )
    assert "kind: Secret" in out
    assert "name: azure-ailabs" in out
    assert "namespace: kora-system" in out
    assert 'runkora.io/inference-provider: "true"' in out
    assert 'apiKey: "s3cr3t"' in out


def test_render_secret_missing_env_var_raises():
    with pytest.raises(KeyError, match="MISSING"):
        render_secret("x", "ns", {}, {"apiKey": "MISSING"})


@pytest.mark.parametrize("value", ["x=y ", "a #b", "123", "yes", "", "rg-name  ", 'q"uote'])
def test_rendered_secret_parses_back_to_the_exact_string(value):
    out = render_secret("s", "ns", {"V": value}, {"key": "V"})
    assert yaml.safe_load(out)["stringData"]["key"] == value
