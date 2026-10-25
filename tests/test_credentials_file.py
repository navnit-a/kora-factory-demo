import os

import pytest

from factory_demo.kora_api import load_client


def test_load_client_refuses_group_or_world_readable_token(tmp_path, monkeypatch):
    creds = tmp_path / "creds.json"
    creds.write_text('{"access_token": "abc"}')
    os.chmod(creds, 0o644)
    monkeypatch.setenv("KORA_CA_FILE", str(creds))
    with pytest.raises(PermissionError, match="chmod 600"):
        load_client(str(creds))


def test_load_client_accepts_owner_only_token(tmp_path, monkeypatch):
    creds = tmp_path / "creds.json"
    creds.write_text('{"access_token": "abc"}')
    os.chmod(creds, 0o600)
    monkeypatch.setenv("KORA_CA_FILE", str(creds))
    assert load_client(str(creds)).token == "abc"
