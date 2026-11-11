from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class MaxBodySizeMiddleware:
    """Rejects any request whose declared `Content-Length` exceeds `max_bytes`, before CORS,
    rate limiting, or any route ever runs (2026-10-10, production-readiness pass).

    Before this, the only body-size guards in this app were narrow: a per-field
    `max_length=8000` on the chat message schema, and a dedicated bounded-read helper on the
    two upload routes. Any other JSON body had no enforced ceiling at all. Pure ASGI (not
    `BaseHTTPMiddleware`) and checks the header only, deliberately not a streaming byte-counter -
    it never reads the body itself, so legitimate requests pay zero extra cost. A request with
    no `Content-Length` (e.g. chunked transfer encoding) is not caught here; in practice every
    real document upload and every ASGI client this app serves sets the header for any sizable
    body, so this remains a meaningful net for pathological *declared* sizes without the
    complexity of counting bytes as they stream in.

    Registered last in app.main (so it becomes the outermost layer and runs first on every
    request) - must be large enough to pass through the largest legitimate request body today,
    the 20MB document upload, plus multipart overhead.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        for name, value in scope.get("headers", ()):
            if name == b"content-length":
                try:
                    declared_bytes = int(value)
                except ValueError:
                    declared_bytes = None
                if declared_bytes is not None and declared_bytes > self._max_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "error_type": "RequestBodyTooLargeError",
                            "detail": f"Request body exceeds the maximum allowed size of {self._max_bytes} bytes.",
                        },
                    )
                    await response(scope, receive, send)
                    return
                break

        await self._app(scope, receive, send)
