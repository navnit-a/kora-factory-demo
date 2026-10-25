import pytest

from factory_bridge.allowlist import allow, read_allowlist


def test_missing_allowlist_is_empty(tmp_path):
    assert read_allowlist(tmp_path / "ideas-allowlist") == {}


def test_lines_with_and_without_names(tmp_path):
    path = tmp_path / "ideas-allowlist"
    path.write_text("111 Navnit\n\n222\n333 Justin Smith\n")
    assert read_allowlist(path) == {111: "Navnit", 222: "", 333: "Justin Smith"}


@pytest.mark.parametrize("bad", ["abc Navnit", "-5 Navnit", "12a"])
def test_bad_line_names_its_number(tmp_path, bad):
    path = tmp_path / "ideas-allowlist"
    path.write_text(f"111 Navnit\n{bad}\n")
    with pytest.raises(ValueError, match="line 2"):
        read_allowlist(path)


def test_allow_appends_a_line_and_creates_the_folder(tmp_path):
    path = tmp_path / "generated" / "ideas-allowlist"
    allow(path, 111, "Navnit")
    allow(path, 222, "")
    assert path.read_text() == "111 Navnit\n222\n"
    assert read_allowlist(path) == {111: "Navnit", 222: ""}


def test_allow_keeps_a_name_on_one_line(tmp_path):
    path = tmp_path / "ideas-allowlist"
    allow(path, 111, "Nav\n999  Evil")
    assert read_allowlist(path) == {111: "Nav 999 Evil"}
