"""오류 형식 {code, message, request_id} (명세 4.4)."""

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def _body(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message, "request_id": uuid.uuid4().hex}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # headers(405의 Allow 등)는 그대로 넘긴다
        return JSONResponse(
            _body("http_error", str(exc.detail)),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 입력값(아이 원문일 수 있음)은 싣지 않고 어느 칸이 틀렸는지만 알린다
        fields = ", ".join(".".join(str(p) for p in e.get("loc", ())) for e in exc.errors())
        return JSONResponse(_body("invalid_request", f"요청 형식이 맞지 않아요: {fields}"), 422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, __: Exception) -> JSONResponse:
        # 예외 내용은 응답에 싣지 않는다
        return JSONResponse(_body("internal_error", "잠깐 문제가 생겼어요."), status_code=500)
