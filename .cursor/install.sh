#!/usr/bin/env bash
# 云 Agent 环境安装脚本（幂等）。
# 由 .cursor/environment.json 的 install 钩子在每次新机器启动时调用；
# Cursor 会在 install 较慢时自动做检查点缓存，后续启动走增量。
# 负责：系统依赖（PostgreSQL16 + pgvector + Redis）→ Python 依赖 → 数据库初始化 → 迁移。
set -uo pipefail

echo "[install] 1/5 安装系统依赖（PostgreSQL 16 + pgvector + Redis）"
sudo apt-get update -y -q
sudo apt-get install -y -q \
  postgresql postgresql-contrib postgresql-16-pgvector redis-server

echo "[install] 2/5 启动 PostgreSQL 与 Redis"
sudo pg_ctlcluster 16 main start 2>/dev/null || sudo service postgresql start || true
sudo service redis-server start || true
# 等待 PostgreSQL 就绪（最多 ~20s）
for _ in $(seq 1 20); do
  if sudo -u postgres psql -tc "SELECT 1" >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "[install] 3/5 初始化数据库 agent_db 与 pgvector 扩展（幂等）"
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';" || true
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='agent_db'" \
  | grep -q 1 || sudo -u postgres createdb agent_db
sudo -u postgres psql -d agent_db -c "CREATE EXTENSION IF NOT EXISTS vector;" || true

echo "[install] 4/5 安装 Python 依赖（运行时 + 开发/测试工具）"
cd project-python
pip install --break-system-packages -q -r requirements.txt
pip install --break-system-packages -q pytest pytest-asyncio ruff mypy

echo "[install] 5/5 运行数据库迁移"
python3 -m alembic upgrade head \
  || echo "[install] 迁移未成功（DB 可能尚未就绪），agent 可手动重试: cd project-python && python3 -m alembic upgrade head"

echo "[install] 完成。可运行：cd project-python && python3 -m pytest -q"
