from factory_demo.ideas import IDEAS, seed_ideas
from tests.test_evaluation_runner import FakeTrello


def test_seven_ideas_each_with_a_title_and_two_sentences():
    assert len(IDEAS) == 7
    for title, idea in IDEAS:
        assert title and title[0].isupper()
        assert idea.count(". ") + idea.endswith(".") >= 2


async def test_seed_ideas_skips_existing_titles():
    first_title = IDEAS[0][0]
    trello = FakeTrello(
        {"a" * 24: {"title": first_title, "list": "Ideas", "description": "", "comments": ()}}
    )
    created = await seed_ideas(trello)
    assert len(created) == 6
    assert first_title not in created
    titles = [c["title"] for c in trello.cards.values()]
    assert titles.count(first_title) == 1
    assert len(titles) == 7


async def test_seeding_twice_creates_nothing_new():
    trello = FakeTrello()
    await seed_ideas(trello)
    assert await seed_ideas(trello) == ()
