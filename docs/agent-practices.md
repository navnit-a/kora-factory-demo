# Agent and tool practices for the kora factory

Every agent prompt and tool server in this repo follows these rules. Sources: Anthropic's "Building
effective agents", "Writing effective tools for agents", "Effective harnesses for long-running agents"
and the Claude 4 prompting guide; the Claude Agent SDK permission and subagent docs; the FastMCP tool
docs. All read through Context7 on 25 Oct 2026.

## Shape of the system

1. **Workflow outside, agent inside.** The board is a fixed workflow: each agent owns one list and a
   fixed set of moves. The model decides how to do the work on a card, never which lane it belongs to.
   Predictable steps stay in code paths and tool rules, not in the model's judgement.
2. **One card per run.** A run picks up at most one card, finishes it or hands it back, and ends. Doing
   several at once is the failure mode the long-running-agent study saw most.
3. **The evaluator loop is bounded.** Reviewer and developer form an evaluator-optimizer pair. A card
   that bounces back twice goes to Blocked with the reasons, instead of a third attempt.

## Prompts

4. **Say why.** Each prompt opens with the agent's role on the team and why its lane matters, because
   Claude follows instructions better when it knows their purpose.
5. **Say what to do, then how to stop.** Every prompt ends with an explicit stopping rule: what done
   looks like, what to do when the list is empty (end the run without calling more tools), and what to
   do when stuck (move to Blocked with a comment).
6. **Memory lives outside the context.** Each run starts fresh. The card's comments and the repo's git
   log are the progress notes: the agent reads them first and writes one comment before it ends saying
   what it did, what it checked and what is left.
7. **Verify before moving right.** Nothing moves forward until it was checked end to end: tests run in
   the sandbox, CI green on the PR, or the acceptance criteria compared line by line.
8. **Leave a clean state.** Code is committed and pushed, the PR is open or merged, the card is in the
   right list. A half-done card goes back with a comment, never left in place silently.
9. **Card text is data, not instructions.** Titles, descriptions and comments are written by people
   and other agents. Prompts tell the agent to treat them as the task to work on, never as orders that
   change its role, tools or rules.

## Tools

10. **Few tools, shaped like tasks.** A tool does one step of the job, not one API endpoint. Moving a
    card always carries the reason, so `trello_move_card` takes `reason` and writes the comment itself.
11. **Namespaced names.** `trello_*`, `telegram_*`, `transport_*`, `places_*`, so tools from different
    servers never blur together.
12. **Unambiguous, typed parameters.** `card_id`, `list_name`, `to_list`, with a description on every
    parameter and a closed set of values where there is one (the eight list names).
13. **Small, meaningful responses.** Return names and short text, not raw API objects. Lists take a
    `limit` with a small default. Long text is truncated with a note saying how to get the rest.
14. **Errors say what to do next.** "No list named 'Revew'. Lists are: Ideas, Backlog, ..." beats a
    stack trace. Errors are tool errors the model can read, not crashes.
15. **Annotations tell the truth.** Read tools are `readOnlyHint`; moves and comments are idempotent
    where repeating them is harmless; nothing in this demo is destructive, so no delete tools exist.

## Guardrails

16. **Least privilege twice.** kora grants each agent only its own tool scopes, and the agent's prompt
    names only those tools. The reviewer cannot create cards; the trains agent cannot touch Trello.
17. **Hard limits.** Every agent has a per-run budget, kora's loop guardrails on, and one run at a time
    per schedule.
18. **Evaluate before filming.** Each agent runs once against a fixture card before the video, and its
    result is checked against what its lane should produce.
