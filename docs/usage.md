# Using This Template

This template is the **base layer** for new Claude Code projects. It is **not** an application. After deriving a project from it, you choose the stack inside that project and let BMAD-METHOD drive the development loop.

## 1. What this template gives you

| Layer | What it is |
| --- | --- |
| [`CLAUDE.md`](../CLAUDE.md) | Karpathy-style 60-line behavioral baseline + one beginner sentence. Loaded by Claude Code on every session. |
| `.gitignore` / `.gitattributes` / `.editorconfig` / `LICENSE` | Basic hygiene. Cross-OS line endings, common ignore patterns, MIT license. |
| `.claude/hooks/block_dangerous_commands.py` | Blocks Claude from running `rm -rf`, force-pushing, reading `.env` / private keys, printing secret env vars. |
| `.claude/settings.json` | Registers the hook above and pre-approves ~80 read-mostly / build / test commands. |
| `.mcp.json` | Pre-wires two MCP servers: **[Context7](https://github.com/upstash/context7)** (live, version-specific docs for hundreds of libraries — React, Next.js, FastAPI, Django, … — so Claude doesn't hallucinate old APIs) and **[Sequential Thinking](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)** (Anthropic-maintained MCP for structured multi-step reasoning, complements BMAD's planning chain). Both are free, need no API key, and start on first session. |
| `.github/` | PR + Issue templates (`PULL_REQUEST_TEMPLATE.md`, `ISSUE_TEMPLATE/bug_report.md`, `ISSUE_TEMPLATE/feature_request.md`) so contributions follow a structure. Language-agnostic. |
| [`scripts/health-check.py`](../scripts/health-check.py) | **Self-verification script.** Cross-platform Python (no deps). Run `python scripts/health-check.py` after deriving the template, or anytime later, to confirm core files exist, JSON parses, MCP entries are declared, Playwright is staged, BMad is installed, runtime tools (Node/pnpm/npx/git) are on PATH, and the safety hook compiles. Exit code 0 = green, 1 = at least one FAIL. |
| `package.json` + `playwright.config.ts` + `e2e/` | **Playwright pre-staged** for frontend end-to-end tests. Run `pnpm install && pnpm e2e:install` to activate (one Chromium download). The placeholder spec is `test.skip`'d, so `pnpm e2e` passes on an empty template. If your project is backend-only / CLI-only, delete these three files. |
| **BMAD-METHOD** (installed at template-init time) | Provides the PM / Architect / Developer / QA / UX agents and the SDLC workflow that takes a feature from idea → PRD → architecture → stories → code → QA. |
| `docs/` (this folder) | The two documents you are reading right now. |

That's it. No business code. No CI/CD pipelines. No security workflows. No Tier 1.5 policies. By design.

## 2. How to start a new project from this template

### Step 1 — Create the new repo from the template

On GitHub:

1. Go to https://github.com/lordrance/claude-code-bmad-foundation
2. Click the green **Use this template** → **Create a new repository**
3. Give it a real name (e.g. `my-game-pilot`)
4. **Public or Private** — your call per project
5. **Include all branches**: unchecked (`main` is enough)

If you prefer the terminal:

```bash
gh repo create lordrance/<your-new-project> \
  --template lordrance/claude-code-bmad-foundation \
  --public \
  --clone
cd <your-new-project>
```

### Step 2 — Clone and run the health check

```bash
cd <your-new-project>
python scripts/health-check.py
```

This single command verifies ~20 things at once: every core file exists, every JSON parses, both MCP entries are declared, Playwright is staged, BMad is installed, all runtime tools (Python, Git, Node, pnpm, npx) are on PATH, and the safety hook compiles. End-of-output is a colored summary; **exit code 0 means green to proceed**. If you see any `FAIL` line, fix that first before touching anything else.

### Step 3 — Update README and LICENSE for the new project

The template ships with a README that describes the template itself. Replace it with one that describes your new project. Update the LICENSE copyright holder if needed.

### Step 4 — Configure GitHub settings for the new repo

`Use this template` copies the **files**, but it does **not** carry over these per-repo settings — you have to set them once in the new repo:

| What to set | Why it doesn't carry over | Where in GitHub UI |
| --- | --- | --- |
| **Description + topics** | GitHub policy; metadata is per-repo. | About panel (right side of repo main page) → ⚙ |
| **Branch protection on `main`** (optional for solo, recommended once collaborators join) | Not template-copied. | Settings → Rules → Rulesets → New ruleset |
| **Secret scanning + Push protection** | Defaults to ON for public repos; verify it is ON if you go private. | Settings → Code security |
| **Dependabot alerts + security updates** | Defaults vary; turn on explicitly. | Settings → Code security |
| **Merge prefs** (squash + rebase, no merge commit, delete branch on merge) | Not template-copied. | Settings → General → Pull Requests |
| **Disable Wiki / Projects** if you do not use them | Defaults to ON. | Settings → General → Features |

For a solo / personal project, you can skip branch protection. For anything you intend to share or take to production, enable at minimum:

- Require a pull request before merging
- Require status checks (after CI is added)
- Block force pushes
- Block deletions

These are the same defaults the **heavyweight sibling repo** (`claude-code-industrial-workbench`) configures automatically — when your project crosses that line, that template is the right move (see [`./decision-bmad-vs-full-workbench.md`](./decision-bmad-vs-full-workbench.md)).

### Step 5 — Now choose a stack — but **inside the new project, not back in the template**

Once you know what you're building (a web app, a CLI tool, a game backend…), add the stack-specific files inside the new project:

- Node project: add `package.json`, pick package manager
- Python project: add `pyproject.toml` + `uv` or `poetry` lockfile
- Go project: `go mod init`
- Etc.

**[Playwright](https://playwright.dev/) is pre-installed** for end-to-end browser tests. Unit tests (Vitest / Jest / Testing Library) cover component logic but can't test real browser navigation, route guards, route loaders, or cross-page flows — that's Playwright's job. Activate it once per derived project:

```bash
pnpm install              # installs @playwright/test
pnpm e2e:install          # downloads Chromium (~50 MB, one-time)
pnpm e2e                  # runs the (skipped) example spec — should pass clean
```

Once your app runs on `http://localhost:5173` (or change the `baseURL` in `playwright.config.ts`), unskip the example in `e2e/example.spec.ts` and write more specs alongside it. The BMAD `bmad-qa-generate-e2e-tests` skill generates Playwright specs against this layout.

**Backend-only / CLI-only project?** Delete `package.json`, `playwright.config.ts`, and `e2e/` — they're staged for the common case, not mandatory.

The template intentionally does not pick this for you. Different projects need different stacks.

## 3. How to drive BMAD's PM → Architect → Dev → QA loop

BMAD is the workflow engine. Once installed, it provides specialized agents that take your idea through a structured pipeline. Open Claude Code in the new project's folder and:

### 3.1 — Talk to the PM agent first (NEVER skip this)

```
@pm I want to build <one-sentence description of the project>.
Help me write the PRD.
```

The PM agent will ask clarifying questions (target users, success criteria, scope boundaries). Answer them honestly. The output is a **Product Requirements Document** in `docs/prd.md` (or whichever folder BMAD chose).

### 3.2 — Hand the PRD to the Architect agent

```
@architect Read docs/prd.md and propose an architecture.
```

The Architect agent will produce `docs/architecture.md` covering:
- Tech stack recommendation (this is where the stack choice actually gets made)
- Component boundaries
- Data model sketches
- Major trade-offs and risks

Push back on anything that doesn't fit your context (e.g. "I don't want Postgres for a single-user CLI"). Architecture is iterative.

### 3.3 — Break architecture into stories

```
@scrum-master Break the architecture into developer-ready stories.
```

The result is a set of files under `docs/stories/` (or BMAD's chosen path). Each story is a small, mergeable unit of work with acceptance criteria.

### 3.4 — Let the Developer agent implement one story at a time

```
@dev Implement story 1.1.
```

Critical rule: **one story per session**. Don't tell the Dev agent to "implement everything." That defeats the loop.

### 3.5 — QA verifies each story before the next

```
@qa Verify story 1.1.
```

QA writes tests, checks acceptance criteria, and either approves the story or sends it back to dev. Only after QA approves do you move on to story 1.2.

### 3.6 — Commit each completed story as its own commit

Use Conventional Commits:

```bash
git add .
git commit -m "feat(story-1.1): implement <thing>"
```

This is the cycle. PRD → architecture → stories → dev → QA → commit → next story. Slower than vibe-coding, dramatically higher hit rate on the first try.

## 4. Auto-pilot mode: low-friction execution

The default settings in this template are configured to **minimize confirmation clicks** without losing the safety floor. Three things make this work:

### 4.1 — `defaultMode: "acceptEdits"`

Set in [`.claude/settings.json`](../.claude/settings.json). File edits (Edit / Write / NotebookEdit) are auto-approved. You can still toggle modes mid-session with **Shift+Tab**:

| Mode | Behavior | When to use |
| --- | --- | --- |
| `default` | Every Bash / PowerShell call asks | Touching anything sensitive |
| **`acceptEdits`** (this template's default) | File edits auto, shell asks unless on allowlist | Everyday coding |
| `bypassPermissions` | Everything auto except what the hook blocks | Strong autonomous runs; trust the hook completely |

### 4.2 — Pre-approved command allowlist

[`.claude/settings.json → permissions.allow`](../.claude/settings.json) pre-approves ~80 read-mostly and build/test/format/git-local commands. Categories:

- **Read-only filesystem**: `ls`, `cat`, `head`, `tail`, `find`, `grep`, `wc`, `tree`, …
- **Git inspection + local-safe**: `git status / diff / log / show / branch / add / commit / fetch / checkout / restore / stash / tag`
- **Node ecosystem**: `npm test / lint / typecheck / build / dev`, `pnpm` equivalents, `npx prettier / eslint / tsc / vitest / jest / playwright`
- **Python ecosystem**: `pytest`, `ruff`, `mypy`, `black`, `isort`, `uv run / sync / lock`
- **Go ecosystem**: `go test / build / vet`, `gofmt`, `golangci-lint`
- **Rust ecosystem**: `cargo build / test / check / clippy / fmt`
- **BMAD scripts**: `python _bmad/scripts/*`, `npx bmad-method *`
- **gh CLI read-only**: `gh repo view / pr view / pr list / run view / api repos/*`
- **PowerShell read-only**: `Get-*`, `Test-Path`, `ConvertFrom-Json`, etc.

Plus a **deny list** that overrides allow for the truly destructive: `git push --force`, `git reset --hard`, `git clean -fd`, `git branch -D`, `gh repo delete`, `npm publish`, …

### 4.3 — Safety floor never disappears

[`.claude/hooks/block_dangerous_commands.py`](../.claude/hooks/block_dangerous_commands.py) runs on **every** Bash / PowerShell call, regardless of allowlist or mode. It blocks:

- `rm -rf` and equivalents
- `git push --force` (in any form)
- `git reset --hard`, `git clean -fd`, `git branch -D`
- Reading `.env` / `.env.*` / `*.pem` / `*.key`
- Printing `$SECRET` / `$TOKEN` / `$API_KEY` / `$GITHUB_TOKEN` style env vars

So even in `bypassPermissions` mode, these can't slip through.

### 4.4 — `/loop` slash command: one-shot Dev ↔ Review cycle

Defined in [`.claude/commands/loop.md`](../.claude/commands/loop.md). Invoke from any Claude Code session:

```
/loop story-1.1
```

(or `/loop "make the login form accept passkeys"` for an ad-hoc task)

What `/loop` does in **one continuous response** without stopping for your input:

1. **Dev** phase — uses the `bmad-dev-story` skill to implement
2. **Review** phase — uses the `bmad-code-review` skill to strictly inspect
3. **Apply** phase — uses `bmad-correct-course` to fix what review found
4. Loop back to step 2 until review finds 0 issues OR 3 cycles elapse
5. Produce **one** final report at the end

You read one summary at the end instead of typing `@qa`, `@dev`, `@qa`, `@dev`. If a decision genuinely needs your judgment (e.g. "should this be a public API?"), `/loop` collects all such questions at the end of the report so you answer them **all at once**, not interleaved with code changes.

### 4.5 — When to back off from auto-pilot

Switch back to `default` mode (Shift+Tab) when you are about to:

- Touch authentication / authorization code
- Write database migrations on tables with real data
- Modify payment / billing logic
- Edit production-touching infra-as-code
- Make irreversible API contract changes

The hook still wouldn't let you nuke files, but a sensitive logic change benefits from per-step pause to think.

### 4.6 — Trade-off, stated honestly

Less clicking = less per-step inspection. The hook catches **destructive** ops; it does **not** catch **wrong** ones. A `/loop` run that converges to "QA found 0 issues" can still produce code that satisfies the wrong requirement. **Read the final report.** If it touched files you didn't expect, that's the signal to roll back.

For the first BMAD cycle on any new project, prefer **default** mode until you trust the agent's judgment in your specific stack and domain. Then graduate to `acceptEdits` (default after derive) and eventually `bypassPermissions` for routine cycles.

## 5. Memory — where each kind of context lives

Claude Code projects accumulate three different kinds of "memory," and they live in three different places. Knowing which lives where avoids the common bug of "I wrote X down somewhere, where did it go?"

| Layer | Where it lives | What goes there | Survives `git clone` to a new machine? |
| --- | --- | --- | --- |
| **User-level auto-memory** | `~/.claude/projects/<project>/memory/` (your home dir) | Claude's own notes about you, your preferences, your role, project-specific feedback. Written automatically by Claude during sessions per `auto memory` rules in [`CLAUDE.md`](../CLAUDE.md). | ❌ No — local to your home dir, not in the repo. |
| **Planning artifacts** | `docs/planning-artifacts/<type>/` (in the repo) | BMAD's structured outputs: briefs, PRDs, UX docs, architecture, epics, stories, readiness reports. Written by BMAD skills (`bmad-create-prd`, `bmad-create-architecture`, etc.). | ✅ Yes — committed to the repo, follows it everywhere. |
| **Implementation artifacts** | `docs/implementation-artifacts/` (in the repo) | Sprint plans, sprint status YAML, per-story files, retrospective notes. Written by `bmad-sprint-planning`, `bmad-dev-story`, `bmad-retrospective`. | ✅ Yes — committed to the repo. |

**Rule of thumb:**
- If it's about **you** (your role, your preferences, feedback you've given) → user-level auto-memory handles it. Don't duplicate it in the repo.
- If it's about **the project's intent** (PRD, architecture, decisions) → BMAD writes it to `docs/planning-artifacts/`. Commit it.
- If it's about **what was built** (story files, sprint progress) → BMAD writes it to `docs/implementation-artifacts/`. Commit it.

You generally don't write any of these by hand — Claude / BMAD do it for you. Your job is to let them, and to commit the results.

## 6. Graduation tools — what to add later, NOT on day 1

The template ships with a deliberately small tool surface so Claude's decisions stay focused. Two things are worth adding **after** the project outgrows the defaults — but installing them too early just adds noise.

### 6.1 — `wshobson/agents` (when BMAD has a gap)

Add it when **all three** are true:

1. You've done at least one full BMAD cycle on the project.
2. You've identified a specific gap BMAD doesn't cover well (e.g. "I need a deep refactor specialist", "I need an SEO-focused content writer", "I need a SQL query optimizer").
3. You've checked that no built-in BMAD agent handles it.

Then:

```bash
/plugin marketplace add wshobson/agents
/plugin install <specific-plugin>
```

Install **one plugin at a time**. Claude's tool list gets noisy fast, and noise reduces decision quality.

### 6.2 — `CodeGraph` (when the project gets large)

[CodeGraph](https://github.com/colbymchenry/codegraph) is a local code-intelligence MCP. It pre-indexes your source into an AST knowledge graph (tree-sitter → local SQLite + FTS5), so Claude answers "where is X defined / what calls Y" by querying the index in a few calls instead of fanning out across grep / find / Read across dozens of files.

Add it when **all three** are true:

1. Your project has roughly **>1000 source files** — under that, plain grep is fast enough and the index is overhead.
2. You notice Claude burning many tool calls on code-navigation questions (not on writing new code, where Context7 already helps).
3. You're willing to keep one more local index running. CodeGraph re-syncs on file changes via native OS file watchers — usually invisible.

Reported median impact across real codebases (upstream benchmarks): **~59% fewer tokens, ~49% faster, ~70% fewer tool calls**. The headline 52→3 tool-call number in promo material is from a ~4000-file project — small projects see much smaller wins, which is why this is **not** installed by default.

Follow the install instructions at the upstream repo. It is MIT-licensed, runs 100% locally, needs no API key, and supports 19+ languages.

### Why these are NOT bundled

CodeGraph and `wshobson/agents` are valuable, but their value scales with project size or with specific gaps you've already felt. Installing them on an empty template means:

- More MCP tools / agents in Claude's tool list from day 1 → harder to pick the right tool, more tokens spent describing the surface.
- A maintenance surface (indexes, plugin updates) before there's anything to maintain.

The template's job is to **ship you to the starting line**. Add these the first time you feel the pain they solve.

## 7. Why SuperClaude is intentionally NOT installed

SuperClaude is a popular alternative framework that injects its own `CLAUDE.md` and instruction files into `~/.claude/`. Two problems with installing it on top of this template:

1. It would overwrite or compete with the carefully preserved Karpathy `CLAUDE.md`, which is the behavioral baseline this template is built around.
2. Its persona-switching model overlaps with BMAD's agent-handoff model — running both produces confused behavior.

Choose one or the other, not both. This template's choice is BMAD.

## 8. Multi-agent work — try Agent Teams first

When you need multiple Claude sessions to coordinate (parallel research, supervisor / worker patterns, durable state across sessions), reach for [**Claude Code Agent Teams**](https://code.claude.com/docs/en/agent-teams) first. It is Anthropic's native primitive for the job — currently experimental, enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` in `~/.claude/settings.json`. No extra install, no extra framework, just a setting toggle.

For most projects at this template's scope you may not even need that — BMAD's `@agent` chain (PM → Architect → Dev → QA) already covers sequential multi-agent coordination, and the sequential version is usually enough.

Heavier orchestration frameworks (DAG control, durable workflow state at team / production scale) become worth their overhead later — when you cross that line, graduate to [`claude-code-industrial-workbench`](https://github.com/lordrance/claude-code-industrial-workbench).

## 9. Things this template will not solve for you

To be honest about scope:

- **Security review at scale** — for multi-person or regulated projects, use the heavyweight sibling [`claude-code-industrial-workbench`](https://github.com/lordrance/claude-code-industrial-workbench) instead. See [`./decision-bmad-vs-full-workbench.md`](./decision-bmad-vs-full-workbench.md).
- **Cost guardrails / token budgeting** — not implemented yet anywhere in the Claude Code ecosystem as of 2026-05. Watch your usage manually.
- **Eval harness / regression testing of AI behavior** — same as above.
- **Audit log of every AI action** — same as above.

These four are the Tier 3 gaps. They will land in a future revision of the heavyweight workbench, not here.

## 10. One-line summary

**This template ships you to the starting line; BMAD coaches you through the race; you finish projects faster than building from zero each time.**
