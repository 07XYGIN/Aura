import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.agent import agent_graph
from app.core.config import SYNC_DATABASE_URL
from app.core.exceptions import (
    validation_exception_handler,
)
from app.core.logging_config import configure_logging
from app.core.proactive_scheduler import start_proactive_scheduler, stop_proactive_scheduler
from app.middleware.logging_middleware import RequestResponseLoggingMiddleware
from app.routers import admin, attachments, aura, history, location, memory, msg, user

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("程序启动成功")

    with PostgresSaver.from_conn_string(SYNC_DATABASE_URL) as checkpointer:
        checkpointer.setup()
        agent_graph.aura = agent_graph.build_graph(checkpointer)
        logging.info("Aura 初始化成功")
        proactive_stop_event = start_proactive_scheduler()
        try:
            yield
        finally:
            await stop_proactive_scheduler(proactive_stop_event)

    logging.info("程序关闭")


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(RequestResponseLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
        aura.router,
        attachments.router,
        location.router,
        user.router,
    ]
    for router in routers:
        app.include_router(router)

    exception_handlers = [
        (RequestValidationError, validation_exception_handler),
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

