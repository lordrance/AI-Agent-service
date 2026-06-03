# AGENTS.md

## Cursor Cloud 专用说明（project-python）

云 Agent 启动时会读取 `.cursor/environment.json`，自动执行：

1. **`install`** → `bash .cursor/scripts/cloud-install.sh`（pip 依赖 + dev 工具）
2. **`start`** → `bash .cursor/scripts/cloud-start.sh`（Docker Compose 拉起 Postgres 16 + pgvector、Redis）

### 首次一次性设置（推荐，之后每次秒开）

1. 打开 [Cloud Agents → Environments](https://cursor.com/dashboard/cloud-agents#environments) → **New environment**，选择本仓库。
2. 在 **Secrets** 里配置 `OPENAI_API_KEY` 等（参考 `project-python/.env.example`）。
3. 用下面提示词跑一次 **Setup Run**，让 Agent 验证环境并修复问题：

```
为 project-python（FastAPI + LangGraph + pgvector + SQLAlchemy/Alembic 的 AI Agent 服务）配置云环境：
装并启动 PostgreSQL 16 + pgvector 扩展（库 agent_db、用户 postgres/postgres）、Redis；
pip install -r project-python/requirements.txt 与 dev 依赖（pytest、pytest-asyncio、ruff、mypy）。
目标：新 agent 起来后 alembic upgrade head、pytest、uvicorn app.main:app 可直接运行。
仓库已含 .cursor/environment.json 与 docker-compose.cloud.yml，请先执行 cloud-install / cloud-start 脚本验证。
```

4. 验证通过后，在 Environment 页面 **Save snapshot**。
5. 把 snapshot ID 写入 `.cursor/environment.json`（与 `build` 二选一，snapshot 优先、启动更快）：

```json
{
  "snapshot": "snapshot-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "install": "bash .cursor/scripts/cloud-install.sh",
  "start": "bash .cursor/scripts/cloud-start.sh"
}
```

6. 合并到 `main` 后，**以后每个新 Cloud Agent 都会自动用这份环境**，无需再手动安装。

### 日常命令（在 `project-python/` 目录、已 activate `.venv`）

```bash
source project-python/.venv/bin/activate
cd project-python

# 数据库迁移（Epic 引入 Alembic 后）
alembic upgrade head

# 测试
pytest

# 启动 API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 服务连接

| 服务 | 地址 |
|------|------|
| PostgreSQL | `postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db` |
| Redis | `redis://localhost:6379/0` |

全栈（含 Milvus）联调：`docker compose -f project-python/docker-compose.yml up -d`
