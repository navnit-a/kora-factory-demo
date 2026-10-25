from factory_demo import feeds


def test_publish_steps_reset_the_branch_to_main():
    steps = feeds.publish_steps(feeds.TRAINS_BRANCH, feeds.TRAINS_PATH, "data: trains 2026-10-27")
    assert "git/refs/heads/agent-trains" in steps and "force=true" in steps
    assert steps.index("git/ref/heads/main") < steps.index("contents/public/data/trains.json")


def test_publish_steps_open_a_pull_request_only_when_none_is_open():
    steps = feeds.publish_steps(feeds.LUNCH_BRANCH, feeds.LUNCH_PATH, "data: lunch 2026-10-27")
    assert "--head agent-lunch --state open" in steps
    assert "-f base=main -f head=agent-lunch" in steps


def test_shapes_name_every_field_the_planner_parses():
    assert all(
        key in feeds.TRAINS_SHAPE for key in ("updated", "status", "lines", "more", "attribution")
    )
    assert all(
        key in feeds.LUNCH_SHAPE
        for key in ("updated", "place", "picks", "lat", "lon", "reason", "attribution")
    )


def test_data_pr_title():
    assert feeds.data_pr_title("trains", "2026-10-27") == "data: trains 2026-10-27"
