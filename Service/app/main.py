import uvicorn
import logging
from fastapi import FastAPI
from app.api.v1.user import router as user_router
from app.core.errors import exception_handlers

logging.basicConfig(# type: ignore
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S",
    filemode='a',
    encoding='utf-8'
)
def create_app():
    _app = FastAPI()
    _routers = [user_router]
    for exc_type, handler in exception_handlers:
        _app.add_exception_handler(exc_type, handler)
    for router in _routers:
        _app.include_router(router)
    return _app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        port=3000,
        reload=False,
        host="127.0.0.1",
    )