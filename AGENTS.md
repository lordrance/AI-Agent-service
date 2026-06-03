# AGENTS.md

## Cursor Cloud specific instructions

### Repository layout

| Area | Purpose |
|------|---------|
| **Repo root** | Claude Code + BMAD template (`_bmad/`, hooks, MCP). Not a shipped app. |
| **`project-python/`** | Runnable **enterprise-ai-agent** FastAPI skeleton (health, chat, document upload). |

There is **no frontend** in this repo. Root Playwright (`pnpm e2e`) uses a skipped placeholder spec.

### One-time VM packages (not in update script)

If `python3 -m venv` fails with “ensurepip is not available”, install:

```bash
sudo apt-get install -y python3.12-venv
```

For **PostgreSQL-backed** flows (`/health/ready`, document APIs), either use Docker Compose from `project-python/` (if Docker is installed) or install local Postgres:

```bash
sudo apt-get install -y postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres createdb agent_db   # skip if exists
```

The repo has **no Alembic migrations**. On first run, create ORM tables once (from `project-python/` with venv active):

```bash
python -c "
import asyncio
from app.config import get_settings
from app.infrastructure.database.models import Base
from app.infrastructure.database.session import init_engine
async def main():
    e = init_engine(get_settings().database_url)
    async with e.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    await e.dispose()
asyncio.run(main())
"
```

Copy env: `cp project-python/.env.example project-python/.env` and set `OPENAI_API_KEY` for `/chat`.

### Services to run for development

| Service | Command | Port |
|---------|---------|------|
| **FastAPI** | `cd project-python && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | 8000 |
| **PostgreSQL** | `sudo service postgresql start` (local) or `docker compose up -d postgres` | 5432 |
| **Redis / Milvus** | Optional; only needed for full RAG/vector paths. See `project-python/docker-compose.yml`. |

Use **tmux** for long-running `uvicorn` (see Cloud Agent tmux conventions).

### Lint / test / verify

| Scope | Command |
|-------|---------|
| Template sanity | `python3 scripts/health-check.py` (repo root) |
| Playwright | `pnpm install` then `pnpm e2e` (placeholder skipped) |
| Python lint | `cd project-python && source .venv/bin/activate && ruff check .` (many style findings may already exist) |
| Python tests | `pytest` (no test modules in tree yet; “no tests ran” is expected) |
| API smoke | `curl http://127.0.0.1:8000/api/v1/health` |

Swagger UI: `http://127.0.0.1:8000/docs`

### Gotchas

- Shell may expose `python3` but not `python`; use `python3` for health-check.
- **`app.infrastructure.trace.langfuse_exporter`** must exist for the app to import `chat` routes; if missing from checkout, add a no-op or Langfuse exporter before starting uvicorn.
- `ruff check` can report many pre-existing issues; that does not block running the server.
- Playwright browser deps: if GUI tests fail, run `sudo pnpm exec playwright install-deps` once (optional for skipped e2e).

See `README.md` and `project-python/README.md` for full onboarding.
