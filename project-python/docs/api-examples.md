# API 调用示例

基础 URL：`http://127.0.0.1:8000`。以下假设 `AUTH_ENABLED=false`（开发默认）。

## 健康检查

```bash
curl -s http://127.0.0.1:8000/api/v1/health
curl -s http://127.0.0.1:8000/api/v1/health/ready
```

## 上传文档

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/documents/upload \
  -F "file=@./README.md"
```

## RAG 查询

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "向量库用什么？"}'
```

## 对话（非流式）

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "用一句话介绍你自己"}],
    "conversation_id": "demo-1"
  }'
```

## 对话（SSE 流式）

```bash
curl -N -X POST http://127.0.0.1:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"数到 5"}]}'
```

## Agent（带记忆）

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/agent \
  -H "Content-Type: application/json" \
  -d '{
    "input": "计算 (12 + 8) * 3",
    "session_id": "agent-demo-1",
    "use_memory": true
  }'
```

## 删除文档

```bash
curl -s -X DELETE http://127.0.0.1:8000/api/v1/documents/{document_id}
```

## 多租户（API Key）

`.env` 中设置 `AUTH_ENABLED=true` 与 `API_KEYS=tenant-a:secret-a`：

```bash
curl -s -H "X-API-Key: secret-a" \
  http://127.0.0.1:8000/api/v1/documents
```
