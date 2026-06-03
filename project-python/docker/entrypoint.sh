#!/bin/sh
# 生产入口：可选迁移 + gunicorn（优雅停机由 K8s/Docker SIGTERM 触发）
set -eu

cd /app

if [ "${RUN_MIGRATIONS_ON_STARTUP:-true}" = "true" ]; then
  echo "[entrypoint] Running alembic upgrade head..."
  alembic upgrade head
fi

echo "[entrypoint] Starting gunicorn (workers=${GUNICORN_WORKERS:-auto})..."
exec gunicorn -c /app/docker/gunicorn_conf.py "app.main:app"
