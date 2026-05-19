import uvicorn
import logging
from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres import PostgresSaver
from app.routers import msg, login, history, user
from app.core.agent import agent_graph
from app.core.config import SYNC_DATABASE_URL  # 新增
from app.core.exceptions import (
    unicorn_exception_handler, UnicornException,
    validation_exception_handler, loginerr, LoginException
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info('程序启动成功')

    with PostgresSaver.from_conn_string(SYNC_DATABASE_URL) as checkpointer:
        checkpointer.setup()
        agent_graph.aura = agent_graph.build_graph(checkpointer)
        logging.info('Aura初始化成功')
        yield

    logging.info('程序关闭')


def create_app():
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=86400
    )
    routers: list[APIRouter] = [login.router, user.router, msg.router, history.router]
    for router in routers:
        app.include_router(router)

    exception_handlers = [
        (UnicornException, unicorn_exception_handler),
        (LoginException, loginerr),
        (RequestValidationError, validation_exception_handler)
    ]
    for exc_type, handler in exception_handlers:
        app.add_exception_handler(exc_type, handler)
    return app


app = create_app()

if __name__ == '__main__':
    uvicorn.run(
        "main:app",
        port=8000,
        reload=True,
        host="127.0.0.1"
    )