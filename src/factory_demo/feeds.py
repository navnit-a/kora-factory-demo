import json

from factory_demo.practices import REPO_PATH

DATA_DIR = "public/data/"
TRAINS_PATH = f"{DATA_DIR}trains.json"
LUNCH_PATH = f"{DATA_DIR}lunch.json"
TRAINS_BRANCH = "agent-trains"
LUNCH_BRANCH = "agent-lunch"
DATA_BRANCHES = (TRAINS_BRANCH, LUNCH_BRANCH)
PRODUCT_REPO = REPO_PATH.removeprefix("repos/")

TRAINS_EXAMPLE = json.dumps(
    {
        "updated": "2026-10-27T07:45:00+11:00",
        "status": "disruptions",
        "lines": [
            {
                "line": "T1 North Shore & Western Line",
                "summary": "Trains run less often between Hornsby and Berowra.",
            }
        ],
        "more": 2,
        "attribution": "Data: Transport for NSW Open Data, CC BY 4.0",
    },
    indent=2,
)

LUNCH_EXAMPLE = json.dumps(
    {
        "updated": "2026-10-27T11:30:00+11:00",
        "place": "Sydney Masonic Centre",
        "picks": [
            {
                "name": "Example Noodle Bar",
                "kind": "restaurant",
                "cuisine": "vietnamese",
                "distance_m": 120,
                "street": "Example Street",
                "lat": -33.8781,
                "lon": 151.2043,
                "reason": "closest hot meal",
            },
            {
                "name": "Example Cafe",
                "kind": "cafe",
                "cuisine": "coffee_shop",
                "distance_m": 210,
                "street": "Example Lane",
                "lat": -33.8769,
                "lon": 151.2055,
                "reason": "quick coffee and a sandwich",
            },
            {
                "name": "Example Thai",
                "kind": "restaurant",
                "cuisine": "thai",
                "distance_m": 340,
                "street": "Example Road",
                "lat": -33.8790,
                "lon": 151.2031,
                "reason": "a sit-down lunch",
            },
        ],
        "attribution": "Data: OpenStreetMap contributors, ODbL",
    },
    indent=2,
)

TRAINS_SHAPE = f"""`{TRAINS_PATH}` is one JSON object with exactly these fields:
- `updated`: when the data is from, ISO 8601 with its offset.
- `status`: `normal` or `disruptions`, as the tool returned it.
- `lines`: one object per disruption, in the tool's order, each with `line` (the line's name) and
  `summary` (the disruption in plain words); an empty list when the status is `normal`.
- `more`: an integer, the further updates the tool counted.
- `attribution`: the tool's attribution line, exactly as it returned it.
The example's values are illustrative; write the tool's.
```json
{TRAINS_EXAMPLE}
```"""

LUNCH_SHAPE = f"""`{LUNCH_PATH}` is one JSON object with exactly these fields:
- `updated`: when the data is from, ISO 8601 with its offset.
- `place`: the place name from your run message.
- `picks`: exactly three objects, the three you chose, each with `name`, `kind`, `cuisine`,
  `distance_m` (an integer), `street`, `lat` and `lon` (numbers) copied from the tool, and
  `reason`, a short phrase on why it is a good pick.
- `attribution`: the tool's attribution line, exactly as it returned it.
The example's values are illustrative; write the tool's.
```json
{LUNCH_EXAMPLE}
```"""


def data_pr_title(agent: str, day: str) -> str:
    return f"data: {agent} {day}"


def publish_steps(branch: str, path: str, title: str) -> str:
    return f"""1. Read the tip of `main` with
   `gh api {REPO_PATH}/git/ref/heads/main --jq .object.sha`; call it `<main sha>`.
2. Reset `{branch}` to it with
   `gh api -X PATCH {REPO_PATH}/git/refs/heads/{branch} -f sha='<main sha>' -F force=true`. When
   that returns 422 or 404 the branch does not exist yet: create it with
   `gh api -X POST {REPO_PATH}/git/refs -f ref=refs/heads/{branch} -f sha='<main sha>'`.
3. Read the file's current sha with
   `gh api '{REPO_PATH}/contents/{path}?ref={branch}' --jq .sha`; call it `<file sha>`. A 404
   means the file does not exist yet and there is no `<file sha>`.
4. Write the JSON to a local file through a heredoc with a quoted delimiter,
   `cat > data.json <<'JSON'`, then upload it with
   `gh api -X PUT {REPO_PATH}/contents/{path} -f branch={branch} -f message='{title}'
   -f content="$(base64 -w0 < data.json)" -f sha='<file sha>'`, leaving out `-f sha` when
   step 3 found no file.
5. Look for an open pull request with
   `gh pr list --repo {PRODUCT_REPO} --head {branch} --state open --json number`. When
   the list is empty, open one with
   `gh api -X POST {REPO_PATH}/pulls -f base=main -f head={branch} -f title='{title}'
   -f body='Data refresh by the {branch} agent. Only {path} changes.'`.
6. The `updated` field is the tool's `as_of` when it has one, otherwise this run's time in UTC,
   written with its offset. Values from tool output never go into a shell command unquoted:
   single-quote every sha and every value copied from a tool, and write the JSON through the
   heredoc file, never inline."""
