#!/usr/bin/env bash
# 部署后冒烟测试：健康检查、就绪探针、指标、可选 RAG
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
API_PREFIX="${API_PREFIX:-/api/v1}"
TIMEOUT="${SMOKE_TIMEOUT:-30}"

echo "==> Smoke test against ${BASE_URL}${API_PREFIX}"

curl -fsS --max-time "${TIMEOUT}" "${BASE_URL}${API_PREFIX}/health" | tee /tmp/smoke-health.json
echo
grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' /tmp/smoke-health.json \
  || { echo "FAIL: liveness"; exit 1; }

curl -fsS --max-time "${TIMEOUT}" "${BASE_URL}${API_PREFIX}/health/ready" | tee /tmp/smoke-ready.json
echo
grep -q '"database"' /tmp/smoke-ready.json \
  || { echo "FAIL: ready missing database field"; exit 1; }

curl -fsS --max-time "${TIMEOUT}" "${BASE_URL}${API_PREFIX}/metrics" | head -c 500
echo
echo "... metrics OK (truncated)"

# 可选：RAG 检索（无需 OPENAI_KEY）
if [ "${SMOKE_SKIP_RAG:-false}" != "true" ]; then
  code=$(curl -sS -o /tmp/smoke-rag.json -w "%{http_code}" --max-time "${TIMEOUT}" \
    -X POST "${BASE_URL}${API_PREFIX}/rag/query" \
    -H "Content-Type: application/json" \
    -d '{"query":"smoke test deployment","top_k":1}')
  echo "RAG /rag/query HTTP ${code}"
  if [ "${code}" != "200" ] && [ "${code}" != "401" ]; then
    echo "FAIL: unexpected RAG status ${code}"
    cat /tmp/smoke-rag.json || true
    exit 1
  fi
fi

echo "==> All smoke checks passed."
