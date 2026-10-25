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


def test_publish_steps_number_under_an_outer_step():
    steps = feeds.publish_steps(feeds.TRAINS_BRANCH, feeds.TRAINS_PATH, "t", "4.")
    assert [line.split()[0] for line in steps.splitlines() if line[:1].isdigit()] == [
        f"4.{n}." for n in range(1, 7)
    ]
    assert "\n     `gh api" in steps
    assert "step 4.3 found no file" in " ".join(steps.split())


def test_publish_steps_create_the_branch_only_when_it_is_missing():
    steps = " ".join(feeds.publish_steps(feeds.LUNCH_BRANCH, feeds.LUNCH_PATH, "t").split())
    assert "returns 422 'Reference does not exist' or 404" in steps


def test_publish_steps_validate_the_data_file_before_the_upload():
    steps = " ".join(feeds.publish_steps(feeds.TRAINS_BRANCH, feeds.TRAINS_PATH, "t").split())
    upload = steps.index(f"-X PUT {feeds.REPO_PATH}/contents/")
    assert "`python3 -m json.tool data.json > /dev/null`" in steps
    assert steps.index("python3 -m json.tool") < upload
    assert "if it fails, stop: do not upload, and reply with the error" in steps


def test_data_pr_rule_fetches_mergeable_before_checking_it():
    rule = " ".join(feeds.DATA_PR_RULE.split())
    assert "--json files,changedFiles,mergeable`" in rule
    assert rule.index("--json files,changedFiles,mergeable") < rule.index("`mergeable` is not")
