from datetime import UTC, datetime, timedelta

from factory_tools.places.cache import cache_key, read_cached, write_cached

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


def test_round_trip_marks_when_it_was_stored(tmp_path, monkeypatch):
    monkeypatch.setenv("PLACES_CACHE_DIR", str(tmp_path))
    key = cache_key(-33.8781, 151.2077, 600, 6)
    write_cached(key, {"places": [{"name": "Corner Cafe"}]}, NOW)
    assert read_cached(key, NOW + timedelta(hours=1)) == {
        "places": [{"name": "Corner Cafe"}],
        "cached_at": "2026-10-25T09:00:00+00:00",
    }


def test_an_answer_older_than_a_day_is_not_served(tmp_path, monkeypatch):
    monkeypatch.setenv("PLACES_CACHE_DIR", str(tmp_path))
    key = cache_key(-33.8781, 151.2077, 600, 6)
    write_cached(key, {"places": []}, NOW)
    assert read_cached(key, NOW + timedelta(hours=25)) is None


def test_a_corrupt_or_missing_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("PLACES_CACHE_DIR", str(tmp_path))
    assert read_cached("missing", NOW) is None
    (tmp_path / "broken.json").write_text("{not json")
    assert read_cached("broken", NOW) is None
