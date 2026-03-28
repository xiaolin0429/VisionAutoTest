from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware


class ApiError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("X-Request-Id") or f"req_{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


def request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid4().hex}")


def success_response(request: Request, data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({
            "data": data,
            "meta": {
                "request_id": request_id_from(request),
            },
        }),
    )


def paginated_response(
    request: Request,
    data: list[Any],
    *,
    page: int,
    page_size: int,
    total: int,
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder({
            "data": data,
            "meta": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "request_id": request_id_from(request),
            },
        }),
    )


def error_response(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            "meta": {
                "request_id": request_id_from(request),
            },
        }),
    )


def no_content_response() -> Response:
    return Response(status_code=204)
