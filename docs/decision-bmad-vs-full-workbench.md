# Decision: BMAD Foundation vs Full Industrial Workbench

There are two Claude Code template repositories in this org. They serve different lifecycles. Pick the right one for the project you're starting.

## TL;DR

| Use this (`claude-code-bmad-foundation`) | Use the [full workbench](https://github.com/lordrance/claude-code-industrial-workbench) |
| --- | --- |
| Solo developer | Team (2+) |
| Coding speed matters most | Review quality / compliance matters most |
| Personal project, prototype, side project | Customer-facing product, regulated data |
| You haven't shipped anything to real users yet | You ship to real users |
| You're learning a new stack | You're maintaining production code |
| OK to revisit security later | Security must be part of every PR |

If you're not sure: **start with this template**. Migrating to the heavyweight workbench later is straightforward (copy the workflows + CODEOWNERS + ruleset). Migrating away from it is annoying.

## What this template (the lightweight one) has

- Karpathy `CLAUDE.md`
- Basic hygiene: `.gitignore`, `.gitattributes`, `.editorconfig`, `LICENSE`
- One safety hook: `block_dangerous_commands.py`
- **Context7 MCP** pre-wired (live library docs)
- **Playwright pre-staged** (`package.json` + `playwright.config.ts` + `e2e/example.spec.ts`, skipped by default; activate with `pnpm install`)
- **Dependabot config** (npm-only, weekly; tracks Playwright)
- **BMAD-METHOD** installed on top (provides PM / Architect / Dev / QA agents + SDLC workflow)
- Two short docs

Approximately **20-30 files** total before you start writing project code.

## What the heavyweight workbench has on top of that

Everything above, plus:

- **CI / Security / Scorecard workflows** — `.github/workflows/ci.yml`, `security.yml`, `scorecard.yml`, `sbom.yml`, `container-scan.yml`, `iac-scan.yml`
- **Branch protection ruleset** — `main` requires PR + status checks + linear history
- **CODEOWNERS** — automatic review requests on touch-sensitive paths
- **Dependabot** — auto-PRs for action and dependency updates
- **Lefthook** + commit-msg + secret-files + json-syntax hooks — local pre-commit safety
- **Tier 1.5 policy docs** — `docs/observability/`, `feature-flags/`, `reliability/`, `release/`, `security/` (OpenTelemetry, OpenFeature, SLO/SLI, Conventional Commits, SBOM, container scanning, IaC scanning, license compliance)
- **AI governance v0** — `docs/ai-governance/`, `.claude/mcp.policy.json`, `.claude/models.policy.md`
- **Custom skills + subagents** — 6 SKILL.md + 4 agent.md focused on review (TDD, debug, code-review, security-review, db-migration-review, api-contract-review)
- **Spec-driven workflow scaffolding** — `.specify/`, `specs/`
- **Issue templates + PR template** — `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`
- **Task runner + DevContainer + tool-versions examples**

Approximately **60-80 files** before you start writing project code.

## Why the lightweight one exists

The full workbench is **excellent** for projects that need it, and **overkill** for projects that don't. If you're a solo developer trying to ship a small game / personal tool / experiment, the heavyweight version produces noise:

- Branch protection on a solo `main` slows you down for no review benefit (there's nobody else to review).
- Conventional Commits + commit-msg gate forces discipline even for `wip:` scratchpad commits.
- 7 CI workflows = 7 GitHub Actions billed-minute consumers; for a hobby repo this can hit free-tier limits.
- 13 Tier 1.5 policy docs assume you'll consult them; on a side project you won't.

The lightweight foundation strips all of that out and bets that **BMAD's structured workflow alone** is enough discipline for solo work.

## Why BMAD specifically

The full workbench has a homemade `specs/<feature>/{spec,plan,tasks,checklist}.md` workflow. It's well-designed but **un-validated** by community use. BMAD has the same shape (PRD → architecture → stories → implementation) but with **48k+ GitHub stars and 5,600+ forks of real-world usage** behind it.

For solo coding speed, install the validated tool, don't re-invent it.

## Migration path: lightweight → heavyweight

If your project grows past the lightweight threshold (gets a collaborator, gets users, gets regulated data), you can migrate:

1. **Copy CI workflows** from the full workbench's `.github/workflows/` (ci, security, scorecard).
2. **Add CODEOWNERS** with the new team members' GitHub handles.
3. **Enable branch protection** on `main` via Settings → Rules → Rulesets.
4. **Copy relevant Tier 1.5 docs** as the project encounters those concerns (don't copy them all up front).
5. **Keep BMAD** — both templates can use BMAD; the full workbench just adds governance around it.

You do not need to abandon BMAD or change CLAUDE.md to migrate. The lightweight → heavyweight path is additive.

## Migration path: heavyweight → lightweight

Less common but valid: a heavyweight project that turned out to be solo / experimental / never shipping.

1. Delete `.github/workflows/` except `ci.yml`.
2. Delete `.github/CODEOWNERS` (the lightweight template keeps `.github/dependabot.yml`, `.github/ISSUE_TEMPLATE/`, and `.github/pull_request_template.md`, so don't delete those).
3. Disable the branch protection ruleset in GitHub Settings → Rules.
4. Delete `docs/observability/`, `feature-flags/`, `reliability/`, `release/`, `security/`, `ai-governance/`.
5. Delete `.specify/`, `specs/`, `evals/`, `presets/`, `.claude/agents/`, `.claude/skills/`, `.claude/mcp.policy.*`, `.claude/models.policy.md`.
6. Delete `lefthook.yml`, `.scripts/`.
7. Keep CLAUDE.md, the basic hygiene files, and `block_dangerous_commands.py`.
8. Install BMAD if not already present.

Result: a project that looks like one created from the lightweight template, with code intact.

## One-line summary

**Lightweight template = ship code fast on solo projects. Full workbench = ship safely on team / customer / regulated projects. Both use BMAD; the difference is how much process surrounds BMAD.**
