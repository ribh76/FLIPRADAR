import logging
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from flipradar.api.schemas.common_schema import ApiError, ApiErrorResponse
from flipradar.services.errors import ServiceError

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_code(status_code: int, fallback: str = "request_error") -> str:
    names = {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "not_authenticated",
        status.HTTP_403_FORBIDDEN: "not_authorized",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
        status.HTTP_429_TOO_MANY_REQUESTS: "rate_limit_exceeded",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
        status.HTTP_502_BAD_GATEWAY: "provider_error",
        status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
        status.HTTP_504_GATEWAY_TIMEOUT: "provider_timeout",
    }
    return names.get(status_code, fallback)


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request: Request,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ApiErrorResponse(
        error=ApiError(
            code=code,
            message=message,
            details=details,
            request_id=_request_id(request),
        )
    )
    encoded_payload = jsonable_encoder(payload)
    encoded_payload["detail"] = message
    return JSONResponse(
        status_code=status_code,
        content=encoded_payload,
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "major validation failure route=%s error_count=%s request_id=%s",
        request.url.path,
        len(exc.errors()),
        _request_id(request),
    )
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message="Request validation failed",
        details=jsonable_encoder(exc.errors()),
        request=request,
    )


async def http_exception_handler(
    request: Request, exc: HTTPException | StarletteHTTPException
) -> JSONResponse:
    status_code = exc.status_code
    detail = (
        exc.detail if isinstance(exc.detail, str) else HTTPStatus(status_code).phrase
    )
    if status_code >= 500:
        logger.exception(
            "http server error route=%s status_code=%s request_id=%s",
            request.url.path,
            status_code,
            _request_id(request),
        )
        detail = "Internal server error"
    else:
        logger.warning(
            "handled http error route=%s status_code=%s detail=%s request_id=%s",
            request.url.path,
            status_code,
            detail,
            _request_id(request),
        )
    return error_response(
        status_code=status_code,
        code=_error_code(status_code),
        message=detail,
        details=None if isinstance(exc.detail, str) else exc.detail,
        request=request,
        headers=getattr(exc, "headers", None),
    )


async def service_exception_handler(
    request: Request, exc: ServiceError
) -> JSONResponse:
    logger.warning(
        "handled service error route=%s status_code=%s detail=%s request_id=%s",
        request.url.path,
        exc.status_code,
        str(exc),
        _request_id(request),
    )
    return error_response(
        status_code=exc.status_code,
        code=_error_code(exc.status_code),
        message=str(exc),
        request=request,
    )


async def database_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.exception(
        "database request failure route=%s request_id=%s",
        request.url.path,
        _request_id(request),
    )
    return error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="database_unavailable",
        message="Database operation failed",
        request=request,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled request failure route=%s request_id=%s",
        request.url.path,
        _request_id(request),
    )
    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="Internal server error",
        request=request,
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(ServiceError, service_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
