from fastmcp.exceptions import ToolError

from factory_tools.lists import canonical_name, lists_sentence


def canonical_ids(lists: list[dict]) -> dict[str, str]:
    matched = [(canonical_name(item["name"]), item["id"]) for item in lists]
    return dict(reversed([(name, list_id) for name, list_id in matched if name]))


def lane_of(lists: list[dict], list_id: object) -> str | None:
    names = {found: name for name, found in canonical_ids(lists).items()}
    return names.get(list_id) if isinstance(list_id, str) else None


def list_id(lists: list[dict], list_name: str) -> str:
    ids = canonical_ids(lists)
    if list_name not in ids:
        board = ", ".join(sorted(item["name"] for item in lists)) or "no lists"
        raise ToolError(
            f"No list named '{list_name}' on the board. The board has: {board}. "
            f"The factory expects: {lists_sentence().removeprefix('Lists are: ')}"
        )
    return ids[list_name]
