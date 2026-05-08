from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from soma_api.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from soma_api.routes.health import router as health_router
from soma_api.routes.recommendations import router as recommendations_router


def create_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = f"req_{uuid4().hex}"
        return await call_next(request)

    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_error_handler),
    )
    app.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, http_exception_handler),
    )
    app.include_router(health_router)
    app.include_router(recommendations_router)

    return app


app = create_app()
