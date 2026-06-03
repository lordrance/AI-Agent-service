#!/usr/bin/env bash
# 云 Agent VM 启动后运行：拉起 PostgreSQL + Redis
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/project-python/docker-compose.cloud.yml"

start_docker_services() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "[cloud-start] docker not found; skip compose services"
    return 0
  fi

  sudo service docker start 2>/dev/null || true

  if docker compose version >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" up -d --wait 2>/dev/null \
      || docker compose -f "$COMPOSE_FILE" up -d
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f "$COMPOSE_FILE" up -d
  else
    echo "[cloud-start] docker compose not available"
    return 0
  fi

  echo "[cloud-start] postgres + redis up (docker compose)"
}

start_native_services() {
  if command -v pg_isready >/dev/null 2>&1; then
    sudo service postgresql start 2>/dev/null || true
    sudo -u postgres psql -d agent_db -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
  fi
  if command -v redis-cli >/dev/null 2>&1; then
    sudo service redis-server start 2>/dev/null || true
  fi
}

start_docker_services || true
start_native_services || true
