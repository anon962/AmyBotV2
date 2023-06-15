import time
from typing import Awaitable, Callable, ClassVar, Optional

from fastapi import Request
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from config import logger

logger = logger.bind(tags=["server"])

_CallNext = Callable[[Request], Awaitable[StreamingResponse]]


class RequestLog(BaseHTTPMiddleware):
    """Log request and response"""

    def __init__(self, app: ASGIApp, dispatch: Optional[DispatchFunction] = None):
        super().__init__(app, dispatch)

    async def dispatch(self, request: Request, call_next: _CallNext):
        logger.debug(f"{request.method} {request.url}")
        resp = await call_next(request)

        resp_body = [section async for section in resp.body_iterator]
        resp.body_iterator = iterate_in_threadpool(iter(resp_body))

        if resp_body:
            try:
                resp_data = resp_body[0].decode()  # type: ignore
                logger.trace(resp_data)
            except UnicodeDecodeError:
                size = sum(len(x) for x in resp_body)
                logger.trace(f"gzip'd response of size {size}")

        return resp


class ErrorLog(BaseHTTPMiddleware):
    """Log Errors"""

    def __init__(self, app: ASGIApp, dispatch: Optional[DispatchFunction] = None):
        super().__init__(app, dispatch)

    async def dispatch(self, request: Request, call_next: _CallNext):
        try:
            resp = await call_next(request)
            return resp
        except:
            logger.exception("")
            raise


class PerformanceLog(BaseHTTPMiddleware):
    """Measure response time"""

    def __init__(self, app: ASGIApp, dispatch: Optional[DispatchFunction] = None):
        super().__init__(app, dispatch)

    async def dispatch(self, request: Request, call_next: _CallNext):
        start = time.time()
        resp = await call_next(request)
        end = time.time()

        elapsed_ms = (end - start) * 1000
        logger.debug(f"Response took {elapsed_ms:.0f}ms")
        return resp


class GZipWrapper(GZipMiddleware):
    """Wraps GZipMiddleware but only for specific endpoints"""

    endpoints: ClassVar[list[str]] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("path") in self.endpoints:
            return await super().__call__(scope, receive, send)
        else:
            await self.app(scope, receive, send)
