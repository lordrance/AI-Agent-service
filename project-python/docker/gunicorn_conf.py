# -*- coding: utf-8 -*-
"""Gunicorn 生产配置：UvicornWorker + 优雅停机。"""

from __future__ import annotations

import multiprocessing
import os

# 绑定地址
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Worker 数量（默认：2 * CPU + 1，可通过环境变量覆盖）
_default_workers = max(2, multiprocessing.cpu_count() * 2 + 1)
workers = int(os.getenv("GUNICORN_WORKERS", str(_default_workers)))

worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))

# 优雅停机：SIGTERM 后等待在途请求完成
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# 日志
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# 预加载应用（多 worker 共享内存；与 lifespan 兼容需注意，FastAPI 推荐 per-worker 初始化）
preload_app = os.getenv("GUNICORN_PRELOAD", "false").lower() == "true"

# 进程名
proc_name = os.getenv("OTEL_SERVICE_NAME", "enterprise-ai-agent")
