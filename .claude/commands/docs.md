---
description: Fetch current docs for a library / framework / SDK via the Context7 MCP, in a single shot.
---

# /docs — one-shot library lookup via Context7

**Argument**: `$ARGUMENTS` (the library name, optionally followed by a topic or symbol — e.g. `react useEffect`, `fastapi background tasks`, `prisma migrations`, `tailwind v4 install`)

## Goal

Wrap the two Context7 calls (`resolve-library-id` then `query-docs`) into a single invocation so the user can type one slash command and get current, version-specific documentation instead of relying on training memory.

This exists because [`CLAUDE.md`](../CLAUDE.md#L62) tells future Claude sessions to use Context7 before going to training memory, but a manual two-call workflow is friction. `/docs` removes that friction.

## How to handle the argument

Parse `$ARGUMENTS` as:

- **First token = library name** (the thing to resolve). Examples: `react`, `fastapi`, `prisma`, `tailwind`, `@upstash/redis`.
- **Remaining tokens = topic** (optional, can be empty). Examples: `useEffect`, `background tasks`, `migrations`, `v4 install`.

If `$ARGUMENTS` is empty, ask the user once: *"Which library? (e.g. `react useEffect`, `fastapi background tasks`)"* — then proceed.

## Steps

1. Call **`mcp__context7__resolve-library-id`** with `libraryName` = the first token. If multiple matches come back, pick the most popular / official one and mention the alternatives in one line.
2. Call **`mcp__context7__query-docs`** with the resolved `context7CompatibleLibraryID` and `topic` = the remaining tokens (or omit `topic` if empty). Use `tokens: 5000` unless the user wrote `--full` in the argument, in which case use `tokens: 15000`.
3. Summarize the result in **≤ 200 words**, focused on what's directly relevant to the topic. If a code snippet from the docs answers the question, include it verbatim (don't paraphrase API names).
4. End with a one-line citation: *"Source: Context7 → `<resolved-id>` (queried `<date>`)."*

## Rules

- **Do not** invent function names / signatures / config keys that weren't in the Context7 response. If the docs don't cover the topic, say so and suggest a different topic string.
- **Do not** mix in training-memory knowledge. The point of this command is to bypass that.
- **Do not** write code that uses the library beyond the snippets in the docs — the user invoked `/docs`, not `/implement`. If they want code, they'll follow up.
- **Do** keep the answer terse. The user can re-invoke with a narrower topic if they need more.
