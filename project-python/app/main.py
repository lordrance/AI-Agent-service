# -*- coding: utf-8 -*-
"""FastAPI 应用入口：生命周期内初始化异步数据库引擎。"""

from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api.routes import agent, chat, document, health, rag
from app.config import get_settings
from app.core.langgraph.graph import build_chat_graph
from app.core.langgraph.model import build_router_model_fn
from app.infrastructure.database.session import configure_session, init_engine
from app.infrastructure.vectordb.factory import build_vector_store
from app.infrastructure.vectordb.pgvector_store import _to_asyncpg_dsn


async def _init_chat_graph(app: FastAPI, settings, stack: AsyncExitStack) -> None:
    """初始化对话图与 Postgres 检查点；任一环节失败则降级（无图/无持久化）。"""
    model_fn = build_router_model_fn()
    if model_fn is None:
        app.state.chat_graph = None
        logger.warning("未配置 OPENAI_API_KEY，对话图未启用（/chat 将返回 503）")
        return

    checkpointer = None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        dsn = _to_asyncpg_dsn(settings.database_url)
        checkpointer = await stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(dsn)
        )
        await checkpointer.setup()
        logger.info("LangGraph Postgres 检查点已就绪")
    except Exception as exc:  # noqa: BLE001
        logger.warning("检查点初始化失败，对话图降级为无持久化: {}", exc)
        checkpointer = None

    app.state.chat_graph = build_chat_graph(model_fn, checkpointer=checkpointer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("启动 {} ({})", settings.app_name, settings.app_env)
    engine = init_engine(settings.database_url)
    configure_session(engine)
    app.state.engine = engine
    app.state.vector_store = build_vector_store()

    async with AsyncExitStack() as stack:
        await _init_chat_graph(app, settings, stack)
        yield
        await app.state.vector_store.close()
        await engine.dispose()
        logger.info("关闭 {}", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.include_router(health.router, prefix=settings.api_prefix)
    application.include_router(chat.router, prefix=settings.api_prefix)
    application.include_router(document.router, prefix=settings.api_prefix)
    application.include_router(rag.router, prefix=settings.api_prefix)
    application.include_router(agent.router, prefix=settings.api_prefix)
    return application


app = create_app()
