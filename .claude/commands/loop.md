---
description: Run BMAD's dev → code-review → correct-course loop autonomously, up to 3 cycles or until clean.
---

# /loop — autonomous Dev ↔ Review iteration

**Argument**: `$ARGUMENTS` (the story / task identifier, e.g. `story-1.1`, or a one-line description of what to implement)

## Goal

Run multiple BMAD agent skills in a single response, **without stopping for user confirmation between them**, until either:

- the code-review pass finds nothing to flag, or
- 3 full cycles have elapsed, or
- you (Claude) judge a human decision is genuinely required (mention it in the final report instead of asking)

The user wants to read **one final summary**, not be ping-ponged between agents.

## Cycle structure

For each cycle, in one continuous response:

### Phase 1 — Implementation (Dev hat)

Use the **`bmad-dev-story`** skill if the argument names a story; otherwise treat the argument as the task description and apply the BMAD developer agent persona (file `_bmad/bmm/...` / `.claude/skills/bmad-agent-dev/SKILL.md`).

- If a story file exists under the BMAD-managed implementation folder, read it first.
- Make the smallest set of edits that satisfies the story's acceptance criteria.
- Run the project's test command if `Taskfile.yml` or `package.json`/`pyproject.toml` make it obvious which one. Skip silently if there is no test setup yet (this is a template-derived project; tests may not exist on cycle 1).

### Phase 2 — Review (QA / code-reviewer hat)

Use the **`bmad-code-review`** skill (file `.claude/skills/bmad-code-review/SKILL.md`).

Be strict. Look specifically for:

- **Acceptance criteria** not actually met by the code (read the story again).
- **Tests missing** for new behavior, or tests that only cover the happy path.
- **Edge cases** unhandled: null / empty / oversized inputs; off-by-one; concurrent access if relevant.
- **Naming** — does a reader cold understand the identifier? If not, flag.
- **Risky edits** — anything that touched a sensitive area (auth, secrets, schema, payments, deploy config) without the user explicitly asking.
- **Dead code or commented-out blocks** introduced by this cycle.
- **Security obvious-misses** — no secrets logged, no `eval`, no shell injection, no SQL string concatenation, no unbounded recursion.

If review finds **0 issues**, declare convergence and skip to Final Report.

### Phase 3 — Apply review (correct-course)

Use **`bmad-correct-course`** if available, otherwise the Dev hat again.

Apply every Critical and High finding. Apply Medium findings unless they would balloon the diff; in that case list them as deferred work.

Do **not** ask the user "which findings to apply?" — apply them yourself. The user opted into autonomous mode.

## After all cycles

Produce **one** final report (don't interleave it with cycle output). Sections:

### Cycles run

For each cycle (1 … N):
- 1-line "Dev did:" summary
- 1-line "Review flagged: X critical / Y high / Z medium / W info"
- 1-line "Applied: yes / partial / no"

### Final state

- Files touched (one line each)
- Tests added or changed (one line each)
- Open issues that did NOT get applied this run, with reason (one line each)

### Human-decision items

The **only** time you ask the user something is for items where the right answer genuinely requires their judgment (e.g. "should we expose this as a public API?", "should this rate limit be 60 or 600?"). List them at the very end of the report so the user can answer **all at once**, not interleaved with code changes.

## Rules

- **Do not** stop between phases for user input.
- **Do not** ask permission for individual edits (`acceptEdits` mode is on).
- **Do not** loop past 3 cycles. If still divergent after 3, stop and report what's blocking convergence.
- **Do not** apply edits to: `CLAUDE.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, `_bmad/` core files, `.claude/hooks/block_dangerous_commands.py`. These are foundation files; if you think one needs changing, list it in Human-decision items instead.
- **Do not** run `git push`. The user does the push.
- **Do** run `git status` / `git diff` between phases to confirm the state.
- **Do** keep cycle output terse — the value to the user is the **final report**, not the play-by-play.

## Inputs

If `$ARGUMENTS` is empty, ask the user once: "Which story or task? (e.g. `story-1.1`, or a sentence)". Then proceed without further prompts.
