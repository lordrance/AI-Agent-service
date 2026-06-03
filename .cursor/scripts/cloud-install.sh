#!/usr/bin/env bash
# 云 Agent 每次启动时运行的 update 脚本（必须幂等）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/project-python"
VENV="$PY/.venv"

cd "$ROOT"

# Python 虚拟环境与依赖
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install --upgrade pip
pip install -r "$PY/requirements.txt"
pip install -e "$PY[dev]"

# 本地 .env（不覆盖已有配置）
if [[ ! -f "$PY/.env" ]]; then
  cp "$PY/.env.example" "$PY/.env"
fi

# Alembic 就绪后取消注释即可在每次启动时自动迁移
# if [[ -f "$PY/alembic.ini" ]]; then
#   cd "$PY" && alembic upgrade head
# fi

echo "[cloud-install] Python deps ready at $VENV"
