from datetime import UTC, datetime
from pathlib import Path

from factory_demo.telegram_preview import parse_posts

HTML = (Path(__file__).parent / "fixtures" / "telegram_preview.html").read_text()


def test_parse_posts_keeps_only_newer_posts():
    posts = parse_posts(HTML, datetime(2026, 10, 25, 8, 0, tzinfo=UTC))
    assert posts == ["Lunch near Sydney Masonic Centre\nData: © OpenStreetMap contributors, ODbL"]


def test_parse_posts_reads_every_post_and_line_breaks():
    posts = parse_posts(HTML, datetime(2026, 10, 25, 0, 0, tzinfo=UTC))
    assert len(posts) == 2
    assert posts[0].splitlines()[1] == "All Sydney Trains lines are running normally."


def test_parse_posts_of_an_empty_page():
    assert parse_posts("<html></html>", datetime(2026, 1, 1, tzinfo=UTC)) == []
