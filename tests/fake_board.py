from factory_tools.trello.look import LABELS, LANE_STICKERS


def card(lane: str, title: str, **fields) -> dict:
    return {
        "list": lane,
        "title": title,
        "description": "",
        "comments": (),
        "cover": None,
        "stickers": (),
        "labels": (),
        "checklist": (),
        **fields,
    }


class FakeBoard:
    def __init__(self, labels: dict[str, dict], cards: dict[str, dict]):
        self.labels = dict(labels)
        self.cards = dict(cards)
        self.writes: tuple[tuple, ...] = ()

    def _write(self, *call) -> None:
        self.writes = (*self.writes, call)

    def _update(self, card_id: str, **fields) -> None:
        self.cards = {**self.cards, card_id: {**self.cards[card_id], **fields}}

    async def label_records(self) -> dict[str, dict]:
        return {label_id: dict(label) for label_id, label in self.labels.items()}

    async def rename_label(self, label_id: str, name: str) -> None:
        self._write("rename_label", label_id, name)
        self.labels = {**self.labels, label_id: {**self.labels[label_id], "name": name}}

    async def ensure_label(self, name: str) -> str:
        found = next((i for i, label in self.labels.items() if label["name"] == name), None)
        if found:
            return found
        self._write("ensure_label", name)
        label_id = f"lab-{len(self.labels)}"
        self.labels = {**self.labels, label_id: {"name": name, "color": LABELS[name]}}
        return label_id

    async def cards_in(self, list_name: str, limit: int) -> list[dict]:
        return [
            {"id": card_id, "title": c["title"], "list": c["list"]}
            for card_id, c in self.cards.items()
            if c["list"] == list_name
        ][:limit]

    def names(self, card_id: str) -> tuple[str, ...]:
        return tuple(self.labels[label_id]["name"] for label_id in self.cards[card_id]["labels"])

    async def card_look(self, card_id: str) -> dict:
        c = self.cards[card_id]
        labels = tuple(dict(self.labels[label_id]) for label_id in c["labels"])
        return {"cover": c["cover"], "description": c["description"], "labels": labels}

    async def card(self, card_id: str) -> dict:
        texts = self.cards[card_id]["comments"]
        return {"id": card_id, "comments": [{"when": "", "text": text} for text in texts]}

    async def stickers(self, card_id: str) -> list[dict]:
        images = self.cards[card_id]["stickers"]
        return [{"id": f"s{n}", "image": image} for n, image in enumerate(images)]

    async def set_cover(self, card_id: str, color: str | None) -> None:
        self._write("set_cover", card_id, color)
        self._update(card_id, cover=color)

    async def set_lane_sticker(self, card_id: str, image: str | None) -> None:
        self._write("set_lane_sticker", card_id, image)
        kept = tuple(s for s in self.cards[card_id]["stickers"] if s not in LANE_STICKERS)
        self._update(card_id, stickers=(*kept, *((image,) if image else ())))

    async def add_label(self, card_id: str, name: str) -> dict:
        self._write("add_label", card_id, name)
        label_id = await self.ensure_label(name)
        self._update(card_id, labels=(*self.cards[card_id]["labels"], label_id))
        return {"id": card_id, "label": name, "added": True}

    async def checklist_items(self, card_id: str) -> tuple[tuple[str, str], ...]:
        return tuple((item, "incomplete") for item in self.cards[card_id]["checklist"])

    async def add_checklist(self, card_id: str, items: tuple[str, ...]) -> dict:
        self._write("add_checklist", card_id, items)
        self._update(card_id, checklist=items)
        return {"id": card_id, "checklist_items": len(items)}
