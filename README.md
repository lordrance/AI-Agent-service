# claude-code-bmad-foundation

A **lightweight** Claude Code template for solo developers who want to ship code fast. The heavy lifting of "how do features get planned, designed, built, and tested" is handed to [**BMAD-METHOD**](https://github.com/bmad-code-org/BMAD-METHOD); this repo only provides the minimum scaffolding above it.

This is a **base template**, not an application. It has no business code, no tech stack, no app features.

## Who this is for

**Use this if you...**
- Work solo or in a tiny team (1–3 people)
- Want Claude Code to follow a structured PRD → architecture → stories → code → QA workflow ([BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD))
- Want a safety floor (Claude can't `rm -rf`, read `.env`, force-push) plus ~80 pre-approved read/build/test commands so you don't click "Approve" all day
- Will probably build something with a frontend (Playwright is pre-staged)

**Use [`claude-code-industrial-workbench`](https://github.com/lordrance/claude-code-industrial-workbench) instead if you...**
- Have 4+ collaborators and need branch protection, CODEOWNERS, signed commits
- Handle regulated data (HIPAA, GDPR, PCI, etc.)
- Ship to real customers and need full CI / security / scorecard / SBOM workflows

## Quickstart

```bash
# 1. On github.com, click "Use this template" → create your new repo.

# 2. Clone it locally
gh repo clone <your-org>/<your-new-project> && cd <your-new-project>

# 3. Verify the template installed cleanly (~20 invariants checked)
python scripts/health-check.py

# 4. If your project has a frontend, activate Playwright (one-time)
pnpm install && pnpm e2e:install

# 5. Open Claude Code and talk to the BMAD PM agent
#    @pm I want to build <one sentence about your project>
#    BMAD then drives PM → Architect → Dev → QA, one story at a time.
```

Full walkthrough in [`docs/usage.md`](./docs/usage.md).

## 1. What this is

- A Karpathy-style [`CLAUDE.md`](./CLAUDE.md) — the upstream behavioral baseline plus a short section telling Claude to use the template's installed tools (Context7, /loop, different-model code review) before training memory.
- Basic project hygiene: [`.gitignore`](./.gitignore), [`.gitattributes`](./.gitattributes), [`.editorconfig`](./.editorconfig), [`LICENSE`](./LICENSE) (MIT).
- A single safety hook: `.claude/hooks/block_dangerous_commands.py` — prevents Claude from running `rm -rf`, reading `.env`, force-pushing, etc.
- Two pre-wired MCP servers in [`.mcp.json`](./.mcp.json): **Context7** (live, version-specific library docs — no stale-API hallucinations) and **Sequential Thinking** (Anthropic-maintained MCP for structured multi-step reasoning that complements BMAD's planning chain). Both are free, no API key needed.
- **Playwright pre-staged** for frontend end-to-end tests: [`package.json`](./package.json), [`playwright.config.ts`](./playwright.config.ts), and [`e2e/example.spec.ts`](./e2e/example.spec.ts) (`test.skip`'d placeholder). Activate per derived project via `pnpm install && pnpm e2e:install`. If your project is backend-only or CLI-only, delete these three files.
- **Self-verification:** [`scripts/health-check.py`](./scripts/health-check.py) — cross-platform Python (no deps). Run `python scripts/health-check.py` after deriving the template to verify ~20 invariants at once (file presence, JSON validity, MCP entries, Playwright stage, BMad install, runtime tools on PATH, safety hook compiles). Exit 0 = green.
- GitHub PR + Issue templates in [`.github/`](./.github/) — language-agnostic, keeps contributions structured.
- **BMAD-METHOD installed on top** — provides the PM / Architect / Developer / QA workflow and 12+ specialized agents.
- Two short docs in `docs/` explaining how to use the template and how it relates to the heavyweight sibling repo.

**Prerequisites:** [Node 18+](https://nodejs.org/) and [pnpm](https://pnpm.io/installation) (`npm install -g pnpm`) are required to activate Playwright. If you'll never need a frontend, you can skip both and delete the Playwright files (see above).

## 2. What is NOT in here (by design)

- No application-stack manifest (`pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, etc.) — the only `package.json` is the minimal one that pulls in Playwright as a devDependency.
- No `Dockerfile`, Terraform, Kubernetes, or app-framework configs (vite/next/jest/pytest/etc.) — `playwright.config.ts` is the only framework config and is opt-out (delete it for non-frontend projects).
- No `src/`, `app/`, `server/`, `client/` — no source code skeleton. (`e2e/` is the Playwright test directory, not application code.)
- No CI / security / supply-chain workflows. Those live in the heavyweight sibling repo: [`claude-code-industrial-workbench`](https://github.com/lordrance/claude-code-industrial-workbench).
- No SuperClaude, no wshobson/agents — not installed by default to keep Claude's tool surface focused.
- No homemade SDLC workflow (specs/, .specify/, custom skills, custom subagents) — BMAD owns this layer.

## 3. How to use this template

The Quickstart above is the 5-command version. For the deeper walkthrough (BMAD agent handoffs, auto-pilot mode, memory layers, graduation tools), see [`docs/usage.md`](./docs/usage.md).

## 4. Related: when to use the full workbench instead

If you're working on a multi-person project, dealing with regulated data, or already shipping to customers — use the heavyweight sibling: [`claude-code-industrial-workbench`](https://github.com/lordrance/claude-code-industrial-workbench). It adds CODEOWNERS, branch protection, OpenSSF Scorecard, SBOM / container / IaC scanning, AI governance policies, and a Tier 1.5 universal engineering skeleton.

See [`docs/decision-bmad-vs-full-workbench.md`](./docs/decision-bmad-vs-full-workbench.md) for the full trade-off.

## 5. Attribution

This template includes BMAD-METHOD-generated files from [`bmad-code-org/BMAD-METHOD`](https://github.com/bmad-code-org/BMAD-METHOD). BMAD-METHOD is licensed under MIT. BMad-related names and trademarks (BMad™, BMad Method™, BMAD-METHOD™, BMad Core™) belong to BMad Code, LLC. **This repository is not an official BMAD project** and is not affiliated with, sponsored by, or endorsed by BMad Code, LLC.

The full list of third-party components and the license/trademark scope live in [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md).

---

License: [MIT](./LICENSE). Not affiliated with, endorsed by, or created by Anthropic, GitHub, Cursor, or Andrej Karpathy.
