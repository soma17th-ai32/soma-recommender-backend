from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

HTTP_ERROR = "HTTP_ERROR"

INVALID_REQUEST_SCHEMA = "INVALID_REQUEST_SCHEMA"
INVALID_REQUEST_SCHEMA_MESSAGE = "Request body does not match the required schema"


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_response(request_id: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(get_request_id(request), exc.code, exc.message),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_response(
            get_request_id(request),
            INVALID_REQUEST_SCHEMA,
            INVALID_REQUEST_SCHEMA_MESSAGE,
        ),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(get_request_id(request), HTTP_ERROR, str(exc.detail)),
    )
