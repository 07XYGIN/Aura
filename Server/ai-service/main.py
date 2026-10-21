import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.agent.graph import agent_graph, agent_runtime
from app.core.config import (
    AURA_CORS_ORIGINS,
    SYNC_DATABASE_URL,
)
from app.core.exceptions import (
    http_exception_handler,
    memory_embeddings_unavailable_handler,
    validation_exception_handler,
)
from app.core.logging_config import configure_logging
from app.core.memory.embeddings import MemoryEmbeddingsUnavailable
from app.middleware.logging_middleware import RequestResponseLoggingMiddleware
from app.routers import (
    admin,
    attachments,
    history,
    location,
    memory,
    msg,
    user,
)

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用生命周期中的 LangGraph 检查点。

    启动时初始化 PostgreSQL 检查点表并构建全局 Agent 图，关闭时释放连接。
    """
    logging.info("正在初始化 LangGraph 检查点")

    with PostgresSaver.from_conn_string(SYNC_DATABASE_URL) as checkpointer:
        checkpointer.setup()
        agent_runtime.graph = agent_graph.build_graph(checkpointer)
        logging.info("Aura 初始化成功")
        yield

    logging.info("程序关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。

    Returns:
        已注册日志/CORS 中间件、业务路由和统一异常处理器的应用实例。
    """
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(RequestResponseLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=AURA_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=86400,
    )
    routers: list[APIRouter] = [
        admin.router,
        msg.router,
        history.router,
        memory.router,
        attachments.router,
        location.router,
        user.router,
    ]
    for router in routers:
        app.include_router(router)

    exception_handlers = [
        (RequestValidationError, validation_exception_handler),
        (HTTPException, http_exception_handler),
        (MemoryEmbeddingsUnavailable, memory_embeddings_unavailable_handler),
    ]
    for exc_type, handler in exception_handlers:
        app.add_exception_handler(exc_type, handler)
    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        port=8000,
        reload=False,
        host="127.0.0.1",
    )

