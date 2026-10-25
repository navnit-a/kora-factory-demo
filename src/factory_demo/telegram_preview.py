from datetime import datetime
from html.parser import HTMLParser

TEXT_CLASS = "tgme_widget_message_text"


class _PreviewReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.posts: list[tuple[str, str]] = []
        self.text: list[str] = []
        self.when = ""
        self.depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "div" and values.get("data-post"):
            self._close()
        if self.depth and tag == "div":
            self.depth += 1
        elif tag == "div" and TEXT_CLASS in (values.get("class") or "").split():
            self.depth = 1
        if self.depth and tag == "br":
            self.text.append("\n")
        if tag == "time" and values.get("datetime") and not self.when:
            self.when = values["datetime"] or ""

    def handle_endtag(self, tag: str) -> None:
        if self.depth and tag == "div":
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.text.append(data)

    def close(self) -> None:
        super().close()
        self._close()

    def _close(self) -> None:
        if self.text and self.when:
            self.posts.append(("".join(self.text).strip(), self.when))
        self.text, self.when, self.depth = [], "", 0


def parse_posts(html: str, after: datetime) -> list[str]:
    reader = _PreviewReader()
    reader.feed(html)
    reader.close()
    return [text for text, when in reader.posts if datetime.fromisoformat(when) > after]
