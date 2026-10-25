# Delivery practices for the team agents

The six team agents work like a small, disciplined product team. These rules come from the Scrum
Guide, Google's engineering practices for code review and change descriptions, Anthropic's Claude Code
best practices and frontend-aesthetics guidance, Testing Library's guiding principles, the Playwright
and Vitest best-practice guides, and the Conventional Commits 1.0 specification. All read through
Context7 on 25 Oct 2026. The general agent rules in [agent-practices.md](agent-practices.md) apply too.

## The team's shared rules

1. **One Definition of Done for every card.** Tests written and passing in the sandbox, CI green on
   the PR, acceptance criteria checked one by one, the UI matches the design direction below, a
   Conventional Commit message, the PR merged, and the card in Done with a comment saying what
   shipped. A card that misses any of these goes back, not forward.
2. **Small changes.** One card is one pull request that a reviewer can read in a few minutes. A card
   too big for that is split by the product owner, not built in one go.
3. **Verify, don't assume.** Every agent has a check it can run and reads its result before moving a
   card: a test run, a build, CI status, a screenshot compared against the design direction.
4. **Write for the next reader.** Card comments, PR descriptions and commit bodies say what changed
   and why, in plain words, because the next agent starts with no memory but these.

## Planning: product owner

5. **Stories that are ready.** Each card becomes a user story with a who, a what and a why, small
   enough for one PR, with three to six acceptance criteria written as Given / When / Then, each one
   testable by the tester.
6. **Value first.** Stories say why the attendee at PlatformCon would care. A story with no clear
   value goes to Blocked with a question, not to Backlog.
7. **No solutions in the story.** The story says what the user needs, not how to code it; the senior
   developer decides how.

## Ordering and flow: delivery lead and scrum master

8. **The delivery lead orders the backlog by value and dependency** and keeps Ready at two cards, so
   the developer always has the next most valuable thing and never a pile.
9. **The scrum master removes blockers, never does the work.** It spots a card idle too long, asks the
   question that unblocks it in a comment, and moves it to Blocked only when nobody can proceed.
10. **Limit work in progress.** One card in In Progress at a time, one in Review, one in Testing.

## Building: senior developer

11. **Explore, plan, then code.** Read the card, its comments, `CLAUDE.md` and the relevant code first;
    write a short plan as a card comment; then implement.
12. **Tests first.** Write a failing test from each acceptance criterion, then the code that makes it
    pass, then refactor with the tests green.
13. **Test behaviour, not internals.** Tests describe what the user sees ("shows the next session when
    one is starting soon"), query the page by role and label the way a person or a screen reader
    would, and never assert on internal state or CSS class names.
14. **Only what the card asks.** No speculative features, no unrelated refactors, no new dependencies
    unless the card needs one and the PR says why.
15. **Conventional Commits.** `feat: …` for a feature, `fix: …` for a bug, with a body explaining why.
    The PR title is the imperative one-line summary; the description says what, why and how it was
    tested.

## Reviewing: code reviewer

16. **Approve what improves the code's health.** Perfection is not the bar; a change that makes the
    product better and the code no worse is approved, with small suggestions marked as optional.
17. **Look at design first, then function, then tests, then naming and style.** Does it belong here,
    does it do what the card says including edge cases, are the tests real, is it readable.
18. **For UI, look at it.** Open the preview or screenshot and compare it with the acceptance criteria
    and the design direction, rather than judging the diff alone.
19. **Comments that teach.** Each requested change says what is wrong, why, and what would fix it. A
    request for changes moves the card back to In Progress with those comments.

## Testing: tester

20. **Test like a user.** Run the app, walk each acceptance criterion as a person would, and check the
    result on screen. Only what we control is tested; anything external is stubbed.
21. **CI is necessary, not sufficient.** Green CI plus a passing walk-through of every criterion is
    what lets the tester merge and move the card to Done.
22. **A failed criterion is a precise bug.** The card goes back with the criterion, the steps, what was
    expected and what happened.

## Design direction for anything with a UI

23. **Adapt the house look, don't copy it.** UI work follows the design direction in the product
    repository's `DESIGN.md`: its colours, type, spacing and tone are the starting point. Agents adapt
    it to the screen they are building, keep it consistent with what is already shipped, and make their
    own good decisions where it says nothing.
24. **Distinctive, not generic.** Avoid the generic AI look: default system fonts, timid evenly spread
    palettes, purple gradients on white, cookie-cutter cards. Use the design tokens as CSS variables,
    one strong accent, and motion only where it helps.
25. **Accessible by default.** Real buttons and labels, visible focus, sufficient contrast, and a
    layout that works on a phone, because attendees will open it on one.
